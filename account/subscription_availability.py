"""Provera da li se pretplatnički proizvodi mogu automatski naručiti (stanje + zaliha)."""

from datetime import timedelta

from django.utils import timezone

from product.models import Product, ProductState

# Koliko dana odložiti sledeći pokušaj kada nešto nije dostupno
SUBSCRIPTION_OOS_RETRY_DAYS = 7


def is_product_available_for_subscription_order(product: Product, quantity: int) -> bool:
    """Automatska pretplatna isporuka: samo aktivni proizvod, na stanju, dovoljno komada."""
    if product.is_deleted:
        return False
    if product.state != ProductState.IN_STOCK:
        return False
    if product.stock < quantity:
        return False
    return True


def get_unavailable_subscription_items(subscription):
    """
    Vraća listu stavki koje trenutno ne mogu da se automatski naruče.
    Svaka stavka: {product_name, quantity}.
    """
    bad = []
    for item in subscription.items.select_related("product", "product__category"):
        p = item.product
        if not is_product_available_for_subscription_order(p, item.quantity):
            cat = getattr(p.category, "name", None) or ""
            name = f"{cat} {p.name}".strip() if cat else p.name
            bad.append({"product_name": name, "quantity": item.quantity})
    return bad


def bump_next_order_after_oos(subscription):
    """Pomeri sledeći pokušaj za SUBSCRIPTION_OOS_RETRY_DAYS dana od sada."""
    subscription.next_order_at = timezone.now() + timedelta(
        days=SUBSCRIPTION_OOS_RETRY_DAYS
    )
    subscription.save(update_fields=["next_order_at", "updated_at"])
