import os
from datetime import datetime
from product.models import Category, Product, DomainMapping
from django.utils.text import slugify



def generate_sitemap(DOMAIN,SHOP_URL, LANG_CODES):
    """
    Generiše sitemap za proizvode i kategorije određenog domena.
    """
    SITEMAP_FILE = f"{DOMAIN}.xml"  # Naziv fajla za sitemap
    current_time = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S+00:00")

    # Početak i kraj XML strukture za sitemap
    sitemap_start = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
        'xmlns:xhtml="http://www.w3.org/1999/xhtml">\n'
    )
    sitemap_end = "</urlset>\n"

    # Brišemo postojeći fajl ako postoji
    if os.path.exists(SITEMAP_FILE):
        os.remove(SITEMAP_FILE)

    # Dohvatanje domena
    try:
        domain_mapping = DomainMapping.objects.get(domain=DOMAIN)
    except DomainMapping.DoesNotExist:
        print(f"Domen {DOMAIN} nije pronađen u bazi podataka.")
        return

    # Filtriranje proizvoda i kategorija prema domenu
    products = domain_mapping.products.all()
    categories = domain_mapping.categories.all()

    # Skupljanje URL-ova
    urls = []

    # Proizvodi
    for product in products:
        product_slug = slugify(product.name)
        category_slug = slugify(product.category.name)
        for lang in LANG_CODES:
            lang_code = lang.split('_')[0]
            product_url = f"https://www.{DOMAIN}/{lang_code}/{category_slug}-{product_slug}"
            urls.append(
                f"  <url>\n"
                f"    <loc>{product_url}</loc>\n"
                f"    <lastmod>{current_time}</lastmod>\n"
            )
            # hreflang alternate links
            for alternate_lang in LANG_CODES:
                lang_code = alternate_lang.split('_')[0]
                alternate_url = f"https://www.{DOMAIN}/{lang_code}/{category_slug}-{product_slug}"
                urls.append(
                    f"    <xhtml:link rel=\"alternate\" hreflang=\"{lang_code}\" href=\"{alternate_url}\" />\n"
                )
            urls.append("  </url>\n")

    # Kategorije
    for category in categories:
        category_slug = slugify(category.name)
        for lang in LANG_CODES:
            lang_code = lang.split('_')[0]
            category_url = f"https://www.{DOMAIN}/{lang_code}/{SHOP_URL}/{category_slug}"
            urls.append(
                f"  <url>\n"
                f"    <loc>{category_url}</loc>\n"
                f"    <lastmod>{current_time}</lastmod>\n"
            )
            # hreflang alternate links
            for alternate_lang in LANG_CODES:
                lang_code = alternate_lang.split('_')[0]
                alternate_url = f"https://www.{DOMAIN}/{lang_code}/{SHOP_URL}/{category_slug}"
                urls.append(
                    f"    <xhtml:link rel=\"alternate\" hreflang=\"{lang_code}\" href=\"{alternate_url}\" />\n"
                )
            urls.append("  </url>\n")

    # Generisanje sadržaja sitemap-a
    sitemap_content = sitemap_start + "".join(urls) + sitemap_end

    # Provera generisanog sadržaja
    #print("Generated Sitemap Content:\n", sitemap_content)

    # Upisivanje u fajl
    with open(SITEMAP_FILE, "w", encoding="utf-8") as f:
        f.write(sitemap_content)

    print(f"Sitemap successfully written to: {SITEMAP_FILE}")

# Pokretanje generisanja sitemap-a
#generate_sitemap("snus-oesterreich.at")
