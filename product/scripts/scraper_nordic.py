import requests
from bs4 import BeautifulSoup
import re

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

# Pomoćna funkcija za generisanje sluga
def slugify(text):
    return re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-')

# Parsira listing stranicu i vraća listu proizvoda (samo osnovni podaci)
def scrape_products_from_url(base_url, limit=1000):
    products = []
    seen_slugs = set()
    page = 1
    total_collected = 0

    while total_collected < limit:
        url = f"{base_url}?page={page}"
        print(f"🌍 Učitavam: {url}")

        response = requests.get(url, headers=HEADERS)
        if response.status_code != 200:
            print("❌ Ne mogu da učitam stranicu.")
            break

        soup = BeautifulSoup(response.text, "html.parser")
        product_cards = soup.select("div.product-card")
        if not product_cards:
            break

        for card in product_cards:
            title_tag = card.select_one("div.product-card__main__title .name")
            brand_tag = card.select_one("span.brand")
            stock_tag = card.select_one("div.product-card-inventory-status")

            title = title_tag.text.strip() if title_tag else "-"
            brand = brand_tag.text.strip() if brand_tag else "-"
            stock = stock_tag.text.strip() if stock_tag else "-"

            slug = slugify(title)
            available = stock.lower() in ["in stock", "finns i lager"]

            if slug in seen_slugs:
                continue
            seen_slugs.add(slug)

            products.append({
                "title": title,
                "slug": slug,
                "brand": brand,
                "available": available
            })
            total_collected += 1

        page += 1

    return products

# Scrapuje sa oba sajta i kombinuje dostupnosti (izbegava duplikate po slugu)
def scrape_all_sources(limit=1000):
    all_products = []
    seen_slugs = set()

    sources = [
        "https://nordicpouch.com/en/categories/nicotine-pouch",
        "https://nordicpouch.se/sv/categories/vitt-tobaksfritt-snus"
    ]

    for url in sources:
        print(f"🔄 Scrapujem sa: {url}")
        products = scrape_products_from_url(url, limit=limit)
        for p in products:
            if p["slug"] not in seen_slugs:
                all_products.append(p)
                seen_slugs.add(p["slug"])
            else:
                # Ako isti slug već postoji, zadrži bar jedan izvor
                continue

    print(f"✅ Ukupno jedinstvenih proizvoda: {len(all_products)}")
    return all_products

# Glavna funkcija za dobijanje dostupnosti
def get_supplier_availability():
    print("🔍 Proveravam dostupnost proizvoda kod dobavljača (Nordic)...")
    products = scrape_all_sources()
    availability = {p["slug"]: p["available"] for p in products}
    print(f"✅ Dostupnih proizvoda: {sum(availability.values())}")
    return availability

# Ručno testiranje
if __name__ == "__main__":
    availability = get_supplier_availability()
    print(f"\n🔢 Ukupno učitano: {len(availability)} proizvoda")
