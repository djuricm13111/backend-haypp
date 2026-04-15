import os
import sys
from pathlib import Path

# 1) Dodaj root Django projekta u PATH
CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# 2) Podesi Django settings i setup
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings")
import django
django.setup()

from django.utils.text import slugify
from load_products import load_gs_products
from scraper_nordic import get_supplier_availability
from product.models import Product, ProductState, refresh_all_mixpack_bundles

# === Učitaj stanja iz GS (wholesale / SR sheet) ===
def load_gs_stock():
    url_sr = "https://docs.google.com/spreadsheets/d/1aDjxdxoAUE5qH7rwRYo8Rlt0xwf9LZXjy6f88BolXYg"
    sheet_sr = "wholesale"
    data = load_gs_products(sheet_name=sheet_sr, spreadsheet_url=url_sr)

    result = {}
    for row in data:
        name = row.get("Product", "").strip()
        raw = row.get("Stanje", "")
        raw_str = raw.strip() if isinstance(raw, str) else str(raw)
        try:
            qty = int(raw_str)
        except (ValueError, TypeError):
            qty = 0

        slug = slugify(name)
        result[slug] = qty
    return result


def update_my_stock_only():
    stock_sr = load_gs_stock()
    affected = 0

    for product in Product.objects.all():
        slug = product.slug
        qty_sr = stock_sr.get(slug)
        if qty_sr is not None:
            qty_sr = max(qty_sr, 0)
            Product.objects.filter(pk=product.pk).update(
                state=ProductState.IN_STOCK,
                stock=qty_sr,
            )
        affected += 1

    refresh_all_mixpack_bundles()
    print(f"✅ Ažurirano GS stanje: {affected} proizvoda (+ mix pack stanja)")


def update_all_stock():
    stock_sr = load_gs_stock()
    supplier_stock = get_supplier_availability()
    affected = 0

    for product in Product.objects.all():
        slug = product.slug

        qty_sr = stock_sr.get(slug)
        if qty_sr is not None:
            qty_sr = max(qty_sr, 0)
            state_sr = ProductState.IN_STOCK
            stock_val_sr = qty_sr
        elif supplier_stock.get(slug):
            state_sr = ProductState.IN_STOCK
            stock_val_sr = 0
        else:
            state_sr = ProductState.OUT_OF_STOCK
            stock_val_sr = 0

        Product.objects.filter(pk=product.pk).update(state=state_sr, stock=stock_val_sr)
        affected += 1

    refresh_all_mixpack_bundles()
    print(f"✅ Ažurirano kompletno stanje (GS + dobavljač): {affected} proizvoda (+ mix pack stanja)")

    from django.db.models import Q
    valid_slugs = set(stock_sr.keys()) | set(supplier_stock.keys())
    stale_products = Product.objects.filter(~Q(slug__in=valid_slugs), is_deleted=False)
    affected_deleted = stale_products.update(is_deleted=True)
    print(f"🗑️ Obeleženo kao obrisano: {affected_deleted} proizvoda")


if __name__ == "__main__":
    update_all_stock()
