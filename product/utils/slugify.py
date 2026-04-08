# u nekom utils fajlu, npr. backend/utils/slugify.py
import re
import unicodedata

def slugify_python(text: str) -> str:
    """
    - Normalize NFD: razdvaja dijakritičke znakove (npr. “ä” → “a” + ¨)
    - Uklanja sve kombinacione znakove (dijakritike)
    - Pretvara u lowercase
    - Sve što nije a–z ili 0–9 pretvara u crticu
    - Briše duple crtice i vodeće/završne crtice
    """
    # 1) Unicode NFD
    text = unicodedata.normalize('NFD', text)
    # 2) ukloni Combining Marks (dijakritike)
    text = re.sub(r'[\u0300-\u036f]', '', text)
    # 3) u lowercase
    text = text.lower()
    # 4) non‑alnum → “-”
    text = re.sub(r'[^a-z0-9]+', '-', text)
    # 5) skini duple crtice
    text = re.sub(r'-{2,}', '-', text)
    # 6) trim vodeće/završne
    return text.strip('-')
