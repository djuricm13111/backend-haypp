import os
import django
from decimal import Decimal
from django.core.exceptions import ObjectDoesNotExist
from product.models import Product, Category


#exec (open('scripts/data/update_prices.py').read()) #aktiviranje skripte za upis u BP

# Postavljanje Django okruženja
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'your_project.settings')
django.setup()

def update_prices_by_brand(brand_slug, new_price_eur):
    """Ažurira cene svih proizvoda u kategoriji na osnovu slug-a."""
    try:
        # Pronalazi kategoriju na osnovu slug-a
        brand = Category.objects.get(slug=brand_slug)
        
        # Pronalazi sve proizvode povezane sa ovom kategorijom
        products = Product.objects.filter(category=brand)

        # Ažurira cenu za svaki proizvod
        for product in products:
            product.price = Decimal(new_price_eur)  # Ažuriranje cene u EUR
            product.save()  # Čuva izmene u bazi
        
        print(f'Cene za kategoriju "{brand.name}" ažurirane na {new_price_eur} EUR.')

    except ObjectDoesNotExist:
        print(f'Kategorija sa slug-om "{brand_slug}" ne postoji.')
    except Exception as e:
        print(f'Došlo je do greške: {e}')

def get_product_by_slug(product_slug):
    """Pronalazi proizvod na osnovu slug-a."""
    try:
        product = Product.objects.get(slug=product_slug)
        return product
    except Product.DoesNotExist:
        print(f'Proizvod sa slug-om "{product_slug}" ne postoji.')
        return None

def update_all_prices():
    """Ažuriranje cena za više brendova."""
    # Definišite cene za različite brendove
    brands_prices = {
        'velo': 4.79,
        'zyn': 4.99,
        'lyft': 4.99,
        'ace': 4.88,  # Uklonjen duplikat
        'skruf': 4.69,
        '77': 4.58,
        'xqs': 4.79
    }

    # Iteracija kroz sve brendove i ažuriranje cena
    for slug, price in brands_prices.items():
        update_prices_by_brand(slug, price)


# Glavna funkcija za pokretanje
if __name__ == "__main__":
    update_all_prices()
    print("Ažuriranje cena završeno.")