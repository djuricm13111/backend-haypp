import json
from django.utils.text import slugify
from product.models import Category, Product, ProductImage, CategoryImage, ProductSEO, CategorySEO
from djmoney.models.fields import MoneyField
from django.core.exceptions import ValidationError
from scripts.gs_orders import add_products_to_google_sheet
from scripts.data.domain_mapping import domain_mapping
from scripts.data.sitemap import generate_sitemap
from django.db import transaction
#exec (open('scripts/data/import_products.py').read()) #aktiviranje skripte za upis u BP

DEFAULT_PRICE = 5.00  # Pretpostavljena cena, prilagodite po potrebi
BASE_IMAGE_URL = "https://snus-s3.s3.eu-north-1.amazonaws.com/products/"
BASE_CATEGORY_IMAGE_URL_DESKTOP = "https://snus-s3.s3.eu-north-1.amazonaws.com/categories/desktop/"
BASE_CATEGORY_IMAGE_URL_MOBILE = "https://snus-s3.s3.eu-north-1.amazonaws.com/categories/mobile/"

#LANG_CODES = ['en_us', 'de']
# LANG_CODES = ['en_us', 'de', 'it', 'fr', 'hu', 'tr', 'sr_latn']
# DEFAULT_LANG = "en_us"
# DOMAIN  = "snusco.com"

def import_products(DOMAIN, LANG_CODES, DEFAULT_LANG):
    print(f"DATA FOR {DOMAIN}")

    # Obriši sve SEO podatke za dati domen
    with transaction.atomic():
        deleted_count, _ = ProductSEO.objects.filter(domain=DOMAIN).delete()
        print(f"Obrisano {deleted_count} SEO zapisa za {DOMAIN}")
    

    # Učitajte JSON podatke
    with open(f'scripts/data/products.json', 'r') as file:  # Zamenite 'path_to_your_json_file.json' sa stvarnom putanjom
        products_data = json.load(file)
    with open(f'scripts/data/{DOMAIN}/seo.json', 'r') as file:
        seo_data = json.load(file)

    # Mapirajte SEO podatke prema ID-u za brzo povezivanje
    seo_data_by_id = {seo['id']: seo for seo in seo_data}

    # Iterirajte kroz svaki proizvod i kreirajte/ažurirajte ih u bazi podataka
    for product_data in products_data:

        seo = seo_data_by_id.get(product_data['id'], {})
        
        
        # Pronađite kategoriju na osnovu imena ili kreirajte novu ako ne postoji
        category_name = product_data['category']
        category_slug = slugify(category_name)
        category_title_texts = {
            'en_us': f"{category_name} {product_data['title']}- Buy Now | {DOMAIN}",
            'de': f"{category_name} - Jetzt kaufen | {DOMAIN}",
            'fr': f"{category_name} - Achetez maintenant | {DOMAIN}",
            'it': f"{category_name} - Acquista ora | {DOMAIN}",
            'sr_latn': f"{category_name} - Kupi sada | {DOMAIN}",
        }

        category_og_title_texts = {
            'en_us': f"Discover {category_name} - Limited Offer!",
            'de': f"Entdecken Sie {category_name} - Begrenztes Angebot!",
            'fr': f"Découvrez {category_name} - Offre limitée!",
            'it': f"Scopri {category_name} - Offerta limitata!",
            'sr_latn': f"Otkrijte {category_name} - Ograničena ponuda!",
        }
        try:
            category = Category.objects.get(slug=category_slug)
        except Category.DoesNotExist:
            print(f"Nema Kategorije - {category_slug}")
            continue

        # Kreirajte ili ažurirajte proizvod
        product, created = Product.objects.all_including_deleted().update_or_create(
            id=product_data['id'],
            defaults={
                'category': category,
                'name': product_data['title'],
                'nicotine': product_data['nicotine'],
                'price': DEFAULT_PRICE,
                #'description': product_data.get('description_en', ''),
                #'short_description': product_data.get('short_description_en', ''),
                'recommended': False,
                'state': 'IN_STOCK',
                'pouches_per_can': product_data.get('pouches_per_can', None),
                'format': product_data.get('format', None),
                'flavor': product_data.get('flavor', None),
                'net_weight': product_data.get('net_weight', None),
                'manufacturer': product_data.get('manufacturer', None),
                'sku': product_data.get('sku', None)

            }
        )

        # if created:
        #     print(f'Kreiran je novi proizvod:{category_slug} {product.name}')
        # else:
        #     print(f'Ažuriran je proizvod:{category_slug} {product.name}')

        # **Obriši postojeće slike za proizvod**
        ProductImage.objects.filter(product=product).delete()
        # Handle images if present
        if 'images' in product_data:
                category_path = f"{category_name.lower().replace(' ', '_')}/"
                for img_data in product_data['images']:
                    full_image_url = f"{BASE_IMAGE_URL}{category_path}{img_data['image_url']}"
                    ProductImage.objects.update_or_create(
                        product=product,
                        original_image_key=full_image_url,
                        defaults={
                            'is_primary': img_data['is_primary']
                        }
                    )

        seo_entry = next((entry for entry in seo_data if entry['id'] == product_data['id']), None)
        
        if not seo_entry:
            #print(f"SEO podaci za proizvod sa ID {product_data['id']} nisu pronađeni.")
            continue

        title_texts = {
            'en_us': f"{category_name} {product.name} - Buy Now | {DOMAIN}",
            'de': f"{category_name} {product.name} - Jetzt kaufen | {DOMAIN}",
            'fr': f"{category_name} {product.name} - Achetez maintenant | {DOMAIN}",
            'it': f"{category_name} {product.name} - Acquista ora | {DOMAIN}",
            'sr_latn': f"{category_name} {product.name} - Kupi sada | {DOMAIN}",
        }

        og_title_texts = {
            'en_us': f"Try {product.name} in {category_name} - Limited Offer!",
            'de': f"Versuchen Sie {product.name} in {category_name} - Begrenztes Angebot!",
            'fr': f"Essayez {product.name} dans {category_name} - Offre limitée!",
            'it': f"Prova {product.name} in {category_name} - Offerta limitata!",
            'sr_latn': f"Pokušajte {product.name} u {category_name} - Ograničena ponuda!",
        }
        # Definišite zajedničke SEO podatke koji se unose samo jednom
        seo_defaults = {
            'meta_keywords': f"{category_name}, {product.name}, {product.flavor}, {product.manufacturer}",
            
        }

        # Postavi OG sliku ako postoji primarna slika (ovo radimo samo jednom)
        primary_image = ProductImage.objects.filter(product=product, is_primary=True).first()
        if primary_image:
            seo_defaults['og_image'] = primary_image.get_large_image_url()

        # Kreirajte ili ažurirajte SEO podatke samo za jezike
        for lang_code in LANG_CODES:
            description_key = f'description_{lang_code}'
            short_description_key = f'short_description_{lang_code}'

            # Pripremite podatke za SEO
            seo_title = title_texts.get(lang_code, title_texts[DEFAULT_LANG])
            seo_og_title = og_title_texts.get(lang_code, og_title_texts[DEFAULT_LANG])


            seo_description = seo_entry[description_key]
            seo_short_description = seo_entry[short_description_key]

            # Generisanje meta i OG opisa
            meta_description = f"{seo_description[:157]}..." if len(seo_description) > 160 else seo_description
            og_description = f"{seo_description[:297]}..." if len(seo_description) > 300 else seo_description


            # Kreirajte ili ažurirajte SEO podatke za proizvod
            seo_entryy, seo_created = ProductSEO.objects.update_or_create(
                product=product,
                domain=DOMAIN,
                defaults={
                    **seo_defaults,
                    f'title_{lang_code}': seo_title,
                    f'meta_description_{lang_code}': meta_description,
                    f'og_title_{lang_code}': seo_og_title,
                    f'og_description_{lang_code}': og_description,
                    f'description_{lang_code}': seo_description,
                    f'short_description_{lang_code}': seo_short_description,
                }
            )

            if seo_created:
                print(f"Kreirani SEO podaci za proizvod {product.name} na jeziku {lang_code}")
            else:
                print(f"Ažurirani SEO podaci za proizvod {product.name} na jeziku {lang_code}")

    print("import_products završena.")