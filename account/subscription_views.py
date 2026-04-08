import logging
from datetime import timedelta

from django.db import transaction
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.settings import DEFAULT_DOMAIN
from .models import ProductSubscription, SubscriptionItem, SubscriptionStatus
from .order_email_data import build_order_confirmation_email_data
from .subscription_orders import create_authenticated_order
from .subscription_serializers import (
    ProductSubscriptionCreateSerializer,
    ProductSubscriptionReadSerializer,
    SubscriptionAddItemSerializer,
)
from .tasks import send_order_confirmation_email

logger = logging.getLogger(__name__)


def _enqueue_confirmation(order, language):
    try:
        data = build_order_confirmation_email_data(order)
        send_order_confirmation_email.delay(order.user.email, data, language)
    except Exception:
        logger.exception("Subscription: greška pri slanju emaila za narudžbinu %s", order.pk)


class SubscriptionListCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        qs = ProductSubscription.objects.filter(user=request.user).prefetch_related(
            "items__product__category"
        )
        return Response(ProductSubscriptionReadSerializer(qs, many=True).data)

    def post(self, request):
        ser = ProductSubscriptionCreateSerializer(data=request.data, context={"request": request})
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        language = request.headers.get("Accept-Language", "en")

        order_items = [
            {"product": row["product"], "quantity": row["quantity"]} for row in data["items"]
        ]

        first_order = None
        with transaction.atomic():
            sub = ProductSubscription(
                user=request.user,
                interval_days=data["interval_days"],
                status=SubscriptionStatus.ACTIVE,
                address_id=data["address"],
                payment_method=data["payment_method"],
                transport_method=data["transport_method"],
                note=(data.get("note") or "").strip() or None,
                next_order_at=timezone.now() + timedelta(days=data["interval_days"]),
                domain=DEFAULT_DOMAIN,
            )
            sub.save()
            for row in data["items"]:
                SubscriptionItem.objects.create(
                    subscription=sub,
                    product_id=row["product"],
                    quantity=row["quantity"],
                )

            first_order = create_authenticated_order(
                user=request.user,
                address_id=data["address"],
                order_items=order_items,
                payment_method=data["payment_method"],
                transport_method=data["transport_method"],
                note=sub.note or "",
                subscription=sub,
            )

        sub.refresh_from_db()
        if first_order:
            _enqueue_confirmation(first_order, language)

        out = ProductSubscriptionReadSerializer(sub).data
        out["first_order_customer_id"] = getattr(first_order, "customer_order_id", None)
        return Response(out, status=status.HTTP_201_CREATED)


class SubscriptionCancelView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        try:
            sub = ProductSubscription.objects.get(pk=pk, user=request.user)
        except ProductSubscription.DoesNotExist:
            return Response({"detail": "Pretplata nije pronađena."}, status=status.HTTP_404_NOT_FOUND)
        if sub.status != SubscriptionStatus.ACTIVE:
            return Response({"detail": "Pretplata je već otkazana."}, status=status.HTTP_400_BAD_REQUEST)
        with transaction.atomic():
            sub.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class SubscriptionAddItemView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        try:
            sub = ProductSubscription.objects.get(pk=pk, user=request.user)
        except ProductSubscription.DoesNotExist:
            return Response({"detail": "Pretplata nije pronađena."}, status=status.HTTP_404_NOT_FOUND)
        if sub.status != SubscriptionStatus.ACTIVE:
            return Response(
                {"detail": "Ne možete menjati otkazanu pretplatu."}, status=status.HTTP_400_BAD_REQUEST
            )
        ser = SubscriptionAddItemSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        pid = ser.validated_data["product"]
        qty = ser.validated_data["quantity"]
        item, created = SubscriptionItem.objects.get_or_create(
            subscription=sub, product_id=pid, defaults={"quantity": qty}
        )
        if not created:
            item.quantity += qty
            item.save(update_fields=["quantity"])
        sub.refresh_from_db()
        return Response(ProductSubscriptionReadSerializer(sub).data, status=status.HTTP_200_OK)


class SubscriptionItemDeleteView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request, pk, item_id):
        try:
            sub = ProductSubscription.objects.get(pk=pk, user=request.user)
        except ProductSubscription.DoesNotExist:
            return Response({"detail": "Pretplata nije pronađena."}, status=status.HTTP_404_NOT_FOUND)
        if sub.status != SubscriptionStatus.ACTIVE:
            return Response(
                {"detail": "Ne možete menjati otkazanu pretplatu."}, status=status.HTTP_400_BAD_REQUEST
            )
        try:
            item = SubscriptionItem.objects.get(pk=item_id, subscription=sub)
        except SubscriptionItem.DoesNotExist:
            return Response({"detail": "Stavka nije pronađena."}, status=status.HTTP_404_NOT_FOUND)
        if sub.items.count() <= 1:
            return Response(
                {"detail": "Mora ostati bar jedan proizvod u pretplati ili otkažite pretplatu."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        item.delete()
        sub.refresh_from_db()
        return Response(ProductSubscriptionReadSerializer(sub).data, status=status.HTTP_200_OK)
