from rest_framework.request import Request
from django.test import RequestFactory

from .serializers import OrderSerializer


def create_authenticated_order(
    user,
    address_id,
    order_items,
    payment_method,
    transport_method,
    note="",
    subscription=None,
):
    """
    Kreira narudžbinu kao ulogovan korisnik (ista logika kao OrderCreateView).
    order_items: [{"product": int, "quantity": int}, ...]
    """
    factory = RequestFactory()
    wsgi_req = factory.post("/api/orders/create/")
    wsgi_req.user = user
    request = Request(wsgi_req)
    request._user = user
    request._auth = None
    data = {
        "address": address_id,
        "order_items": order_items,
        "payment_method": payment_method,
        "transport_method": transport_method,
        "use_points": False,
        "note": note or "",
    }
    serializer = OrderSerializer(data=data, context={"request": request})
    serializer.is_valid(raise_exception=True)
    order = serializer.save()
    if subscription is not None:
        order.subscription = subscription
        order.save(update_fields=["subscription"])
    return order
