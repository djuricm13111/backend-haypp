"""Kreiranje pretplata nakon uspešnog checkout-a (jedna porudžbina, ista ruta)."""
from collections import defaultdict
from datetime import timedelta

from django.utils import timezone

from backend.settings import DEFAULT_DOMAIN

from .models import ProductSubscription, SubscriptionItem, SubscriptionStatus


def create_subscriptions_from_checkout_order(order, user, rows):
    """
    rows: [{"product": int, "quantity": int, "interval_days": int}, ...]
    Grupiše po interval_days u jednu ProductSubscription po intervalu.
    Povezuje order.subscription na prvu kreiranu pretplatu (FK dozvoljava jednu).
    """
    if not rows or not order.address_id:
        return

    grouped = defaultdict(list)
    for row in rows:
        grouped[row["interval_days"]].append(row)

    first_sub = None
    for interval_days in sorted(grouped.keys()):
        items = grouped[interval_days]
        qty_by_product = defaultdict(int)
        for r in items:
            qty_by_product[r["product"]] += int(r["quantity"])
        sub = ProductSubscription(
            user=user,
            interval_days=interval_days,
            status=SubscriptionStatus.ACTIVE,
            address_id=order.address_id,
            payment_method=order.payment_method,
            transport_method=order.transport_method,
            note=order.note,
            next_order_at=timezone.now() + timedelta(days=interval_days),
            domain=DEFAULT_DOMAIN,
        )
        sub.save()
        for product_id, qty in qty_by_product.items():
            SubscriptionItem.objects.create(
                subscription=sub,
                product_id=product_id,
                quantity=qty,
            )
        if first_sub is None:
            first_sub = sub

    if first_sub:
        order.subscription = first_sub
        order.save(update_fields=["subscription"])
