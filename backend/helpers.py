import json
from pathlib import Path


TEMPLATES_DIR = Path(__file__).resolve().parent / "translations"

def load_email_template(template_name, language):
    template_path = TEMPLATES_DIR / f"{template_name}.json"
    with open(template_path, 'r', encoding='utf-8') as file:
        templates = json.load(file)
    return templates.get(language, templates['en'])