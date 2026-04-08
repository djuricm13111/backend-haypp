#!/usr/bin/env python
# scripts/update_prices_by_brand.py
# Skripta za masovno ažuriranje cena proizvoda po brendu (kategoriji),
# sa podrazumevanom cenom za brendove koji nisu eksplicitno definisani.

import os
import sys
from decimal import Decimal

# 1) Dodaj Django projekat u PATH
def main():
    BASE_DIR = Path(__file__).resolve().parent.parent.parent
    sys.path.insert(0, str(BASE_DIR))

    # 2) Podesi Django settings i inicijalizuj
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
    import django
    django.setup()

    from product.models import Category, Product

    # 3) Definiši specifične cene po slug-u brenda (kategorije)
    brand_prices = {
        'velo': Decimal('4.79'),
        'zyn': Decimal('4.99'),
        'lyft': Decimal('4.99'),
        'ace': Decimal('4.88'),
        'skruf': Decimal('4.69'),
        '77': Decimal('4.58'),
        'xqs': Decimal('4.79'),
    }

    # Default cena za brendove koji nisu u gornjem nizu
    default_price = Decimal('4.78')

    # 4) Prođi kroz sve kategorije i ažuriraj
    for category in Category.objects.all():
        slug = category.slug
        price = brand_prices.get(slug, default_price)

        products = Product.objects.filter(category=category)
        count = products.update(price=price)

        print(f"🔄 Brend '{slug}' ({category.name}): ažurirano {count} proizvoda na cenu {price} EUR")

    print("✅ Ažuriranje cena završeno.")

if __name__ == '__main__':
    from pathlib import Path
    main()
