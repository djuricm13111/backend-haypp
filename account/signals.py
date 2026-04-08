from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from .models import Order, OrderStatus
from backend.settings import USE_POINTS, DEFAULT_DOMAIN

@receiver(pre_save, sender=Order)
def handle_order_status_change(sender, instance, **kwargs):
    if instance.pk:
        previous_order = Order.objects.get(pk=instance.pk)
        if previous_order.order_status != instance.order_status and (instance.domain or DEFAULT_DOMAIN) in USE_POINTS:
            if instance.order_status == OrderStatus.DELIVERED and not instance.added_points:
                instance.complete_order()
            elif instance.order_status != OrderStatus.DELIVERED and instance.added_points:
                instance.revoke_points()