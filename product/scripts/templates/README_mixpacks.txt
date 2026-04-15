Mix pack proizvodi (YAML + import skripta)
==========================================

1) Uredi templates/mixpacks.yaml (ili svoj fajl sa --file).

2) Mix pack u bazi:
   - Product red kao i običan proizvod (name, slug, cena, slike…).
   - mix_components: lista { slug, quantity } — slug mora već postojati u bazi.
   - Stanje bundle-a: svi sastojci moraju biti in_stock; broj bundle-a =
     minimum od (stock_komponente // quantity) po svakoj liniji.
   - Nakon importa i nakon update_stock_from_gs.py stanje mix pack-a se osvežava.

3) Provera pre upisa:
   cd backend
   python product/scripts/import_mixpacks_from_yaml.py --dry-run

4) Upis:
   python product/scripts/import_mixpacks_from_yaml.py

5) Ako u YAML-u nema ključa mix_components / bundle_components, postojeće
   MixPackLine zapise u bazi za taj slug skripta NE menja.

Skripta: backend/product/scripts/import_mixpacks_from_yaml.py

Obični proizvodi (bez mix linija): import_products_from_yaml.py + templates/products.yaml
(vidi templates/README_products_yaml.txt).
