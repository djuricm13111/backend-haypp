# Generated manually — drops the retired "Post - AT" transport method choice.
# (Kept minimal: makemigrations also wanted to regenerate every CurrencyField's
# choices list due to an unrelated django-money version drift — not related to
# this change, so left alone rather than bundled in here.)

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('account', '0011_alter_productsubscription_checkout_order'),
    ]

    operations = [
        migrations.AlterField(
            model_name='order',
            name='transport_method',
            field=models.CharField(
                choices=[('DHL Standard', 'DHL Standard'), ('DHL Express Saver', 'DHL Express Saver')],
                default='DHL Standard',
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name='productsubscription',
            name='transport_method',
            field=models.CharField(
                choices=[('DHL Standard', 'DHL Standard'), ('DHL Express Saver', 'DHL Express Saver')],
                default='DHL Standard',
                max_length=20,
            ),
        ),
    ]
