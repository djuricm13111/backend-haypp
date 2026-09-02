from rest_framework import serializers
from .models import CustomUser, UserInteraction, Referral, Order, Voucher
from product.serializers import ProductOrderHistorySerializer
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from rest_framework import serializers
from .models import AddressBook, PointsHistory, OrderItem, Blog, UserPoints, PaymentMethod, OrderStatus, TransportMethod, AddressType
from product.models import Product
from scripts.currency_converter import convert_currency, DEFAULT_CURRENCY
from scripts.discount import calculate_discount
from django.db import transaction
from djmoney.money import Money
from django.utils import timezone
from decimal import Decimal
from collections import defaultdict
from backend.settings import DEFAULT_DOMAIN


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        # Add custom claims
        token['email'] = user.email
        token['is_email_verified'] = user.is_email_verified
        token['is_staff'] = user.is_staff
        return token

class ReferralSerializer(serializers.ModelSerializer):
    referred_full_name = serializers.SerializerMethodField()

    class Meta:
        model = Referral
        fields = '__all__'  # Uključuje sve polje, uključujući i `referred_full_name`

    def get_referred_full_name(self, obj):
        # Vraća puno ime referala (pretpostavljajući da CustomUser model ima polja first_name i last_name)
        return f"{obj.referred.first_name} {obj.referred.last_name}"

class VoucherSerializer(serializers.ModelSerializer):
    amount_in_currency = serializers.SerializerMethodField()

    class Meta:
        model = Voucher
        # Isključuje 'amount' i 'amount_currency' polja iz odgovora
        exclude = ('amount', 'amount_currency') 

    def get_amount_in_currency(self, obj):
        # Uzmi valutu iz konteksta, podrazumevana vrednost je 'USD'
        request_currency = self.context.get('currency', DEFAULT_CURRENCY)
        # Konvertuj iznos vauchera iz USD u zahtevanu valutu
        converted_amount = convert_currency(obj.amount.amount, DEFAULT_CURRENCY, request_currency)
        # Vraća samo numeričku vrednost, bez oznake valute
        return f"{converted_amount}"

class PointsHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = PointsHistory
        fields = ['points', 'point_type', 'reason', 'date', 'status']

class AddressBookSerializer(serializers.ModelSerializer):
    class Meta:
        model = AddressBook
        fields = ['id', 'country', 'city', 'postal_code', 'street', 'street_number', 'secondary_street', 'building_number', 'latitude', 'longitude', 'phone_number', 'type', 'is_primary']

    def create(self, validated_data):
        # Pristupite trenutno autentifikovanom korisniku koristeći context
        user = self.context['request'].user
        # Dodajte trenutno autentifikovanog korisnika kao user-a nove adrese i kreirajte adresu
        return AddressBook.objects.create(user=user, **validated_data)


class CustomUserSerializer(serializers.ModelSerializer):
    referral_code = serializers.CharField(required=False)
    class Meta:
        model = CustomUser
        fields = ['id','email', 'first_name', 'last_name', 'phone_number', 'password', 'referral_code', 'is_email_verified'] 
        extra_kwargs = {'password': {'write_only': True}}

    def create(self, validated_data):
        with transaction.atomic():
            referral_code = validated_data.pop('referral_code', None)
            password = validated_data.pop('password', None)
            user = CustomUser.objects.create_user(**validated_data, password=password, domain=DEFAULT_DOMAIN)
            
            
            # Logika za povezivanje referral-a
            if referral_code:
                try:
                    referrer = CustomUser.objects.get(referral_code=referral_code)
                    Referral.objects.create(referrer=referrer, referred=user)
                    # Kreiranje zapisa u PointsHistory za referrer-a
                    # Dodajemo 400 poena referrer-u kao "pending" dok akcija nije odobrena
                    #TODO
                    PointsHistory.objects.create(
                        user=referrer,
                        points=1,
                        point_type=PointsHistory.PointType.REFERRAL,  
                        reason="Referred a new user",
                        status=PointsHistory.Status.PENDING  # Poeni su postavljeni kao "pending"
                    )
                except CustomUser.DoesNotExist:
                    pass

            UserPoints.objects.get_or_create(user=user, domain=DEFAULT_DOMAIN)
            return user

class OrderHistoryItemSerializer(serializers.ModelSerializer):
    product_details = ProductOrderHistorySerializer(source='product', read_only=True)

    class Meta:
        model = OrderItem
        fields = ['product_details', 'quantity', 'price', 'is_shipped', 'shipped_at']
        
class OrderHistorySerializer(serializers.ModelSerializer):
    order_items = OrderHistoryItemSerializer(many=True)
    address_details = AddressBookSerializer(source='address', read_only=True)
    currency_symbol = serializers.SerializerMethodField()  # Ispravljeno: uklonjeni argumenti

    class Meta:
        model = Order
        fields = [
            'id',
            'customer_order_id',
            'order_items',
            'address_details',
            'payment_method',
            'subtotal',
            'total_price',
            'shipping_cost',
            'created_at',
            'currency_symbol',
            'order_status',
        ]

    def get_currency_symbol(self, obj):
        # Mapiranje valute na simbol
        currency_symbols = {"USD": "$", "EUR": "€"}  # Dodajte više valuta po potrebi

        # Pretpostavljamo da obj.total_price sadrži Money instancu koja ima atribut currency
        return currency_symbols.get(obj.total_price.currency.code, obj.total_price.currency.code)  # Vraća simbol ako postoji, inače kod valute


class AdminOrderItemSerializer(serializers.ModelSerializer):
    label = serializers.SerializerMethodField()
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = OrderItem
        fields = [
            'id',
            'quantity',
            'is_shipped',
            'shipped_at',
            'label',
            'image_url',
            'price',
            'discounted_price',
        ]

    def get_label(self, obj):
        if obj.product_id and obj.product:
            return f"{obj.product.category.name} {obj.product.name}"
        return "—"

    def get_image_url(self, obj):
        if obj.product_id and obj.product:
            img = obj.product.images.filter(is_primary=True).first() or obj.product.images.first()
            if img:
                return img.get_thumbnail_image_url() or img.get_image_url()
        return None


class AdminOrderSerializer(serializers.ModelSerializer):
    order_items = AdminOrderItemSerializer(many=True, read_only=True)
    user_email = serializers.EmailField(source='user.email', read_only=True)
    user_first_name = serializers.CharField(source='user.first_name', read_only=True)
    user_last_name = serializers.CharField(source='user.last_name', read_only=True)
    address_details = AddressBookSerializer(source='address', read_only=True)
    items_shipped_count = serializers.SerializerMethodField()
    items_total_count = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            'id',
            'customer_order_id',
            'order_status',
            'payment_method',
            'transport_method',
            'created_at',
            'updated_at',
            'note',
            'subtotal',
            'total_price',
            'shipping_cost',
            'user_email',
            'user_first_name',
            'user_last_name',
            'address_details',
            'order_items',
            'items_shipped_count',
            'items_total_count',
        ]

    def get_items_shipped_count(self, obj):
        cached = getattr(obj, '_prefetched_objects_cache', {}).get('order_items')
        if cached is not None:
            return sum(1 for i in cached if i.is_shipped)
        return obj.order_items.filter(is_shipped=True).count()

    def get_items_total_count(self, obj):
        cached = getattr(obj, '_prefetched_objects_cache', {}).get('order_items')
        if cached is not None:
            return len(cached)
        return obj.order_items.count()


class CustomUserDetailSerializer(CustomUserSerializer):
    addresses = AddressBookSerializer(many=True, read_only=True) 
    referrals_made = ReferralSerializer(many=True, read_only=True)
    vouchers = serializers.SerializerMethodField()
    order_history = serializers.SerializerMethodField()
    user_points = serializers.SerializerMethodField()

    class Meta(CustomUserSerializer.Meta):
        fields = CustomUserSerializer.Meta.fields + ['is_staff', 'addresses', 'referrals_made', 'vouchers', 'order_history', 'user_points']
    def get_vouchers(self, obj):
        currency = self.context.get('currency', DEFAULT_CURRENCY)
        
        # Instanciranje VoucherSerializer sa prosleđenim kontekstom
        voucher_serializer = VoucherSerializer(obj.vouchers.all(), many=True, context={'currency': currency})
        
        return voucher_serializer.data
    def get_order_history(self, obj):
        # Dobavljamo sve porudžbine za korisnika i serijalizujemo ih
        orders = Order.objects.filter(user=obj).order_by('-created_at').prefetch_related(
        'order_items',  # Učitavamo povezane OrderItem objekte
        'order_items__product'  # Učitavamo povezane Product objekte za svaki OrderItem
    )
        order_serializer = OrderHistorySerializer(orders, many=True)
        return order_serializer.data
    def get_user_points(self, obj):
        user_points = obj.user_points.first()
        if user_points:
            return {
                'points': user_points.points,
                'vip_points': user_points.vip_points,
                'level': user_points.level
            }
        return {
            'points': 0,
            'vip_points': 0,
            'level': 1
        }

#Order
from rest_framework import serializers

class OrderItemMobileSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()
    image_url = serializers.SerializerMethodField()  
    scanned = serializers.BooleanField(default=False, read_only=True)
    sku = serializers.CharField(source='product.sku', read_only=True)

    class Meta:
        model = OrderItem
        fields = ['id', 'name', 'quantity', 'scanned', 'image_url', 'sku'] 

    def get_name(self, obj):
        if obj.product and obj.product.category:
            return f"{obj.product.category.name} {obj.product.name}"
        return obj.product.name if obj.product else "No Product"

    def get_image_url(self, obj):  
        if obj.product and hasattr(obj.product, 'images'):
            primary_image = obj.product.images.filter(is_primary=True).first()
            if primary_image:
                return primary_image.get_image_url()
        return None

class OrderMobileSerializer(serializers.ModelSerializer):
    order_items = OrderItemMobileSerializer(many=True, read_only=True)
    class Meta:
        model = Order
        fields = ['id', 'order_status', 'purchase_date', 'order_items']


class OrderItemSerializer(serializers.ModelSerializer):
    # Koristi ProductSerializer za 'product' polje umesto prikazivanja samo ID-a
    #product = ProductSerializer(read_only=True)

    class Meta:
        model = OrderItem
        fields = ['product', 'quantity']


import logging
import secrets

from .subscription_checkout import create_subscriptions_from_checkout_order
from .subscription_serializers import ALLOWED_INTERVAL_DAYS

logger = logging.getLogger(__name__)


class CheckoutSubscriptionEntrySerializer(serializers.Serializer):
    """Pretplata: proizvod, interval (dani), količina koja ulazi u pretplatu (može biti < ukupno u korpi)."""
    product = serializers.IntegerField(min_value=1)
    interval_days = serializers.IntegerField(min_value=1)
    quantity = serializers.IntegerField(min_value=1)

    def validate_interval_days(self, value):
        if value not in ALLOWED_INTERVAL_DAYS:
            raise serializers.ValidationError(
                f"Dozvoljeni intervali su: {', '.join(map(str, sorted(ALLOWED_INTERVAL_DAYS)))} dana."
            )
        return value


class OrderSerializer(serializers.ModelSerializer):
    order_items = OrderItemSerializer(many=True)
    use_points = serializers.BooleanField(write_only=True, default=False)
    guest_email = serializers.EmailField(write_only=True, required=False, allow_blank=True)
    guest_first_name = serializers.CharField(write_only=True, required=False, allow_blank=True)
    guest_last_name = serializers.CharField(write_only=True, required=False, allow_blank=True)
    shipping_address = serializers.DictField(write_only=True, required=False, allow_null=True)
    confirmation_email = serializers.EmailField(
        write_only=True,
        required=False,
        allow_blank=True,
        help_text="Za ulogovanog korisnika: nova e-adresa se upisuje u nalog nakon potvrde porudžbine.",
    )
    subscriptions = CheckoutSubscriptionEntrySerializer(
        many=True,
        required=False,
        default=list,
        help_text="Opciono: lista {product, interval_days, quantity} za automatske ponovljene porudžbine.",
    )

    address = serializers.PrimaryKeyRelatedField(
        queryset=AddressBook.objects.all(),
        required=False,
        allow_null=True,
    )

    class Meta:
        model = Order
        fields = [
            'address',
            'order_items',
            'payment_method',
            'transport_method',
            'use_points',
            'note',
            'guest_email',
            'guest_first_name',
            'guest_last_name',
            'shipping_address',
            'confirmation_email',
            'subscriptions',
        ]

    def validate_address(self, value):
        request = self.context['request']
        if value is None:
            return value
        user = request.user
        if not user.is_authenticated:
            raise serializers.ValidationError("Za gostujuću kupovinu ne šaljite ID adrese.")
        if value.user != user:
            raise serializers.ValidationError("Ova adresa ne pripada autentikovanom korisniku.")
        return value

    def validate(self, attrs):
        request = self.context['request']
        user = request.user
        if user.is_authenticated:
            if not attrs.get('address'):
                raise serializers.ValidationError({'address': 'Ovo polje je obavezno za prijavljene korisnike.'})
            for key in ('guest_email', 'guest_first_name', 'guest_last_name', 'shipping_address'):
                if attrs.get(key):
                    raise serializers.ValidationError({key: 'Ova polja nisu dozvoljena kada ste prijavljeni.'})
            ce = attrs.get('confirmation_email')
            if ce and str(ce).strip():
                ce_norm = str(ce).strip()
                if CustomUser.objects.filter(email__iexact=ce_norm).exclude(pk=user.pk).exists():
                    raise serializers.ValidationError(
                        {'confirmation_email': 'Ova e-adresa je već povezana sa drugim nalogom.'}
                    )
        else:
            if attrs.get('address'):
                raise serializers.ValidationError({'address': 'Za gostujuću kupovinu ostavite adresu praznom.'})
            ge = attrs.get('guest_email')
            gf = attrs.get('guest_first_name')
            gl = attrs.get('guest_last_name')
            sa = attrs.get('shipping_address')
            if not ge or not str(ge).strip():
                raise serializers.ValidationError({'guest_email': 'Obavezno za gostujuću kupovinu.'})
            if not gf or not str(gf).strip():
                raise serializers.ValidationError({'guest_first_name': 'Obavezno za gostujuću kupovinu.'})
            if not gl or not str(gl).strip():
                raise serializers.ValidationError({'guest_last_name': 'Obavezno za gostujuću kupovinu.'})
            if not isinstance(sa, dict):
                raise serializers.ValidationError({'shipping_address': 'Neispravan format adrese.'})
            if not str(sa.get('country', '')).strip() or not str(sa.get('city', '')).strip() or not str(sa.get('postal_code', '')).strip() or not str(sa.get('street', '')).strip():
                raise serializers.ValidationError({'shipping_address': 'Država, grad, poštanski broj i ulica su obavezni.'})
            if attrs.get('use_points'):
                raise serializers.ValidationError({'use_points': 'Poeni nisu dostupni za gostujuću kupovinu.'})
            email = str(ge).strip()
            if CustomUser.objects.filter(email__iexact=email).exists():
                raise serializers.ValidationError(
                    {'guest_email': 'Nalog sa ovom e-adresom već postoji. Prijavite se da završite porudžbinu.'}
                )
        subs = attrs.get('subscriptions') or []
        if subs:
            order_items = attrs.get('order_items', [])
            product_qty = {}
            for oi in order_items:
                p = oi.get('product')
                if not p:
                    continue
                pid = p.pk if hasattr(p, 'pk') else int(p)
                product_qty[pid] = product_qty.get(pid, 0) + int(oi.get('quantity', 1))
            sub_qty_by_product = defaultdict(int)
            for s in subs:
                pid = s['product']
                if pid not in product_qty:
                    raise serializers.ValidationError(
                        {'subscriptions': f'Proizvod {pid} nije u porudžbini kao običan proizvod.'}
                    )
                sub_qty_by_product[pid] += int(s['quantity'])
            for pid, sq in sub_qty_by_product.items():
                if sq > product_qty[pid]:
                    raise serializers.ValidationError(
                        {
                            'subscriptions': (
                                f'Za proizvod {pid} je u pretplati traženo {sq} kom, '
                                f'a u porudžbini je ukupno {product_qty[pid]}.'
                            )
                        }
                    )
        return attrs

    def create(self, validated_data):
        logger.info(f"Creating order with validated data: {validated_data}")
        request = self.context['request']
        guest_email = validated_data.pop('guest_email', None)
        guest_first_name = validated_data.pop('guest_first_name', None)
        guest_last_name = validated_data.pop('guest_last_name', None)
        shipping_address = validated_data.pop('shipping_address', None)
        confirmation_email = validated_data.pop('confirmation_email', None)
        if confirmation_email is not None and str(confirmation_email).strip() == '':
            confirmation_email = None

        subscription_input = validated_data.pop('subscriptions', [])

        if request.user.is_authenticated:
            user = request.user
        else:
            user = CustomUser.objects.create_user(
                email=guest_email.strip(),
                password=secrets.token_urlsafe(32),
                first_name=(guest_first_name or '').strip()[:30],
                last_name=(guest_last_name or '').strip()[:150],
                domain=DEFAULT_DOMAIN,
            )
            validated_data['address'] = AddressBook.objects.create(
                user=user,
                country=shipping_address['country'],
                city=shipping_address['city'],
                postal_code=shipping_address['postal_code'],
                street=shipping_address['street'],
                secondary_street=shipping_address.get('secondary_street') or None,
                building_number=shipping_address.get('building_number') or None,
                street_number=shipping_address.get('street_number') or None,
                phone_number=shipping_address.get('phone_number') or None,
                type=shipping_address.get('type') or AddressType.HOME,
                is_primary=True,
            )

        validated_data['user'] = user
        order_items_data = validated_data.pop('order_items')

        product_qty_for_sub = {}
        for oi in order_items_data:
            if 'product' in oi:
                pid = oi['product'].id if hasattr(oi['product'], 'id') else int(oi['product'])
                product_qty_for_sub[pid] = product_qty_for_sub.get(pid, 0) + int(oi.get('quantity', 1))

        use_points = validated_data.pop('use_points', False)
        transport_method = validated_data.get('transport_method', TransportMethod.POST_AT)
        currency = self.context.get('currency', DEFAULT_CURRENCY)
        points_spent = 0

        if validated_data['payment_method'] in [PaymentMethod.CARD, PaymentMethod.PAYPAL]:
            validated_data['order_status'] = OrderStatus.PAID
        total_qty = sum(int(item.get("quantity", 1)) for item in order_items_data)
        global_d = Decimal(str(calculate_discount(total_qty)))

        with transaction.atomic():
            total_price = Money(0, DEFAULT_CURRENCY)

            order = Order(**validated_data)
            order.save()

            for item_data in order_items_data:
                if "product" not in item_data:
                    raise Exception("Svaka stavka porudžbine mora imati product.")
                product = Product.objects.get(id=item_data["product"].id)
                quantity = item_data.get('quantity', 1)

                product.sales_count += quantity
                product.save()

                line_d = (
                    Decimal(0)
                    if product.mix_lines.exists()
                    else global_d
                )
                # Koristi discounted_price kao bazu ako je postavljen i niži od price
                # (usklađeno sa frontend volumeAdjustedUnitPrice logikom)
                if product.discounted_price and product.discounted_price < product.price:
                    base_price = product.discounted_price.amount
                else:
                    base_price = product.price.amount
                unit_disc = base_price * (Decimal(1) - line_d)
                line_subtotal = Money(unit_disc * Decimal(quantity), DEFAULT_CURRENCY)
                total_price += line_subtotal

                OrderItem.objects.create(
                    order=order,
                    product=product,
                    quantity=quantity,
                    price=Money(product.price.amount, DEFAULT_CURRENCY),
                    discounted_price=Money(unit_disc, DEFAULT_CURRENCY),
                )

            # Dodato ovde
            # Usklađeno sa frontendom (global_const.freeShippingThreshold = 50): besplatna dostava od €50 međuzbira.
            # Ispod praga: fiksno €20 za Post/DHL Standard (ranije težinski proračun ~€12).
            free_subtotal_threshold = Decimal("50")
            flat_shipping_eur = Decimal("20")
            express_shipping_eur = Decimal("24.90")

            if total_price.amount >= free_subtotal_threshold:
                shipping_cost = Money(0, DEFAULT_CURRENCY)
            elif transport_method == TransportMethod.DHL_EXPRESS_SAVER:
                shipping_cost = Money(express_shipping_eur, DEFAULT_CURRENCY)
            else:
                shipping_cost = Money(flat_shipping_eur, DEFAULT_CURRENCY)


            if use_points:
                max_deduction = user.points * 10
                if max_deduction > total_price.amount:
                    points_spent = total_price.amount / 10
                    total_price = Money(0, DEFAULT_CURRENCY)
                else:
                    points_spent = user.points
                    total_price -= Money(max_deduction, DEFAULT_CURRENCY)
                user.points -= points_spent
                user.points = user.points#round(user.points, 4)


            order.shipping_cost = shipping_cost
            order.subtotal = total_price
            # Ukupno kao na checkout-u: međuzbir + dostava. PDV je već u cenama proizvoda (B2C, uračunat).
            order.total_price = total_price + shipping_cost
            order.save()

            # Update user's last order date and total orders
            user.last_order_date = timezone.now()
            user.total_orders += 1
            

            user.save()

            if request.user.is_authenticated and confirmation_email:
                ce = str(confirmation_email).strip()
                if ce and ce.lower() != user.email.lower():
                    user.email = ce
                    user.save(update_fields=['email'])

            if subscription_input and order.address_id:
                sub_rows = []
                for s in subscription_input:
                    sub_rows.append(
                        {
                            'product': s['product'],
                            'quantity': int(s['quantity']),
                            'interval_days': s['interval_days'],
                        }
                    )
                create_subscriptions_from_checkout_order(order, user, sub_rows)

        # Record points usage in PointsHistory outside of the transaction
        if points_spent > 0:
            PointsHistory.objects.create(
                user=user,
                points=-points_spent,
                point_type=PointsHistory.PointType.REDEEM,
                status=PointsHistory.Status.APPROVED,
                reason=f'Redeemed for order {order.id}'
            )
        return order




    
class UserInteractionSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserInteraction
        fields = '__all__'
from django.utils.translation import get_language
class BlogSerializer(serializers.ModelSerializer):
    class Meta:
        model = Blog
        fields = ['id', 'title', 'slug', 'subtitles', 'paragraphs', 'published_date', 'updated_date']

    def to_representation(self, instance):
        language = get_language()
        representation = super().to_representation(instance)

        # Dinamički koristimo prevedena polja za trenutni jezik
        for field in ['title', 'subtitles', 'paragraphs']:
            translated_field_name = f"{field}_{language}"
            if hasattr(instance, translated_field_name):
                representation[field] = getattr(instance, translated_field_name)

        return representation