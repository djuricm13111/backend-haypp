from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from product.models import MixPackLine, Product


@receiver(post_save, sender=Product)
def refresh_mixpacks_when_component_saved(sender, instance, **kwargs):
    mix_ids = (
        MixPackLine.objects.filter(component_product_id=instance.pk)
        .values_list("mix_product_id", flat=True)
        .distinct()
    )
    for mid in mix_ids:
        p = Product._base_manager.get(pk=mid)
        p.refresh_mixpack_from_components(save=True)


@receiver(post_save, sender=MixPackLine)
def refresh_mixpack_when_line_saved(sender, instance, **kwargs):
    instance.mix_product.refresh_mixpack_from_components(save=True)


@receiver(post_delete, sender=MixPackLine)
def refresh_mixpack_when_line_deleted(sender, instance, **kwargs):
    instance.mix_product.refresh_mixpack_from_components(save=True)
