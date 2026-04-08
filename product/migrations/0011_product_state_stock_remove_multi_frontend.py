# Generated manually: single storefront — state/stock on Product; drop Frontend / ProductAvailability

from django.db import migrations, models


def copy_availability_to_product(apps, schema_editor):
    Product = apps.get_model('product', 'Product')
    PA = apps.get_model('product', 'ProductAvailability')
    Frontend = apps.get_model('product', 'Frontend')
    sr = None
    try:
        sr = Frontend.objects.get(slug='sr')
    except Frontend.DoesNotExist:
        pass
    for p in Product.objects.all():
        pa = None
        if sr is not None:
            try:
                pa = PA.objects.get(product_id=p.pk, frontend_id=sr.id)
            except PA.DoesNotExist:
                pass
        if pa is None:
            pa = PA.objects.filter(product_id=p.pk).first()
        if pa is not None:
            p.state = pa.state
            p.stock = pa.stock
            p.save(update_fields=['state', 'stock'])


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('product', '0010_alter_productseo_unique_together_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='state',
            field=models.CharField(
                choices=[
                    ('in_stock', 'Na stanju'),
                    ('on_request', 'Dostupno na upit'),
                    ('out_of_stock', 'Nema na stanju'),
                ],
                default='in_stock',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='product',
            name='stock',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.RunPython(copy_availability_to_product, noop_reverse),
        migrations.DeleteModel(
            name='ProductAvailability',
        ),
        migrations.DeleteModel(
            name='Frontend',
        ),
    ]
