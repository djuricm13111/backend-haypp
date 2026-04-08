
from decimal import Decimal
DEFAULT_CURRENCY = 'EUR'

# Pretpostavimo fiksne konverzione kurseve za primer
CONVERSION_RATES = {
    "USD": Decimal('1.00'),  # Pretpostavimo da je USD defaultna valuta
    "EUR": Decimal('0.9'),  # 1 USD = 0.85 EUR
    # Dodajte više valuta i njihove konverzione kurseve prema potrebi
}

def convert_currency(amount, from_currency, to_currency):
    """
    Konvertuje iznos iz jedne valute u drugu koristeći predefinisane konverzione kurseve.

    :param amount: Iznos novca koji treba konvertovati.
    :param from_currency: Valuta iz koje se vrši konverzija.
    :param to_currency: Valuta u koju se vrši konverzija.
    :return: Konvertovani iznos u ciljnoj valuti.
    """
    if not isinstance(amount, Decimal):
        amount = Decimal(amount)
    # Pretvara iznos u defaultnu valutu ako je potrebno
    if from_currency != "USD":
        amount_in_usd = amount / CONVERSION_RATES[from_currency]
    else:
        amount_in_usd = amount

    # Pretvara iznos iz defaultne valute u ciljnu valutu
    if to_currency != "USD":
        converted_amount = amount_in_usd * CONVERSION_RATES[to_currency]
    else:
        converted_amount = amount_in_usd

    return converted_amount
