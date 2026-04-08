import gspread
from oauth2client.service_account import ServiceAccountCredentials
from django.utils.text import slugify



# Funkcija za upisivanje proizvoda u Google Sheet
def add_products_to_google_sheet(products_data):
    credentials_file = 'snusco-gs-credentials.json'
    scopes = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    
    # Prijava pomoću Google Sheets API
    credentials = ServiceAccountCredentials.from_json_keyfile_name(credentials_file, scopes)
    client = gspread.authorize(credentials)

    # ID Sheet-a
    spreadsheet_id = '1aDjxdxoAUE5qH7rwRYo8Rlt0xwf9LZXjy6f88BolXYg'
    spreadsheet = client.open_by_key(spreadsheet_id)

    # Odabir Sheet-a "Products"
    sheet = spreadsheet.worksheet('Products')

    # Sortiranje proizvoda po kategoriji
    sorted_products = sorted(products_data, key=lambda x: x['category'])

    # Priprema podataka za upis
    rows = []
    for product_data in sorted_products:
        row_data = [
            "",  # Prazna kolona
            product_data['category'],  # Kategorija
            product_data['title'],  # Ime proizvoda
            product_data.get('format', ''),  # Format
            "",  # Ostavlja Cost praznim
            "",  # Ostavlja Selling Price praznim
            product_data.get('nicotine', ''),  # MG vrednost
            slugify(f"{product_data['category']}-{product_data['title']}")  # Slug
        ]
        rows.append(row_data)

    # Upiši sve proizvode odjednom u Google Sheet
    sheet.append_rows(rows)

    print("Proizvodi su uspešno dodati i sortirani u tabelu 'Products'.")

    print("Proizvodi su uspešno dodati u tabelu 'Products'.")