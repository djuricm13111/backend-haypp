YAML import običnih proizvoda (bez bundle / MixPackLine)
=======================================================

Skripta: backend/product/scripts/import_products_from_yaml.py

- Ista struktura stavki kao u mixpacks.example.yaml (name, slug, brand, cena, slike…).
- Polja mix_components / bundle_components se ignorišu — za bundle koristi import_mixpacks_from_yaml.py.

Komande (iz backend/):

  python product/scripts/import_products_from_yaml.py --dry-run
  python product/scripts/import_products_from_yaml.py
  python product/scripts/import_products_from_yaml.py --file /putanja/do/liste.yaml

Podrazumevani fajl: product/scripts/templates/products.yaml
