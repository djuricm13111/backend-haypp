# Generated manually for OrderItem shipping flags

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('account', '0004_order_customer_order_id'),
    ]

    operations = [
        migrations.AddField(
            model_name='orderitem',
            name='is_shipped',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='orderitem',
            name='shipped_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
