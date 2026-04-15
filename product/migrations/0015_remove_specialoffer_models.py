from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("product", "0014_mixpackline"),
        ("account", "0010_remove_orderitem_special_offer"),
    ]

    operations = [
        migrations.DeleteModel(
            name="SpecialOfferImage",
        ),
        migrations.DeleteModel(
            name="SpecialOffer",
        ),
    ]
