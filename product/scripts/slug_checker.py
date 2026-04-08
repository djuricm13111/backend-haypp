#!/usr/bin/env python3
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

# 3) Importuj modele i slugify
from django.utils.text import slugify
from product.models import Product

def main():
    updated = 0
    for p in Product.objects.all():
        correct_slug = slugify(p.name)
        if p.slug != correct_slug:
            print(f"[{p.pk}] „{p.slug}” → „{correct_slug}”")
            p.slug = correct_slug
            p.save(update_fields=["slug"])
            updated += 1
    print(f"\nUkupno ispravljenih slugova: {updated}")

if __name__ == "__main__":
    main()
