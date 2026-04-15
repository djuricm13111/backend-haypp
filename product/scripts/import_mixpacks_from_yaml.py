#!/usr/bin/env python
"""
Učitavanje mix pack / bundle proizvoda iz YAML fajla (preglednije od CSV-a).

  cd backend/product/scripts
  python import_mixpacks_from_yaml.py
  python import_mixpacks_from_yaml.py --file templates/moj_mixpacks.yaml --dry-run

Zahtev: PyYAML (već u backend/requirements.txt).
"""
from __future__ import annotations

import argparse
import os
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings")

import django

django.setup()

import yaml
from django.db import IntegrityError
from django.utils.text import slugify
from djmoney.money import Money

from product.models import Category, MixPackLine, Product, ProductImage, ProductState
from scripts.currency_converter import DEFAULT_CURRENCY

DEFAULT_FILE = Path(__file__).resolve().parent / "templates" / "mixpacks.yaml"
EXAMPLE_FILE = Path(__file__).resolve().parent / "templates" / "mixpacks.example.yaml"

VALID_STATES = {c.value for c in ProductState}


def _dec(val, default=None) -> Decimal | None:
    if val is None or val == "":
        return default
    if isinstance(val, (int, float)):
        return Decimal(str(val))
    s = str(val).strip().replace(",", ".")
    if not s or s.lower() in ("-", "null", "none", "mixed"):
        return default
    try:
        return Decimal(s)
    except InvalidOperation:
        return default


def _int(val, default=0) -> int:
    if val is None or val == "":
        return default
    try:
        return int(val)
    except (TypeError, ValueError):
        return default


def _money(amount_str: str | None, currency: str | None) -> Money | None:
    if amount_str is None or str(amount_str).strip() == "":
        return None
    d = _dec(amount_str)
    if d is None:
        return None
    cur = (currency or DEFAULT_CURRENCY).upper()
    return Money(d, cur)


def _yaml_defines_mix_components(doc: dict) -> bool:
    return "mix_components" in doc or "bundle_components" in doc


def _sync_mix_lines_from_yaml(doc: dict, prod: Product) -> str:
    """Vraća sufiks poruke. Prazna lista briše linije; ključ nedostaje = ne dira postojeće linije u bazi."""
    if not _yaml_defines_mix_components(doc):
        return ""
    raw = doc.get("mix_components")
    if raw is None and "bundle_components" in doc:
        raw = doc.get("bundle_components")
    if raw is None:
        raw = []
    if not isinstance(raw, list):
        return " (mix_components moraju biti lista)"
    MixPackLine.objects.filter(mix_product=prod).delete()
    if not raw:
        return ", mix linije uklonjene (običan proizvod)"
    to_create: list[MixPackLine] = []
    missing: list[str] = []
    for row in raw:
        if not isinstance(row, dict):
            continue
        cslug = slugify((row.get("slug") or "").strip())
        qty = max(1, _int(row.get("quantity"), 1))
        comp = Product._base_manager.filter(slug=cslug, is_deleted=False).first()
        if not comp:
            missing.append(cslug)
            continue
        if comp.pk == prod.pk:
            continue
        to_create.append(
            MixPackLine(
                mix_product=prod,
                component_product=comp,
                quantity=qty,
            )
        )
    if raw and not to_create:
        Product._base_manager.filter(pk=prod.pk).update(
            stock=0,
            state=ProductState.OUT_OF_STOCK,
        )
        return f" (mix: nijedna komponenta nije pronađena: {', '.join(missing) or '?'})"
    if to_create:
        MixPackLine.objects.bulk_create(to_create)
    prod.refresh_mixpack_from_components(save=True)
    suf = f", mix komponenti: {len(to_create)}"
    if missing:
        suf += f" (nedostaju slugovi: {', '.join(missing)})"
    return suf


def upsert_product(doc: dict, dry_run: bool, *, sync_mix_lines: bool = True) -> str:
    name = (doc.get("name") or "").strip()
    raw_slug = (doc.get("slug") or "").strip()
    brand = (doc.get("brand") or "").strip()

    if not name or not raw_slug or not brand:
        return "SKIP: nedostaje name, slug ili brand"

    if len(name) > 100:
        return f"SKIP: name duži od 100 karaktera ({len(name)}): {name[:40]}…"

    product_slug = slugify(raw_slug)
    cat_slug = slugify(brand)

    nic = _dec(doc.get("nicotine_mg_per_pouch"), Decimal("0"))
    if nic is None:
        nic = Decimal("0")

    pouches = doc.get("pouches_per_can")
    pouches_i = _int(pouches, 0) if pouches is not None else None

    fmt = (doc.get("format") or "").strip() or None
    flavor = (doc.get("flavor") or doc.get("flavour") or "").strip() or None
    net_w = _dec(doc.get("net_weight_grams"))
    mfr = (doc.get("manufacturer") or "").strip() or None
    sku = (doc.get("sku") or "").strip() or None

    state_raw = (doc.get("state") or "in_stock").strip().lower()
    if state_raw not in VALID_STATES:
        state_raw = ProductState.IN_STOCK.value

    stock = max(0, _int(doc.get("stock"), 0))
    price = _money(doc.get("price_amount"), doc.get("currency"))
    disc = _money(doc.get("discounted_price_amount"), doc.get("currency"))
    if disc is not None and price is None:
        disc = None  # discounted bez regular price — ignoriši

    images = doc.get("images") or []
    if not isinstance(images, list):
        images = []

    if dry_run:
        mix_desc = ""
        if sync_mix_lines:
            mix_raw = doc.get("mix_components")
            if mix_raw is None and "bundle_components" in doc:
                mix_raw = doc.get("bundle_components")
            if isinstance(mix_raw, list) and mix_raw:
                bits = []
                for row in mix_raw:
                    if isinstance(row, dict):
                        bits.append(
                            f"{slugify((row.get('slug') or '').strip())}×{_int(row.get('quantity'), 1)}"
                        )
                mix_desc = f" mix=[{', '.join(bits)}]"
            elif _yaml_defines_mix_components(doc) and isinstance(mix_raw, list):
                mix_desc = " mix=[]"
        return (
            f"DRY-RUN OK: slug={product_slug} brand={brand} "
            f"price={price} images={len(images)} state={state_raw}{mix_desc}"
        )

    category, _ = Category.objects.update_or_create(
        slug=cat_slug, defaults={"name": brand}
    )

    defaults = {
        "category": category,
        "name": name,
        "nicotine": nic,
        "pouches_per_can": pouches_i,
        "format": fmt,
        "flavor": flavor,
        "net_weight": net_w,
        "manufacturer": mfr,
        "sku": sku,
        "state": state_raw,
        "stock": stock,
        "is_deleted": False,
    }
    if price is not None:
        defaults["price"] = price
        defaults["currency"] = price.currency.code
    if disc is not None:
        defaults["discounted_price"] = disc

    prod, created = Product._base_manager.update_or_create(
        slug=product_slug,
        defaults=defaults,
    )

    if images:
        ProductImage.objects.filter(product=prod).delete()
        for img in images:
            if not isinstance(img, dict):
                continue
            key = (img.get("s3_key") or img.get("image_path") or "").strip()
            if not key:
                continue
            primary = bool(img.get("primary", img.get("is_primary", False)))
            ProductImage.objects.create(
                product=prod,
                original_image_key=key,
                is_primary=primary,
            )

    mix_msg = _sync_mix_lines_from_yaml(doc, prod) if sync_mix_lines else ""
    action = "kreiran" if created else "ažuriran"
    return f"OK: {product_slug} ({action}), slike: {len(images)}{mix_msg}"


def main() -> None:
    p = argparse.ArgumentParser(description="Import mixpack products from YAML.")
    p.add_argument(
        "--file",
        type=Path,
        default=None,
        help=f"Putanja do YAML (podrazumevano: {DEFAULT_FILE})",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Samo ispisi šta bi uradio, bez upisa u bazu",
    )
    args = p.parse_args()
    path = args.file or DEFAULT_FILE

    if not path.is_file():
        print(f"❌ Fajl ne postoji: {path}")
        if EXAMPLE_FILE.is_file():
            print(f"   Kopiraj primer: cp {EXAMPLE_FILE} {DEFAULT_FILE}")
        sys.exit(1)

    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    items = (data or {}).get("products")
    if not isinstance(items, list):
        print("❌ YAML mora imati ključ 'products:' sa listom stavki.")
        sys.exit(1)
    if not items:
        print("ℹ️ Lista `products` je prazna — nema šta da se uradi.")
        sys.exit(0)

    print(f"📄 {path} — {len(items)} stavki — dry_run={args.dry_run}\n")

    for i, doc in enumerate(items, start=1):
        if not isinstance(doc, dict):
            print(f"  [{i}] SKIP: nije objekat")
            continue
        try:
            msg = upsert_product(doc, args.dry_run)
        except IntegrityError as e:
            msg = f"GREŠKA IntegrityError: {e}"
        print(f"  [{i}] {msg}")

    print("\n🏁 Gotovo.")
    if args.dry_run:
        print("   (Ponovi bez --dry-run za upis u bazu.)")


if __name__ == "__main__":
    main()
