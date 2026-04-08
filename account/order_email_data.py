"""Payload za send_order_confirmation_email — deljeno između OrderCreateView i pretplata."""
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

    products_data = []
    for item in OrderItem.objects.filter(order=order):
        primary_image = None
        if item.product:
            primary_image = ProductImage.objects.filter(
                product=item.product, is_primary=True
            ).first()
        if item.product:
            product_data = {
                "id": item.product.id,
                "name": item.product.name,
                "category": item.product.category.name,
                "nicotine": item.product.nicotine,
                "quantity": item.quantity,
                "price": item.price.amount,
                "discounted_price": item.discounted_price.amount
                if item.discounted_price
                else None,
            }
        else:
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
        if primary_image:
            product_data["image"] = primary_image.get_image_url()
        products_data.append(product_data)

    data["products"] = products_data

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
