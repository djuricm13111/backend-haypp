from rest_framework import serializers
from .models import Product, CartItem, Cart, ProductState, Category, FeaturedGroup
from django.utils.translation import gettext as _
from django.utils.translation import get_language
from scripts.currency_converter import convert_currency, DEFAULT_CURRENCY
from backend.settings import MODELTRANSLATION_DEFAULT_LANGUAGE

import logging

# Konfiguriši logger
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)  # Možeš podesiti na INFO ili ERROR u zavisnosti od potrebe


class ProductSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    price = serializers.SerializerMethodField()
    discounted_price = serializers.SerializerMethodField()  # New field for discounted price
    is_in_stock = serializers.SerializerMethodField()
    images = serializers.SerializerMethodField()
    is_mix_pack = serializers.SerializerMethodField()

    def get_images(self, obj):
        # Pretpostavlja se da ProductImage ima metodu get_image_url
        # koja vraća URL originalne slike, i metode get_large_image_url i
        # get_thumbnail_image_url za varijante veličina slika.
        images = []
        if 'prefetched_images' in self.context.keys():
            images = self.context['prefetched_images'].get(obj.id, [])
        else:
            images = obj.images.all()  # Preuzima sve slike povezane sa proizvodom
        
        return [{
            'original': image.get_image_url(),
            'large': image.get_large_image_url(),
            'thumbnail': image.get_thumbnail_image_url(),
            'is_primary': image.is_primary,
        } for image in images]
 
    
    
    def get_price(self, obj):
        currency = self.context.get('currency', DEFAULT_CURRENCY)  # Podrazumevana valuta je USD
        converted_price = convert_currency(obj.price.amount, DEFAULT_CURRENCY, currency)
        return converted_price

    def get_discounted_price(self, obj):
        if obj.discounted_price and obj.discounted_price < obj.price:
            currency = self.context.get('currency', DEFAULT_CURRENCY)
            converted_discounted_price = convert_currency(obj.discounted_price.amount, DEFAULT_CURRENCY, currency)
            return converted_discounted_price
        return None

    def get_is_in_stock(self, obj):
        return obj.display_catalog_state()

    def get_is_mix_pack(self, obj):
        v = getattr(obj, "is_mix_pack", None)
        if v is not None:
            return bool(v)
        return obj.mix_lines.exists()

    class Meta:
        model = Product
        fields = [
            "id",
            "name",
            "nicotine",
            "price",
            "discounted_price",
            "category_name",
            "recommended",
            "pouches_per_can",
            "format",
            "flavor",
            "net_weight",
            "manufacturer",
            "sales_count",
            "is_in_stock",
            "created_at",
            "images",
            "is_mix_pack",
        ]


class ProductLiteSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    price = serializers.SerializerMethodField()
    is_in_stock = serializers.SerializerMethodField()
    is_mix_pack = serializers.SerializerMethodField()
    
    def get_price(self, obj):
        currency = self.context.get('currency', DEFAULT_CURRENCY)  # Podrazumevana valuta je USD
        converted_price = convert_currency(obj.price.amount, DEFAULT_CURRENCY, currency)
        return converted_price

    def get_is_in_stock(self, obj):
        return obj.display_catalog_state()

    def get_is_mix_pack(self, obj):
        v = getattr(obj, "is_mix_pack", None)
        if v is not None:
            return bool(v)
        return obj.mix_lines.exists()

    class Meta:
        model = Product
        fields = [
            "id",
            "name",
            "slug",
            "nicotine",
            "price",
            "category_name",
            "pouches_per_can",
            "format",
            "flavor",
            "net_weight",
            "is_in_stock",
            "is_mix_pack",
        ]


class CategorySerializer(serializers.ModelSerializer):
    images = serializers.SerializerMethodField()
    def get_images(self, obj):
        image = obj.images.first()  
        if image:
            return {
                'desktop': image.desktop_image_key,
                'mobile': image.mobile_image_key,
            }
        return None
    

    class Meta:
        model = Category
        fields = ['id', 'name', 'slug', 'color',  'images']


class ProductOrderHistorySerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    images = serializers.SerializerMethodField()

    def get_images(self, obj):
        # Pretpostavlja se da ProductImage ima metodu get_image_url
        # koja vraća URL originalne slike, i metode get_large_image_url i
        # get_thumbnail_image_url za varijante veličina slika.
        images = obj.images.all()  # Preuzima sve slike povezane sa proizvodom
        return [{
            'original': image.get_image_url(),
            'large': image.get_large_image_url(),
            'thumbnail': image.get_thumbnail_image_url(),
            'is_primary': image.is_primary,
        } for image in images]

    class Meta:
        model = Product
        fields = [
            'id',
            'slug',
            'category_name',
            'name',
            'nicotine',
            'pouches_per_can',
            'format',
            'flavor',
            'images',
        ]


class ProductFeaturedSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    images = serializers.SerializerMethodField()
    price = serializers.SerializerMethodField()
    is_in_stock = serializers.SerializerMethodField()
    is_mix_pack = serializers.SerializerMethodField()

    def get_images(self, obj):
        # Pretpostavlja se da ProductImage ima metodu get_image_url
        # koja vraća URL originalne slike, i metode get_large_image_url i
        # get_thumbnail_image_url za varijante veličina slika.
        images = []
        if 'prefetched_images' in self.context.keys():
            images = self.context['prefetched_images'].get(obj.id, [])
        else:
            images = obj.images.all()  # Preuzima sve slike povezane sa proizvodom
        
        return [{
            'original': image.get_image_url(),
            'large': image.get_large_image_url(),
            'thumbnail': image.get_thumbnail_image_url(),
            'is_primary': image.is_primary,
        } for image in images]
    
    def get_price(self, obj):
        currency = self.context.get('currency', DEFAULT_CURRENCY)  # Podrazumevana valuta je USD
        converted_price = convert_currency(obj.price.amount, DEFAULT_CURRENCY, currency)
        return converted_price

    def get_is_in_stock(self, obj):
        return obj.display_catalog_state()

    def get_is_mix_pack(self, obj):
        v = getattr(obj, "is_mix_pack", None)
        if v is not None:
            return bool(v)
        return obj.mix_lines.exists()

    class Meta:
        model = Product
        fields = [
            "id",
            "name",
            "nicotine",
            "price",
            "category_name",
            "images",
            "pouches_per_can",
            "format",
            "flavor",
            "net_weight",
            "is_in_stock",
            "is_mix_pack",
        ]
class FeaturedGroupSerializer(serializers.ModelSerializer):
    products = ProductFeaturedSerializer(many=True)

    class Meta:
        model = FeaturedGroup
        fields = ("id", "name", "slug", "products") 


class CartItemSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    product_id = serializers.IntegerField(write_only=True)

    class Meta:
        model = CartItem
        fields = ['id', 'product', 'product_id', 'quantity']

    def create(self, validated_data):
        product_id = validated_data.pop('product_id')
        product = Product.objects.get(pk=product_id)
        quantity = validated_data.get('quantity', 1)

        cart, _ = Cart.objects.get_or_create(user=self.context['request'].user)
        cart_item, created = CartItem.objects.get_or_create(
            product=product,
            cart=cart,  # Dodajte cart kao deo get_or_create
            defaults={'quantity': quantity}
        )
        if not created:
            cart_item.quantity += quantity
            cart_item.save()
        
        cart.items.add(cart_item)  # Dodajte cart_item u items set
        cart.save()

        return cart_item


class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, read_only=True)

    class Meta:
        model = Cart
        fields = ['id', 'items']

