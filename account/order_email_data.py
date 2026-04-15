"""Payload za send_order_confirmation_email — deljeno između OrderCreateView i pretplata."""
from collections import defaultdict, deque

from django.utils import formats

from product.models import ProductImage
from .models import OrderItem


def _subscriptions_for_order(order):
    """Sve pretplate vezane za ovu porudžbinu (više intervala); fallback na stari order.subscription."""
    subs = list(
        order.checkout_subscriptions.all()
        .prefetch_related("items")
        .order_by("id")
    )
    if subs:
        return subs
    if order.subscription_id:
        return [order.subscription]
    return []


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

    subs = _subscriptions_for_order(order)
    sub_qty_by_product = defaultdict(int)
    sub_buckets = defaultdict(deque)
    for sub in subs:
        interval = sub.interval_days
        for si in sub.items.all():
            pid = si.product_id
            q = int(si.quantity)
            sub_qty_by_product[pid] += q
            sub_buckets[pid].append((q, interval))

    order_items = list(OrderItem.objects.filter(order=order).order_by("id"))
    total_by_product = defaultdict(int)
    for item in order_items:
        if item.product_id:
            total_by_product[item.product_id] += int(item.quantity)

    reg_remaining = defaultdict(int)
    for pid, tqty in total_by_product.items():
        sq = int(sub_qty_by_product.get(pid, 0))
        reg_remaining[pid] = max(0, tqty - sq)

    products_data = []
    products_subscription = []
    products_regular = []

    def take_sub_qty_with_intervals(pid, need_qty):
        rows = []
        left = need_qty
        b = sub_buckets[pid]
        while left > 0 and b:
            bq, interval = b[0]
            take = min(left, bq)
            rows.append((take, interval))
            if take == bq:
                b.popleft()
            else:
                b[0] = (bq - take, interval)
            left -= take
        return rows

    def row_from_product_item(item, qty, is_sub_line, interval_days=None):
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
        if is_sub_line and interval_days is not None:
            product_data["subscription_interval_days"] = int(interval_days)
        return product_data

    for item in order_items:
        if not item.product_id:
            continue

        pid = item.product_id
        q = int(item.quantity)

        if not subs or sub_qty_by_product.get(pid, 0) <= 0:
            pd = row_from_product_item(item, q, False)
            products_data.append(pd)
            products_regular.append(pd)
            continue

        r = reg_remaining[pid]
        reg_take = min(r, q)
        sub_take = q - reg_take
        reg_remaining[pid] = r - reg_take

        if reg_take > 0:
            pd = row_from_product_item(item, reg_take, False)
            products_data.append(pd)
            products_regular.append(pd)
        if sub_take > 0:
            parts = take_sub_qty_with_intervals(pid, sub_take)
            allocated = sum(pq for pq, _ in parts)
            if allocated < sub_take:
                pd = row_from_product_item(item, sub_take - allocated, False)
                products_data.append(pd)
                products_regular.append(pd)
            for part_qty, int_d in parts:
                pd = row_from_product_item(item, part_qty, True, int_d)
                products_data.append(pd)
                products_subscription.append(pd)

    data["products"] = products_data
    data["products_subscription"] = products_subscription
    data["products_regular"] = products_regular

    schedules = []
    for sub in subs:
        next_at = sub.next_order_at
        schedules.append(
            {
                "interval_days": sub.interval_days,
                "next_order_at_iso": next_at.isoformat() if next_at else None,
                "next_order_at_display": (
                    formats.date_format(next_at, "SHORT_DATETIME_FORMAT")
                    if next_at
                    else ""
                ),
            }
        )
    data["subscription_schedules"] = schedules
    data["subscription"] = schedules[0] if schedules else None

    return data
