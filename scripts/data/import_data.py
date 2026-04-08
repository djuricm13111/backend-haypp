import json
from django.utils.text import slugify
from product.models import Category, Product, ProductImage, CategoryImage, ProductSEO, CategorySEO
from djmoney.models.fields import MoneyField
from django.core.exceptions import ValidationError
from scripts.gs_orders import add_products_to_google_sheet
from scripts.data.import_products import import_products
from scripts.data.domain_mapping import domain_mapping
from scripts.data.sitemap import generate_sitemap
from scripts.data.update_prices import update_all_prices
from decimal import Decimal

#exec (open('scripts/data/import_data.py').read()) #aktiviranje skripte za upis u BP


DEFAULT_PRICE = 5.00  # Pretpostavljena cena, prilagodite po potrebi
BASE_IMAGE_URL = "https://snus-s3.s3.eu-north-1.amazonaws.com/products/"
BASE_CATEGORY_IMAGE_URL_DESKTOP = "https://snus-s3.s3.eu-north-1.amazonaws.com/categories/desktop/"
BASE_CATEGORY_IMAGE_URL_MOBILE = "https://snus-s3.s3.eu-north-1.amazonaws.com/categories/mobile/"

#LANG_CODES = ['en_us', 'de', 'it', 'fr', 'hu', 'tr', 'sr_latn']
LANG_CODES = ['en_us', 'de']
DEFAULT_LANG = "en_us"
DOMAIN  = "snus-oesterreich.at"
SHOP_URL = "snus-verkauf"
MAX_NICOTINE = Decimal("2000.0")
#DOMAIN = "snusdeutschland.de"
print(f"DATA FOR {DOMAIN}")

# Učitajte JSON podatke

with open(f'scripts/data/{DOMAIN}/categories.json', 'r') as file:
    categories_data = json.load(file)
    
for category_data in categories_data:
    slug = slugify(category_data['name'])
    
    if not slug:
        print(f"Category {category_data['name']} is missing a slug.")
        continue

    # Attempt to fetch the existing category by slug
    try:
        category = Category.objects.get(slug=slug)
        created = False
    except Category.DoesNotExist:
        category = Category(slug=slug)
        created = True

    # Update category fields
    category.name = category_data['name']
    category.manufacturer = category_data.get('manufacturer', None)
    category.color = category_data.get('color', None)
    

    
    try:
        category.save()
    except ValidationError as e:
        print(f"Validation error for category {category.name}: {e}")
        continue

    if created:
        print(f'Created new category: {category.name}')
    else:
        print(f'Updated category: {category.name}')

    # **Obriši postojeće slike za kategoriju**
    CategoryImage.objects.filter(category=category).delete()
    # Handle images if present
    if 'image' in category_data:
        desktop_url = f"{BASE_CATEGORY_IMAGE_URL_DESKTOP}{category_data['image']}"
        mobile_url = f"{BASE_CATEGORY_IMAGE_URL_MOBILE}{category_data['image']}"
        CategoryImage.objects.update_or_create(
            category=category,
            defaults={
                'desktop_image_key': desktop_url,
                'mobile_image_key': mobile_url,
            }
        )
    # For Category SEO
    category_title_texts = {
        'en_us': f"{category.name} - Buy Now | {DOMAIN}",
        'de': f"{category.name} - Jetzt kaufen | {DOMAIN}",
        'fr': f"{category.name} - Achetez maintenant | {DOMAIN}",
        'it': f"{category.name} - Acquista ora | {DOMAIN}",
        'sr_latn': f"{category.name} - Kupi sada | {DOMAIN}",
    }

    category_og_title_texts = {
        'en_us': f"Discover {category.name} - Limited Offer!",
        'de': f"Entdecken Sie {category.name} - Begrenztes Angebot!",
        'fr': f"Découvrez {category.name} - Offre limitée!",
        'it': f"Scopri {category.name} - Offerta limitata!",
        'sr_latn': f"Otkrijte {category.name} - Ograničena ponuda!",
    }

    category_seo_defaults = {
        'meta_keywords': f"{category.name}, {category.name} products",
    }
    for lang_code in LANG_CODES:
        description_key = f'description_{lang_code}'
        short_description_key = f'short_description_{lang_code}'

        # Prepare the title and OG title texts
        title = category_title_texts.get(lang_code, category_title_texts[DEFAULT_LANG])
        og_title = category_og_title_texts.get(lang_code, category_og_title_texts[DEFAULT_LANG])

        # Use `update_or_create` to ensure fields are updated for each language
        category_seo_data, category_seo_created = CategorySEO.objects.update_or_create(
            category=category,
            domain=DOMAIN,
            defaults={
                **category_seo_defaults,
                # Save fields specific to the language using the language code as a suffix
                f'description_{lang_code}': category_data.get(description_key, ''),
                f'short_description_{lang_code}': category_data.get(short_description_key, ''),
                f'title_{lang_code}': title,
                f'meta_description_{lang_code}': f"{category_data.get(description_key, '')[:157]}..." if len(category_data.get(description_key, '')) > 160 else category_data.get(description_key, ''),
                f'og_title_{lang_code}': og_title,
                f'og_description_{lang_code}': f"{category_data.get(description_key, '')[:297]}..." if len(category_data.get(description_key, '')) > 300 else category_data.get(description_key, ''),
            }
        )

        # Save the updated or newly created SEO data
        category_seo_data.save()


import_products(DOMAIN, LANG_CODES, DEFAULT_LANG)

domain_mapping(DOMAIN, MAX_NICOTINE)

generate_sitemap(DOMAIN, SHOP_URL, LANG_CODES)

update_all_prices()

 

#add_products_to_google_sheet(products_data)
