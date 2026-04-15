#!/usr/bin/env python
"""
Učitavanje običnih proizvoda iz YAML-a (ista šema polja kao mixpack YAML, bez MixPackLine).

  cd backend && python product/scripts/import_products_from_yaml.py --dry-run
  python product/scripts/import_products_from_yaml.py --file templates/moji.yaml

Ključevi mix_components / bundle_components u YAML-u se ignorišu — koristi import_mixpacks_from_yaml.py za bundle.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings")

import runpy

_mix = runpy.run_path(
    str(Path(__file__).resolve().parent / "import_mixpacks_from_yaml.py"),
)
upsert_product = _mix["upsert_product"]

import yaml
from django.db import IntegrityError

DEFAULT_FILE = Path(__file__).resolve().parent / "templates" / "products.yaml"
EXAMPLE_FILE = Path(__file__).resolve().parent / "templates" / "products.example.yaml"


def main() -> None:
    p = argparse.ArgumentParser(description="Import products from YAML (no mix lines).")
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

    print(f"📄 {path} — {len(items)} stavki — dry_run={args.dry_run} (bez mix linija)\n")

    for i, doc in enumerate(items, start=1):
        if not isinstance(doc, dict):
            print(f"  [{i}] SKIP: nije objekat")
            continue
        try:
            msg = upsert_product(doc, args.dry_run, sync_mix_lines=False)
        except IntegrityError as e:
            msg = f"GREŠKA IntegrityError: {e}"
        print(f"  [{i}] {msg}")

    print("\n🏁 Gotovo.")
    if args.dry_run:
        print("   (Ponovi bez --dry-run za upis u bazu.)")


if __name__ == "__main__":
    main()
