"""Payload za send_order_confirmation_email — deljeno između OrderCreateView i pretplata."""
from collections import defaultdict

from django.utils import formats

from product.models import ProductImage
from .models import OrderItem


def build_order_confirmation_email_data(order):
    data = {
        "customer_email": order.user.email,
        "first_name": order.user.first_name,
        "last_name": order.user.last_name,
        "subtotal": round(order.subtotal.amount, 2),
        "shipping_cost": round(order.shipping_cost.amount, 2),
        "total_price": round(order.total_price.amount, 2),
        "currency": order.total_price.currency.code,
        "id": str(order.customer_order_id),
        "payment_method": order.get_payment_method_display(),
        "transport_method": order.get_transport_method_display(),
        "shipping_is_free": order.shipping_cost.amount == 0,
        "free_shipping_threshold_eur": 50,
    }
    if order.address:
        data["address"] = {
            "country": order.address.country,
            "city": order.address.city,
            "postal_code": order.address.postal_code,
            "street": order.address.street,
            "street_number": order.address.street_number or "",
            "secondary_street": order.address.secondary_street,
            "building_number": order.address.building_number,
            "phone_number": order.address.phone_number,
            "type": order.address.get_type_display(),
        }
    else:
        data["address"] = {}

    subscription_interval = None
    sub_qty_by_product = defaultdict(int)
    if order.subscription_id:
        subscription_interval = order.subscription.interval_days
        for si in order.subscription.items.all():
            sub_qty_by_product[si.product_id] += int(si.quantity)

    order_items = list(OrderItem.objects.filter(order=order).order_by("id"))
    total_by_product = defaultdict(int)
    for item in order_items:
        if item.product_id:
            total_by_product[item.product_id] += int(item.quantity)

    # Koliko komada po proizvodu ide kao jednokratno (ostatak od ukupno − pretplata).
    reg_remaining = defaultdict(int)
    for pid, tqty in total_by_product.items():
        sq = int(sub_qty_by_product.get(pid, 0))
        reg_remaining[pid] = max(0, tqty - sq)

    products_data = []
    products_subscription = []
    products_regular = []

    def row_from_product_item(item, qty, is_sub_line):
        primary_image = ProductImage.objects.filter(
            product=item.product, is_primary=True
        ).first()
        product_data = {
            "id": item.product.id,
            "name": item.product.name,
            "category": item.product.category.name,
            "nicotine": item.product.nicotine,
            "quantity": int(qty),
            "price": item.price.amount,
            "discounted_price": item.discounted_price.amount
            if item.discounted_price
            else None,
        }
        if primary_image:
            product_data["image"] = primary_image.get_image_url()
        product_data["is_subscription_line"] = is_sub_line
        if is_sub_line and subscription_interval is not None:
            product_data["subscription_interval_days"] = subscription_interval
        return product_data

    def row_from_special_item(item):
        primary_image = None
        product_data = {
            "id": item.special_offer.id,
            "name": item.special_offer.name,
            "category": "Special Offer",
            "quantity": item.quantity,
            "price": item.price.amount,
            "discounted_price": item.discounted_price.amount
            if item.discounted_price
            else None,
        }
        product_data["is_subscription_line"] = False
        return product_data

    for item in order_items:
        if item.special_offer_id:
            pd = row_from_special_item(item)
            products_data.append(pd)
            products_regular.append(pd)
            continue

        if not item.product_id:
            continue

        pid = item.product_id
        q = int(item.quantity)

        # Bez pretplate ili proizvod nije u pretplati — sve jednokratno.
        if not order.subscription_id or sub_qty_by_product.get(pid, 0) <= 0:
            pd = row_from_product_item(item, q, False)
            products_data.append(pd)
            products_regular.append(pd)
            continue

        # Prvo se „potroši“ jednokratni kvota po redosledu stavki (order_by id),
        # kao redosled u order_items sa fronta (obično prvo korpa bez pretplate).
        r = reg_remaining[pid]
        reg_take = min(r, q)
        sub_take = q - reg_take
        reg_remaining[pid] = r - reg_take

        if reg_take > 0:
            pd = row_from_product_item(item, reg_take, False)
            products_data.append(pd)
            products_regular.append(pd)
        if sub_take > 0:
            pd = row_from_product_item(item, sub_take, True)
            products_data.append(pd)
            products_subscription.append(pd)

    data["products"] = products_data
    data["products_subscription"] = products_subscription
    data["products_regular"] = products_regular

    data["subscription"] = None
    if order.subscription_id:
        sub = order.subscription
        next_at = sub.next_order_at
        data["subscription"] = {
            "interval_days": sub.interval_days,
            "next_order_at_iso": next_at.isoformat() if next_at else None,
            "next_order_at_display": (
                formats.date_format(next_at, "SHORT_DATETIME_FORMAT") if next_at else ""
            ),
        }

    return data
