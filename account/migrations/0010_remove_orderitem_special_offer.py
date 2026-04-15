import django.db.models.deletion
from django.db import migrations, models


def delete_order_items_linked_to_special_offers(apps, schema_editor):
    OrderItem = apps.get_model("account", "OrderItem")
    OrderItem.objects.filter(special_offer_id__isnull=False).delete()


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("account", "0009_productsubscription_checkout_order"),
        ("product", "0014_mixpackline"),
    ]

    operations = [
        migrations.RunPython(
            delete_order_items_linked_to_special_offers,
            noop_reverse,
        ),
        migrations.RemoveField(
            model_name="orderitem",
            name="special_offer",
        ),
        migrations.AlterField(
            model_name="orderitem",
            name="product",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                to="product.product",
            ),
        ),
    ]
