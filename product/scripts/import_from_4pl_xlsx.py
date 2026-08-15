#!/usr/bin/env python
# import_from_4pl_xlsx.py
#
# Uvozi Nicotine Pouch katalog iz "4PL Product export_ALL ACTIVE.xlsx" u bazu.
# Namenjeno da se pokrene NA PRAZNOM katalogu (posle hard_reset_products.py).
#
# Kolone u xlsx-u: product_name, brand, sku, hs_code, country_of_origin,
# specifications, attributes, weight, gtin, status, stock, image 1..7
#
# 'attributes' je ; -razdvojena lista Key_Value parova (npr.
# "Flavour_Mint;Format_Slim;Nicotine (mg/pouch)_10.4;Type_Nicotine pouch").
#
# Pravila:
# - status kolona (published/inactive) se ignoriše — nije pouzdan indikator dostupnosti.
# - stock se upisuje direktno u Product.stock (jedno skladište, bez per-frontend razlika).
# - nicotine = "Nicotine (mg/pouch)" (NE mg/g — to je koncentracija, ne doza po kesici).
#   "Nicotine free" tip nema uvek eksplicitnu vrednost → nicotine=0.
# - Uključeni tipovi: Nicotine pouch(es), Nicotine free, Vitt snus.
# - Isključeni: e-cigarete (Produkttyp=E-Cigarette, npr. Vozol), Energy Pouches/pouch
#   (kofein, ne nikotin), Supplies/Streetwear (merch/pribor), i redovi bez "Type" atributa
#   uopšte (display/POS stalci, ili redovi bez ijednog atributa — nema dovoljno podataka).
# - sku se upisuje direktno iz fajla (svi skuovi u fajlu su međusobno jedinstveni).
# - manufacturer i price se NE popunjavaju iz xlsx-a (nema tih podataka / cena ručno).
# - slika koristi pun URL sa dobavljačevog CDN-a direktno (ProductImage.original_image_key
#   prepoznaje http(s) i ne lepi S3 prefiks — vidi Product Image.get_image_url()).

import os
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path

import django
import openpyxl

BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(BASE_DIR))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings")
django.setup()

from django.utils.text import slugify
from product.models import Category, Product, ProductImage

XLSX_PATH = Path(__file__).resolve().parent / "4PL Product export_ALL ACTIVE.xlsx"

INCLUDED_POUCH_TYPES = {"nicotine pouch", "nicotine pouches", "vitt snus"}
FREE_POUCH_TYPES = {"nicotine free"}
IMAGE_COLUMNS = [f"image {i}" for i in range(1, 8)]

# Brendovi (Category.slug) koji se u potpunosti preskaču pri uvozu — nijedan
# proizvod tog brenda se ne upisuje u bazu (ne kreira se ni Category ni
# Product, ne filtrira se naknadno). Uredi po potrebi i pokreni ponovo —
# skripta je idempotentna i briše prethodno uvezene proizvode/kategorije
# za brendove koji su ovde naknadno dodati.
#
# Lista dole = svi brendovi pomenuti u set_category_frontend_exclusions.py
# iz drugog projekta (49 "manje popularnih" brendova iz tog dogovora).
# Obriši odavde one koje ipak želiš da zadržiš u katalogu.
EXCLUDED_BRAND_SLUGS = {
    "apres",
    "avant",
    
    "garant",
    "glick",
    "greatest",
    "helwit",
    "ice",
    "iceberg",
    "its",
    "juice-head",
    "kelly-white",
    "klar",
    "klint",
    "kuma",
    "leo",
    "lewa",
    "loop",
    "lumi",
    "lundgrens",
    "maggie",
    "mynt",
    "neafs",
    "nyytti",
    "pura",
    
    "rave",
    "relx",
    "royal-white",
    "smogen",
    "snoberg",
    "xpct",
    "tectonic",
    "togo",
    "tyr",
    "valkyria",
    "vid",
    "vika",
    
    "zeronito",

# "baron",
#     "brute",
#     "chainpop",
#     "denssi",
#     "edel",
#     "fold",
#     "fumi",
#     "snowman",
#     "stng",
#     "xo",
    
#     "xqs",
#"rabbit",

}


def parse_attributes(raw):
    """'Flavour_Mint;Format_Slim;Nicotine (mg/pouch)_10.4' -> dict."""
    d = {}
    for part in (raw or "").split(";"):
        if "_" in part:
            key, value = part.rsplit("_", 1)
            d[key.strip()] = value.strip()
    return d


def classify(attrs):
    """Vraća 'include', 'include_free', ili razlog isključenja (string)."""
    produkttyp = (attrs.get("Produkttyp") or "").strip().lower()
    if produkttyp == "e-cigarette":
        return "skip_ecig"

    type_raw = attrs.get("Type")
    if type_raw is None:
        return "skip_no_type"

    t = type_raw.strip().lower()
    if t in INCLUDED_POUCH_TYPES:
        return "include"
    if t in FREE_POUCH_TYPES:
        return "include_free"
    if t in ("energy pouches", "energy pouch"):
        return "skip_energy"
    if t in ("supplies", "streetwear"):
        return "skip_merch"
    return f"skip_unknown_type:{t}"


def to_decimal(value):
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value))
    except InvalidOperation:
        return None


def to_int(value, default=None):
    if value in (None, ""):
        return default
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return default


def remove_excluded_brands():
    """Briše kategorije (i kaskadno njihove proizvode) za brendove koji su
    naknadno dodati u EXCLUDED_BRAND_SLUGS, ako su ranije već uvezeni."""
    qs = Category.objects.filter(slug__in=EXCLUDED_BRAND_SLUGS)
    removed_slugs = list(qs.values_list("slug", flat=True))
    deleted, _ = qs.delete()
    if removed_slugs:
        print(f"Uklonjeno {deleted} redova za ranije uvezene isključene brendove: {', '.join(removed_slugs)}")


def main():
    remove_excluded_brands()

    wb = openpyxl.load_workbook(XLSX_PATH, data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    header = rows[0]
    idx = {name: i for i, name in enumerate(header)}

    created = 0
    updated = 0
    skipped_counts = {}
    warnings = []
    category_cache = {}

    for row in rows[1:]:
        name = row[idx["product_name"]]
        if not name:
            skipped_counts["skip_no_name"] = skipped_counts.get("skip_no_name", 0) + 1
            continue

        attrs = parse_attributes(row[idx["attributes"]])
        reason = classify(attrs)

        if reason not in ("include", "include_free"):
            skipped_counts[reason] = skipped_counts.get(reason, 0) + 1
            continue

        brand = row[idx["brand"]] or "Unknown"
        cat_slug = slugify(brand)

        if cat_slug in EXCLUDED_BRAND_SLUGS:
            skipped_counts["skip_excluded_brand"] = skipped_counts.get("skip_excluded_brand", 0) + 1
            continue

        category = category_cache.get(cat_slug)
        if category is None:
            category, _ = Category.objects.get_or_create(
                slug=cat_slug, defaults={"name": brand}
            )
            category_cache[cat_slug] = category

        sku = row[idx["sku"]]
        sku = str(sku).strip() if sku is not None else None

        if reason == "include_free":
            nicotine = Decimal("0")
        else:
            nicotine = to_decimal(attrs.get("Nicotine (mg/pouch)"))
            if nicotine is None:
                warnings.append(f"{name} (sku={sku}): nema 'Nicotine (mg/pouch)' vrednost, nicotine ostaje prazan")

        flavor = attrs.get("Flavour")
        fmt = attrs.get("Format") or attrs.get("Style")
        net_weight = to_decimal(attrs.get("Net Weight (gram)"))
        pouches_per_can = to_int(attrs.get("Number of Portions"))
        # dobavljač ume da pošalje negativan stock (backorder/oversold) — Product.stock je
        # PositiveIntegerField, pa se to tretira kao 0 na stanju.
        stock = max(0, to_int(row[idx["stock"]], default=0))

        base_slug = slugify(name)
        slug_taken = (
            Product.objects.all_including_deleted()
            .filter(slug=base_slug)
            .exclude(sku=sku)
            .exists()
        )
        slug = f"{base_slug}-{slugify(sku)}" if (slug_taken and sku) else base_slug

        defaults = {
            "category": category,
            "name": name,
            "slug": slug,
            "nicotine": nicotine,
            "flavor": flavor,
            "format": fmt,
            "net_weight": net_weight,
            "pouches_per_can": pouches_per_can,
            "stock": stock,
        }

        if sku:
            product, was_created = Product.objects.all_including_deleted().update_or_create(
                sku=sku, defaults=defaults
            )
        else:
            defaults["sku"] = None
            product = Product.objects.create(**defaults)
            was_created = True

        if was_created:
            created += 1
        else:
            updated += 1

        image_urls = [row[idx[col]] for col in IMAGE_COLUMNS if row[idx[col]]]
        if image_urls:
            product.images.all().delete()
            for i, url in enumerate(image_urls):
                ProductImage.objects.create(
                    product=product,
                    original_image_key=url,
                    is_primary=(i == 0),
                )

    print(f"Kreirano: {created}")
    print(f"Ažurirano: {updated}")
    print("Preskočeno po razlogu:")
    for reason, count in sorted(skipped_counts.items(), key=lambda x: -x[1]):
        print(f"  {reason}: {count}")
    if warnings:
        print(f"\nUpozorenja ({len(warnings)}):")
        for w in warnings[:30]:
            print(f"  - {w}")
        if len(warnings) > 30:
            print(f"  ... i još {len(warnings) - 30}")


if __name__ == "__main__":
    main()
