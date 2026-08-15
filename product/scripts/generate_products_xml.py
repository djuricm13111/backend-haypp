#!/usr/bin/env python
# generate_products_xml.py
# Generiše frontend-haypp/public/products.xml (sitemap-feed proizvoda + brendova)
# direktno iz baze, sa hreflang alternate linkovima, changefreq i priority.
#
# Pokretanje: python product/scripts/generate_products_xml.py

import os
import sys
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
DEFAULT_LANG = "en"
OUTPUT_PATH = BASE_DIR.parent / "frontend-haypp" / "public" / "products.xml"


def url_block(path: str, lastmod_str: str, changefreq: str, priority: str) -> str:
    en_url = f"{BASE_URL}/{DEFAULT_LANG}/{path}"
    blocks = []
    for lang in LANGUAGES:
        lang_url = f"{BASE_URL}/{lang}/{path}"
        alts = f'    <xhtml:link rel="alternate" hreflang="x-default" href="{en_url}"/>\n'
        for alt_lang in LANGUAGES:
            alts += f'    <xhtml:link rel="alternate" hreflang="{alt_lang}" href="{BASE_URL}/{alt_lang}/{path}"/>\n'
        blocks.append(
            f"  <url>\n"
            f"    <loc>{lang_url}</loc>\n"
            f"{alts}"
            f"    <lastmod>{lastmod_str}</lastmod>\n"
            f"    <changefreq>{changefreq}</changefreq>\n"
            f"    <priority>{priority}</priority>\n"
            f"  </url>"
        )
    return "\n".join(blocks)


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

    today_str = timezone.now().strftime("%Y-%m-%d")

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<?xml-stylesheet type="text/xsl" href="/sitemap.xsl"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"',
        '        xmlns:xhtml="http://www.w3.org/1999/xhtml">',
        "",
    ]

    lines.append("  <!-- Brand pages -->")
    for c in brands:
        lines.append(url_block(c.slug, today_str, "weekly", "0.7"))
        lines.append("")

    lines.append("  <!-- Product pages -->")
    for p in products:
        lastmod = p.updated_at.strftime("%Y-%m-%d") if p.updated_at else today_str
        lines.append(url_block(f"{p.category.slug}/{p.slug}", lastmod, "monthly", "0.6"))
        lines.append("")

    lines.append("</urlset>")

    output = "\n".join(lines) + "\n"
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(output, encoding="utf-8")

    print(f"{len(products)} products + {len(brands)} brands × {len(LANGUAGES)} languages → {OUTPUT_PATH}")


if __name__ == "__main__":
    build()
