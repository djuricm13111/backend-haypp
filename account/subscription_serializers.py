from rest_framework import serializers

from product.models import Product
from .models import AddressBook, ProductSubscription, SubscriptionItem

ALLOWED_INTERVAL_DAYS = frozenset({14, 31, 62})


class SubscriptionItemReadSerializer(serializers.ModelSerializer):
    product_id = serializers.IntegerField(source="product.id", read_only=True)
    product_name = serializers.CharField(source="product.name", read_only=True)
    sku = serializers.CharField(source="product.sku", read_only=True)

    class Meta:
        model = SubscriptionItem
        fields = ("id", "product_id", "product_name", "sku", "quantity")


class ProductSubscriptionReadSerializer(serializers.ModelSerializer):
    items = SubscriptionItemReadSerializer(many=True, read_only=True)
    address_id = serializers.IntegerField(source="address.id", read_only=True)

    class Meta:
        model = ProductSubscription
        fields = (
            "id",
            "interval_days",
            "status",
            "address_id",
            "payment_method",
            "transport_method",
            "note",
            "next_order_at",
            "cancelled_at",
            "created_at",
            "items",
        )


class SubscriptionItemInputSerializer(serializers.Serializer):
    product = serializers.IntegerField(min_value=1)
    quantity = serializers.IntegerField(min_value=1, default=1)


class ProductSubscriptionCreateSerializer(serializers.Serializer):
    interval_days = serializers.IntegerField(min_value=1)
    address = serializers.IntegerField(min_value=1)
    payment_method = serializers.CharField(max_length=20)
    transport_method = serializers.CharField(max_length=20)
    note = serializers.CharField(required=False, allow_blank=True, default="")
    items = SubscriptionItemInputSerializer(many=True)

    def validate_interval_days(self, value):
        if value not in ALLOWED_INTERVAL_DAYS:
            raise serializers.ValidationError(
                f"Dozvoljeni intervali su: {', '.join(map(str, sorted(ALLOWED_INTERVAL_DAYS)))} dana."
            )
        return value

    def validate_items(self, value):
        if not value:
            raise serializers.ValidationError("Potrebna je bar jedna stavka (proizvod i količina).")
        return value

    def validate_address(self, value):
        request = self.context["request"]
        if not AddressBook.objects.filter(id=value, user=request.user).exists():
            raise serializers.ValidationError("Adresa nije pronađena ili ne pripada nalogu.")
        return value

    def validate(self, attrs):
        seen = set()
        for row in attrs["items"]:
            pid = row["product"]
            if pid in seen:
                raise serializers.ValidationError(
                    {"items": "Isti proizvod ne može biti dva puta u istom zahtevu; uvećajte količinu."}
                )
            seen.add(pid)
            if not Product.objects.filter(pk=pid).exists():
                raise serializers.ValidationError({"items": f"Proizvod id={pid} ne postoji."})
        return attrs


class SubscriptionAddItemSerializer(serializers.Serializer):
    product = serializers.IntegerField(min_value=1)
    quantity = serializers.IntegerField(min_value=1, default=1)

    def validate_product(self, value):
        if not Product.objects.filter(pk=value).exists():
            raise serializers.ValidationError("Proizvod ne postoji.")
        return value
