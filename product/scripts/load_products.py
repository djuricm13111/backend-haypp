import gspread
from oauth2client.service_account import ServiceAccountCredentials

# Putanja do tvoje JSON autorizacije
CREDENTIALS_FILE = 'snusco-gs-credentials.json'




def load_gs_products(sheet_name = 'Products', spreadsheet_url="https://docs.google.com/spreadsheets/d/1aDjxdxoAUE5qH7rwRYo8Rlt0xwf9LZXjy6f88BolXYg/edit#gid=825473178"):
    # Postavi opseg pristupa
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    
    # Učitaj kredencijale
    creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_FILE, scope)
    client = gspread.authorize(creds)

    # Otvori spreadsheet i sheet po imenu
    sheet = client.open_by_url(spreadsheet_url).worksheet(sheet_name)

    # Učitaj sve podatke kao listu rečnika
    data = sheet.get_all_records()
    
    print(f"✅ Učitano {len(data)} redova iz Sheets-a.")
    return data

# if __name__ == "__main__":
#     products = load_products()
#     for p in products:
#         print(p)
