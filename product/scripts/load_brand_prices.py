#!/usr/bin/env python
# scripts/load_brand_prices.py
# Ucitava osnovne (najvise) cene po brendu iz brand_prices_eu.csv i azurira Product.price.
# Ovo su cene "od" - popusti na kolicinu se primenjuju posebno preko korpe/frontenda.
#
# Upotreba:
#   python product/scripts/load_brand_prices.py                  # upisuje u bazu
#   python product/scripts/load_brand_prices.py --dry-run         # samo ispise sta bi se promenilo
#   python product/scripts/load_brand_prices.py --default 4.50    # drugacija podrazumevana cena

import argparse
import csv
import os
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path

CSV_PATH = Path(__file__).resolve().parent / "brand_prices_eu.csv"

STATUS_LABELS = {
    "ok": "OK",
    "default": "DEFAULT (nema cene u CSV-u)",
    "no_category": "NEMA KATEGORIJE U BAZI",
    "no_csv_row": "NEMA U CSV-u (DEFAULT)",
    "invalid": "NEISPRAVNA CENA",
}


def print_table(rows):
    headers = ("SLUG", "BREND", "PROIZVODA", "CENA (EUR)", "STATUS")
    widths = [len(h) for h in headers]
    for r in rows:
        widths[0] = max(widths[0], len(r["slug"]))
        widths[1] = max(widths[1], len(r["brand_name"]))
        widths[2] = max(widths[2], len(str(r["count"])))
        widths[3] = max(widths[3], len(r["price_str"]))
        widths[4] = max(widths[4], len(r["status_label"]))

    def line(char="-"):
        return "+" + "+".join(char * (w + 2) for w in widths) + "+"

    def fmt_row(values):
        cells = [f" {v.ljust(widths[i])} " for i, v in enumerate(values)]
        return "|" + "|".join(cells) + "|"

    print(line("="))
    print(fmt_row(headers))
    print(line("="))
    for r in rows:
        print(fmt_row([r["slug"], r["brand_name"], str(r["count"]), r["price_str"], r["status_label"]]))
    print(line("-"))


def main():
    parser = argparse.ArgumentParser(description="Ucitaj cene po brendu iz CSV-a.")
    parser.add_argument("--default", type=str, default="4.78",
                         help="Podrazumevana cena (EUR) za brendove bez pronadjenih podataka")
    parser.add_argument("--dry-run", action="store_true",
                         help="Samo ispisi sta bi se promenilo, bez upisa u bazu")
    args = parser.parse_args()

    default_price = Decimal(args.default)

    BASE_DIR = Path(__file__).resolve().parent.parent.parent
    sys.path.insert(0, str(BASE_DIR))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings")
    import django
    django.setup()

    from product.models import Category, Product

    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    seen_slugs = set()
    report = []
    warnings = []
    total_updated_products = 0

    for row in rows:
        slug = row["slug"].strip()
        brand_name = row.get("brand_name", "").strip() or slug
        seen_slugs.add(slug)
        raw_price = row.get("price_eur", "").strip()

        if raw_price:
            try:
                price = Decimal(raw_price)
                status = "ok"
            except InvalidOperation:
                warnings.append(f"Neispravna cena '{raw_price}' za '{slug}' (brend: {brand_name}) - preskočeno.")
                report.append({"slug": slug, "brand_name": brand_name, "count": 0,
                                "price_str": raw_price, "status_label": STATUS_LABELS["invalid"]})
                continue
        else:
            price = default_price
            status = "default"
            warnings.append(f"Nema pronađene cene za brend '{brand_name}' ({slug}) - koristi se podrazumevana cena {default_price} EUR.")

        try:
            category = Category.objects.get(slug=slug)
        except Category.DoesNotExist:
            warnings.append(f"Kategorija za '{slug}' (brend: {brand_name}) ne postoji u bazi - preskočeno.")
            report.append({"slug": slug, "brand_name": brand_name, "count": 0,
                            "price_str": f"{price} EUR", "status_label": STATUS_LABELS["no_category"]})
            continue

        products = Product.objects.filter(category=category)
        count = products.count()

        if not args.dry_run:
            products.update(price=price)

        total_updated_products += count
        report.append({"slug": slug, "brand_name": brand_name, "count": count,
                        "price_str": f"{price} EUR", "status_label": STATUS_LABELS[status]})

    # Kategorije u bazi koje nisu uopšte u CSV-u (nove/nepoznate) dobijaju default cenu
    for category in Category.objects.exclude(slug__in=seen_slugs):
        products = Product.objects.filter(category=category)
        count = products.count()
        if count == 0:
            continue

        if not args.dry_run:
            products.update(price=default_price)

        total_updated_products += count
        warnings.append(f"Kategorija '{category.slug}' ({category.name}) ne postoji u CSV-u - koristi se podrazumevana cena {default_price} EUR.")
        report.append({"slug": category.slug, "brand_name": category.name, "count": count,
                        "price_str": f"{default_price} EUR", "status_label": STATUS_LABELS["no_csv_row"]})

    print(f"\n{'DRY RUN — ništa nije upisano u bazu' if args.dry_run else 'AŽURIRANJE CENA PO BRENDU'}\n")
    print_table(report)

    if warnings:
        print(f"\n⚠️  UPOZORENJA ({len(warnings)}):")
        for w in warnings:
            print(f"   - {w}")

    print("\nRezime:")
    print(f"   Brendova obrađeno:         {len(report)}")
    print(f"   Proizvoda {'koji bi bili ažurirani' if args.dry_run else 'ažurirano'}: {total_updated_products}")
    print(f"   Sa podrazumevanom cenom:   {sum(1 for r in report if 'DEFAULT' in r['status_label'])}")
    print(f"   Preskočeno (bez kategorije/neispravno): {sum(1 for r in report if r['status_label'] in (STATUS_LABELS['no_category'], STATUS_LABELS['invalid']))}")

    print("\n✅ Gotovo." if not args.dry_run else "\n✅ Dry-run gotov, ništa nije upisano.")


if __name__ == "__main__":
    main()
