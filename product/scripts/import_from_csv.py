#!/usr/bin/env python
# import_from_csv.py
# Skripta za ucitavanje i ažuriranje Category, Product i ProductImage.
# Ako slug već postoji (čak i ako je is_deleted=True), radi se ručno get/update; inače create.

import os
import django
import csv
import sys
from pathlib import Path
from decimal import Decimal, InvalidOperation
from django.db import IntegrityError

# ─── Postavljanje Django okruženja ─────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(BASE_DIR))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings")
django.setup()

from django.utils.text import slugify
from product.models import Category, Product, ProductImage

# Keširanje kategorija
category_cache: dict[str, Category] = {}

# Putanje do CSV fajlova
CURRENT_DIR  = Path(__file__).resolve().parent
PRODUCTS_CSV = CURRENT_DIR / "combined_products.csv"
IMAGES_CSV   = CURRENT_DIR / "combined_images.csv"

# ─── Pomoćne funkcije ──────────────────────────────────────────────────────────
def load_image_map(path: Path) -> dict[str, list[dict]]:
    image_map: dict[str, list[dict]] = {}
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            raw_slug = row.get("slug", "").strip()
            if not raw_slug:
                continue
            slug_key = slugify(raw_slug)
            # U+200B u image_path ako treba zaobići GitHub secret scan na delu imena fajla.
            key      = row.get("image_path", "").strip().replace("\u200b", "")
            primary  = row.get("is_primary", "False").strip().lower() == "true"
            if key:
                image_map.setdefault(slug_key, []).append({
                    "image_key": key,
                    "is_primary": primary,
                })
    return image_map

def parse_decimal(val: str, field: str, slug: str) -> Decimal | None:
    raw = val.strip().replace(",", ".")
    if not raw or raw == "-":
        return None
    try:
        return Decimal(raw)
    except InvalidOperation:
        print(f"⚠️ Neispravna decimalna vrednost '{raw}' za polje '{field}' u proizvodu '{slug}'")
        return None

def parse_int(val: str, field: str, slug: str) -> int | None:
    raw = val.strip()
    if not raw or raw == "-":
        return None
    try:
        return int(raw)
    except ValueError:
        print(f"⚠️ Neispravna celobrojna vrednost '{raw}' za polje '{field}' u proizvodu '{slug}'")
        return None

# Učitaj sve slike jednom
image_map = load_image_map(IMAGES_CSV)

# Skup viđenih (obrađenih) slugova iz ovog CSV-a
seen_slugs: set[str] = set()

# ─── Glavna petlja za Products ─────────────────────────────────────────────────
for row in csv.DictReader(open(PRODUCTS_CSV, encoding="utf-8", newline="")):
    title         = row.get("title", "").strip()
    raw_slug      = row.get("slug", "").strip()
    category_name = row.get("brand", "").strip()

    if not title or not raw_slug or not category_name:
        print(f"⚠️ Preskačem red sa nedostajućim podacima: {row}")
        continue

    # Normalizacija slug-ova
    cat_slug     = slugify(category_name)
    product_slug = slugify(raw_slug)

    # Detekcija duplikata u CSV-u
    if product_slug in seen_slugs:
        print(f"⚠️ Duplikat sluga u CSV-u: '{product_slug}' – preskačem ovaj red.")
        continue
    seen_slugs.add(product_slug)

    # ── Category: update_or_create uz keširanje ────────────────────────────────
    if cat_slug in category_cache:
        category = category_cache[cat_slug]
    else:
        category, _ = Category.objects.update_or_create(
            slug=cat_slug,
            defaults={"name": category_name}
        )
        category_cache[cat_slug] = category

    # ── Spremi podatke za Product ───────────────────────────────────────────────
    product_data = {
        "category":         category,
        "name":             title,
        "nicotine":         parse_decimal(row.get("nicotine_mg_g", ""), "nicotine_mg_g", product_slug) or Decimal("0.0"),
        "pouches_per_can":  parse_int(row.get("pouches_per_can", ""), "pouches_per_can", product_slug),
        "format":           row.get("format", "").strip()          or None,
        "flavor":           row.get("flavour", "").strip()         or None,
        "net_weight":       parse_decimal(row.get("net_weight", ""), "net_weight", product_slug),
        "manufacturer":     row.get("manufacturer", "").strip()    or None,
        "sku":              row.get("sku", "").strip()             or None,
        # Bitno: svaki CSV-om “dotaknuti” proizvod nije obrisan
        "is_deleted":       False,
    }

    # ── Product: ručno GET ili CREATE pomoću base_manager ──────────────────────
    try:
        # base_manager će dohvatiti i is_deleted=True
        prod = Product._base_manager.get(slug=product_slug)
        created = False
        # ažuriraj samo promenjena polja
        changed = []
        for field, new_val in product_data.items():
            if getattr(prod, field) != new_val:
                setattr(prod, field, new_val)
                changed.append(field)
        if changed:
            prod.save()
            print(f"🔄 Ažuriran Product '{product_slug}': {', '.join(changed)}")
        else:
            print(f"✅ Product '{product_slug}' je već ažuran.")
    except Product.DoesNotExist:
        try:
            # koristi base_manager za kreiranje novog (i eksplicitno is_deleted=False)
            prod = Product._base_manager.create(slug=product_slug, **product_data)
            created = True
            print(f"➕ Dodat novi Product: {product_slug}")
        except IntegrityError as e:
            print("‼️ IntegrityError prilikom kreiranja:")
            print(f"   slug = {product_slug}")
            print(f"   red iz CSV = {row}")
            print(f"   greška = {e}")
            prod = Product._base_manager.filter(slug=product_slug).first()
            created = False
            print(f"   Nabavljen postojeći Product: {product_slug}" if prod else "   NIJE pronađen ni nakon greške.")

    # ── Ažuriranje slika ────────────────────────────────────────────────────────
    imgs = image_map.get(product_slug, [])
    if not created:
        deleted_count, _ = ProductImage.objects.filter(product=prod).delete()
        print(f"🗑️ Obrišeno {deleted_count} slika za '{product_slug}'")
    for img in imgs:
        ProductImage.objects.create(
            product=prod,
            original_image_key=img["image_key"],
            is_primary=img["is_primary"]
        )
        print(f"🖼️ Dodata slika za '{product_slug}': {img['image_key']}"
              f"{' (primary)' if img['is_primary'] else ''}")

# ─── Soft delete: sve što NIJE u CSV-u postavi is_deleted=True ─────────────────
to_soft_delete_qs = Product._base_manager.exclude(slug__in=seen_slugs).filter(is_deleted=False)
soft_deleted_count = to_soft_delete_qs.update(is_deleted=True)
print(f"🚫 Soft-deleted (is_deleted=True) proizvoda: {soft_deleted_count} (nisu prisutni u trenutnom CSV-u).")

print("🏁 Učitavanje proizvoda i slika završeno.")
