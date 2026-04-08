# Generated manually — uklanja otkazane pretplate (više ne čuvamo neaktivne redove).

from django.db import migrations


def delete_cancelled_subscriptions(apps, schema_editor):
    ProductSubscription = apps.get_model("account", "ProductSubscription")
    ProductSubscription.objects.filter(status="cancelled").delete()


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("account", "0007_alter_order_shipping_cost_currency_and_more"),
    ]

    operations = [
        migrations.RunPython(delete_cancelled_subscriptions, noop_reverse),
    ]
