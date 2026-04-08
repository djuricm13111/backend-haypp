import os
import json
from django.utils.text import slugify
from product.models import DomainMapping, Product, Category




def domain_mapping(DOMAIN, MAX_NICOTINE):
    print(f"DATA FOR {DOMAIN}")

    # Provera da li putanje postoje pre učitavanja podataka
    products_file_path = f'scripts/data/products.json'
    categories_file_path = f'scripts/data/{DOMAIN}/categories.json'
    seo_file_path = f'scripts/data/{DOMAIN}/seo.json'

    if not os.path.exists(products_file_path) or not os.path.exists(categories_file_path) or not os.path.exists(seo_file_path):
        print("ERROR: JSON files not found. Please check the file paths.")
        exit()

    # Učitajte JSON podatke
    with open(products_file_path, 'r') as file:
        products_data = json.load(file)

    with open(categories_file_path, 'r') as file:
        categories_data = json.load(file)

    with open(seo_file_path, 'r') as file:
        seo_data = json.load(file)

    # Kreiraj mapu SEO podataka na osnovu ID-a proizvoda
    seo_map = {entry['id']: entry for entry in seo_data}
    print("seo map", len(seo_map))

    # Pronađite ili kreirajte DomainMapping za dati domen
    domain_mapping, created = DomainMapping.objects.get_or_create(domain=DOMAIN)
    if created:
        print(f"Created new DomainMapping for domain {DOMAIN}")
    else:
        print(f"Using existing DomainMapping for domain {DOMAIN}")

    # Očistite proizvode i kategorije za ovaj domain mapping
    domain_mapping.products.clear()
    domain_mapping.categories.clear()
    print(f"Cleared existing products and categories for DomainMapping {DOMAIN}")

    # Kreiraj mapu kategorija
    category_slug_map = {}
    category_product_count = {}  # Dodato za brojanje proizvoda po kategoriji

    for category_data in categories_data:
        category_slug = slugify(category_data['name'])

        if not category_slug:
            continue

        # Pronađi ili kreiraj kategoriju
        category, _ = Category.objects.get_or_create(name=category_data['name'], defaults={
            'slug': category_slug
        })

        category_slug_map[category_slug] = category
        category_product_count[category_slug] = 0  # Inicijalizacija brojanja proizvoda

    total_products = 0
    added_products = 0

    # Obrada proizvoda
    for product_data in products_data:
        category_name = product_data.get('category')
        normalized_category_slug = slugify(category_name)

        try:
            # Pretpostavi da proizvod već postoji
            product = Product.objects.get(id=product_data['id'])
        except Product.DoesNotExist:
            print(f"NE POSTOJI PROIZVOD sa ID: {product_data['id']}")
            continue

        # Provera SEO podataka
        seo_entry = seo_map.get(int(product.id))
        if not seo_entry:
            #print(f"No SEO data for product '{product_data['title']}' (ID: {product.id}). Skipping...")
            continue
        total_products += 1
        # Provera da li proizvod ispunjava kriterijum
        if product.nicotine < MAX_NICOTINE:
            added_products += 1
            category_product_count[normalized_category_slug] += 1  # Uvećaj broj proizvoda u kategoriji
            domain_mapping.products.add(product)

    # Dodaj kategorije sa proizvodima u DomainMapping
    for category_slug, count in category_product_count.items():
        if count > 0:  # Dodaj kategoriju samo ako ima proizvoda
            domain_mapping.categories.add(category_slug_map[category_slug])

    domain_mapping.save()
    print(f"Added {added_products} of {total_products} products to DomainMapping for {DOMAIN}")
    print(f"Completed processing for domain {DOMAIN}")
