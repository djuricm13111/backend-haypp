# Generated manually for mix-pack composition.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("product", "0013_alter_product_discounted_price_currency_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="MixPackLine",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "quantity",
                    models.PositiveIntegerField(
                        default=1,
                        help_text="Koliko komada ove komponente treba za jedan bundle (npr. 10 limenki).",
                    ),
                ),
                (
                    "component_product",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="mix_used_in",
                        to="product.product",
                    ),
                ),
                (
                    "mix_product",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="mix_lines",
                        to="product.product",
                    ),
                ),
            ],
            options={
                "verbose_name": "Mix pack linija",
                "verbose_name_plural": "Mix pack linije",
            },
        ),
        migrations.AddConstraint(
            model_name="mixpackline",
            constraint=models.UniqueConstraint(
                fields=("mix_product", "component_product"),
                name="product_mixpack_unique_component",
            ),
        ),
    ]
