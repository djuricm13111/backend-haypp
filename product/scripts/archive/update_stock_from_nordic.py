#!/usr/bin/env python
# update_stock_from_nordic.py
# Ažurira stanje proizvoda isključivo na osnovu Nordic scrape-a.
# Proizvodi koje Nordic ima → IN_STOCK
# Proizvodi koje Nordic nema → OUT_OF_STOCK
# Proizvodi koji nisu nigde na Nordicu → ostaju nepromijenjeni (samo se loguje)

import os
import sys
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(CURRENT_DIR))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings")
import django
django.setup()

from product.models import Product, ProductState, refresh_all_mixpack_bundles
from scraper_nordic import get_supplier_availability


def update_stock_from_nordic():
    print("🔍 Učitavam dostupnost sa Nordica...")
    supplier_stock = get_supplier_availability()

    in_stock_count   = 0
    out_stock_count  = 0
    not_found_count  = 0

    for product in Product.objects.filter(is_deleted=False):
        available = supplier_stock.get(product.slug)

        if available is True:
            Product.objects.filter(pk=product.pk).update(
                state=ProductState.IN_STOCK,
                stock=0,
            )
            in_stock_count += 1
        elif available is False:
            Product.objects.filter(pk=product.pk).update(
                state=ProductState.OUT_OF_STOCK,
                stock=0,
            )
            out_stock_count += 1
        else:
            not_found_count += 1
            print(f"⚠️  Nije pronađen na Nordicu: {product.slug}")

    refresh_all_mixpack_bundles()

    print(f"\n✅ IN_STOCK:     {in_stock_count}")
    print(f"❌ OUT_OF_STOCK: {out_stock_count}")
    print(f"❓ Nije na Nordicu (ostavljeno nepromijenjeno): {not_found_count}")


if __name__ == "__main__":
    update_stock_from_nordic()
