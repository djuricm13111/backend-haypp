# Generated manually — vezuje sve pretplate kreirane na checkout-u sa istom porudžbinom (email / izveštaji).

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("account", "0008_remove_cancelled_product_subscriptions"),
    ]

    operations = [
        migrations.AddField(
            model_name="productsubscription",
            name="checkout_order",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="checkout_subscriptions",
                to="account.order",
            ),
        ),
    ]
