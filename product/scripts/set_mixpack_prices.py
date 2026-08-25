#!/usr/bin/env python
# scripts/set_mixpack_prices.py
# Racuna realnu cenu mix pack / bundle proizvoda na osnovu STVARNIH cena komponenti
# (Product.price, ucitanih npr. preko load_brand_prices.py) x kolicina, uz popust na bundle.
#
# Cena bundle-a = sum(component.price * quantity za svaku mix_lines liniju) * (1 - discount/100)
#
# Upotreba:
#   python product/scripts/set_mixpack_prices.py --dry-run
#   python product/scripts/set_mixpack_prices.py --discount 10
#   python product/scripts/set_mixpack_prices.py --discount 15 --dry-run

import argparse
import os
import sys
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path


def print_table(rows):
    headers = ("SLUG", "NAZIV", "KOMPONENTI", "ZBIR (bez popusta)", "POPUST", "NOVA CENA")
    widths = [len(h) for h in headers]
    for r in rows:
        widths[0] = max(widths[0], len(r["slug"]))
        widths[1] = max(widths[1], len(r["name"]))
        widths[2] = max(widths[2], len(r["components"]))
        widths[3] = max(widths[3], len(r["subtotal_str"]))
        widths[4] = max(widths[4], len(r["discount_str"]))
        widths[5] = max(widths[5], len(r["price_str"]))

    def line(char="-"):
        return "+" + "+".join(char * (w + 2) for w in widths) + "+"

    def fmt_row(values):
        cells = [f" {v.ljust(widths[i])} " for i, v in enumerate(values)]
        return "|" + "|".join(cells) + "|"

    print(line("="))
    print(fmt_row(headers))
    print(line("="))
    for r in rows:
        print(fmt_row([r["slug"], r["name"], r["components"], r["subtotal_str"], r["discount_str"], r["price_str"]]))
    print(line("-"))


def main():
    parser = argparse.ArgumentParser(description="Izracunaj realne cene mix pack proizvoda na osnovu cena komponenti.")
    parser.add_argument("--discount", type=str, default="10",
                         help="Procenat popusta na zbir cena komponenti (podrazumevano: 10)")
    parser.add_argument("--dry-run", action="store_true",
                         help="Samo ispisi sta bi se promenilo, bez upisa u bazu")
    args = parser.parse_args()

    discount_pct = Decimal(args.discount)

    BASE_DIR = Path(__file__).resolve().parent.parent.parent
    sys.path.insert(0, str(BASE_DIR))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings")
    import django
    django.setup()

    from product.models import Product

    mix_products = (
        Product._base_manager
        .filter(mix_lines__isnull=False)
        .distinct()
        .prefetch_related("mix_lines__component_product")
    )

    if not mix_products.exists():
        print("ℹ️  Nema mix pack proizvoda u bazi (nijedan Product nema mix_lines). Ništa za uraditi.")
        print("   Mix pack-ovi se dodaju preko import_mixpacks_from_yaml.py + templates/mixpacks.yaml.")
        return

    report = []
    warnings = []
    total_updated = 0

    for product in mix_products:
        lines = list(product.mix_lines.all())
        subtotal = Decimal("0.00")
        component_parts = []
        missing_price = False

        for line in lines:
            comp = line.component_product
            comp_price = comp.price.amount if comp.price else None
            component_parts.append(f"{line.quantity}×{comp.slug}")
            if comp_price is None:
                missing_price = True
                warnings.append(f"Komponenta '{comp.slug}' u bundle-u '{product.slug}' nema cenu (price=None) - preskočen bundle.")
                continue
            subtotal += comp_price * line.quantity

        if missing_price:
            report.append({
                "slug": product.slug, "name": product.name,
                "components": ", ".join(component_parts),
                "subtotal_str": "?", "discount_str": "-", "price_str": "PRESKOČENO",
            })
            continue

        final_price = (subtotal * (Decimal("1") - discount_pct / Decimal("100"))).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

        if not args.dry_run:
            product.price = final_price
            product.save(update_fields=["price"])
            total_updated += 1

        report.append({
            "slug": product.slug, "name": product.name,
            "components": ", ".join(component_parts),
            "subtotal_str": f"{subtotal} EUR",
            "discount_str": f"{discount_pct}%",
            "price_str": f"{final_price} EUR",
        })

    print(f"\n{'DRY RUN — ništa nije upisano u bazu' if args.dry_run else 'AŽURIRANJE CENA MIX PACK PROIZVODA'}\n")
    print_table(report)

    if warnings:
        print(f"\n⚠️  UPOZORENJA ({len(warnings)}):")
        for w in warnings:
            print(f"   - {w}")

    print("\nRezime:")
    print(f"   Mix pack proizvoda obrađeno: {len(report)}")
    print(f"   Ažurirano: {total_updated if not args.dry_run else 0}")
    print(f"   Preskočeno (nedostaje cena komponente): {sum(1 for r in report if r['price_str'] == 'PRESKOČENO')}")

    print("\n✅ Gotovo." if not args.dry_run else "\n✅ Dry-run gotov, ništa nije upisano.")


if __name__ == "__main__":
    main()
