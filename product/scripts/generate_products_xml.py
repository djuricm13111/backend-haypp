#!/usr/bin/env python
# generate_products_xml.py
# Generiše frontend-haypp/public/products.xml (sitemap-feed proizvoda + brendova)
# direktno iz baze. Jedan sajt/frontend (snuswe.com), za razliku od multi-frontend
# verzije ove skripte iz drugog projekta — nema Frontend/excluded_frontends, samo
# globalni MAX_NICOTINE_MG_PER_POUCH (ista granica koju katalog već primenjuje u
# CatalogFilterMixin.apply_nicotine_limit, da sitemap ne nudi linkove ka
# proizvodima koji bi na sajtu vratili 404).
#
# Pokretanje: python product/scripts/generate_products_xml.py

import os
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(BASE_DIR))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings")
import django

django.setup()

from django.conf import settings
from django.db.models import Q
from django.utils import timezone
from product.models import Category, Product

BASE_URL = "https://www.snuswe.com"
LANGUAGES = ["en", "de", "hu"]
OUTPUT_PATH = BASE_DIR.parent / "frontend-haypp" / "public" / "products.xml"


def add_url(urlset, path, lastmod):
    for lang in LANGUAGES:
        url_el = ET.SubElement(urlset, "url")
        loc = ET.SubElement(url_el, "loc")
        loc.text = f"{BASE_URL}/{lang}/{path}"
        lastmod_el = ET.SubElement(url_el, "lastmod")
        lastmod_el.text = lastmod.strftime("%Y-%m-%d")


def build():
    max_n = getattr(settings, "MAX_NICOTINE_MG_PER_POUCH", 999)
    products = list(
        Product.objects.select_related("category")
        .filter(Q(nicotine__isnull=True) | Q(nicotine__lte=max_n))
        .order_by("slug")
    )

    categories_with_products = {p.category_id for p in products}
    brands = list(
        Category.objects.filter(id__in=categories_with_products).order_by("slug")
    )

    urlset = ET.Element("urlset", {"xmlns": "http://www.sitemaps.org/schemas/sitemap/0.9"})

    # Category nema timestamp polje, pa se brend-stranicama daje današnji datum.
    today = timezone.now()
    for c in brands:
        add_url(urlset, c.slug, today)

    for p in products:
        add_url(urlset, f"{p.category.slug}/{p.slug}", p.updated_at)

    tree = ET.ElementTree(urlset)
    ET.indent(tree, space="  ")
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    tree.write(OUTPUT_PATH, encoding="utf-8", xml_declaration=True)

    print(f"{len(products)} products + {len(brands)} brands x {len(LANGUAGES)} languages -> {OUTPUT_PATH}")


if __name__ == "__main__":
    build()
