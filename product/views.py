from django.conf import settings
from django.shortcuts import render
from rest_framework import generics, permissions, status, views
from rest_framework.response import Response
from .models import Product, Cart, CartItem, ProductImage, Category, ProductState, FeaturedGroup, MixPackLine
from .serializers import ProductSerializer,CartSerializer, CartItemSerializer, CategorySerializer, FeaturedGroupSerializer
from rest_framework.decorators import action
from django.core.cache import cache
from rest_framework import viewsets
from decimal import Decimal, InvalidOperation
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django.db.models import Value, CharField, Count, Q, F, Exists, OuterRef
from django.db.models.functions import Concat

from rest_framework.views import APIView
from django.db import transaction
from django.shortcuts import get_object_or_404
#PRODUCTS
from scripts.currency_converter import convert_currency, DEFAULT_CURRENCY
from rest_framework.pagination import PageNumberPagination

from django.db.models import Prefetch
import logging
from collections import defaultdict
from django.db.models import Case, When, Value, IntegerField


logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)


def queryset_with_is_mix_pack(queryset):
    """Annotira queryset: is_mix_pack ako proizvod ima bar jednu MixPackLine kao bundle."""
    return queryset.annotate(
        is_mix_pack=Exists(
            MixPackLine.objects.filter(mix_product_id=OuterRef("pk"))
        )
    )


class CatalogFilterMixin:
    """Jedan katalog: filter po globalnom limitu nikotina; stanje je na Product.state."""

    def apply_nicotine_limit(self, qs):
        max_n = getattr(settings, 'MAX_NICOTINE_MG_PER_POUCH', 999)
        return qs.filter(Q(nicotine__isnull=True) | Q(nicotine__lte=max_n))

    def get_filtered_queryset(self):
        qs = Product.objects.filter(is_deleted=False).distinct()
        qs = self.apply_nicotine_limit(qs)
        qs = qs.annotate(
            stock_order=Case(
                When(state=ProductState.IN_STOCK, then=Value(0)),
                When(state=ProductState.ON_REQUEST, then=Value(1)),
                default=Value(2),
                output_field=IntegerField(),
            )
        )
        return qs.order_by('stock_order')


from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.authentication import JWTAuthentication
class CategoryListView(CatalogFilterMixin, generics.ListAPIView):
    """
    Kategorije koje imaju bar jedan proizvod koji prolazi katalog-filtere.
    """
    serializer_class = CategorySerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [AllowAny]

    def get_queryset(self):
        # 1) Osnovni QS proizvoda koji prolaze sve filtere iz mixina
        prod_qs = self.get_filtered_queryset()

        # 2) Uzme samo kategorije čiji ID se pojavljuje u tim proizvodima
        qs = Category.objects.filter(
            id__in=prod_qs.values_list('category_id', flat=True)
        ).distinct()

        # 3) (optional) možeš da dodaš neku custom logiku sortiranja
        #    npr. ako imaš priority ili želite po imenu
        return qs.order_by('name')
    
class CategoryProductsView(CatalogFilterMixin, APIView):
    """
    Vraća pojedinačnu kategoriju + sve proizvode iz te kategorije,
    filtrirane i sortirane po dostupnosti pa po popularnosti.
    """
    def get(self, request, slug, format=None):
        # Učitaj SEO za kategoriju
        try:
            category = Category.objects.get(slug=slug)
        except Category.DoesNotExist:
            return Response(
                {'error': 'Kategorija nije pronađena.'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # 1) Osnovni queryset u kategoriji (već ima stock_order iz mixina)
        qs = queryset_with_is_mix_pack(
            self.get_filtered_queryset().filter(category=category)
        )
        products = qs.order_by('stock_order', '-sales_count')

        # Serijalizacija
        category_serializer = CategorySerializer(
            category,
            context={'request': request}
        )
        product_serializer = ProductSerializer(
            products,
            many=True,
            context={
                'request': request,
                'currency': request.headers.get('Currency', DEFAULT_CURRENCY),
            }
        )

        return Response({
            'category': category_serializer.data,
            'products': product_serializer.data
        }, status=status.HTTP_200_OK)

#TODO ubaciti paginaciju ako je potrebna
class ProductPagination(PageNumberPagination):
    page_size = 30
    
class ProductViewSet(CatalogFilterMixin, viewsets.ModelViewSet):
    serializer_class = ProductSerializer
    permission_classes = [permissions.AllowAny]
    lookup_field = 'slug'

    def get_queryset(self):
        return queryset_with_is_mix_pack(self.get_filtered_queryset())

    def retrieve(self, request, *args, **kwargs):
        """
        Враћа један производ користећи базни queryset из get_queryset(),
        који већ може да садржи све потребне prefetch-ове.
        """
        # Користимо само базни queryset, без додатног prefetch_related
        queryset = self.get_queryset()
        product = get_object_or_404(queryset, slug=kwargs.get('slug'))
        serializer = self.get_serializer(product)
        return Response(serializer.data)
    
    
    def list(self, request, *args, **kwargs):
        currency = request.headers.get('Currency', DEFAULT_CURRENCY)

        cache_key = f"all_products_{currency}"

        # Provera da li su podaci dostupni u kešu
        cached_data = cache.get(cache_key)
        if cached_data is not None:
            return Response(cached_data)  # Vraćanje podataka iz keša ako su dostupni
        
        # Ako podaci nisu u kešu, nastavite sa uobičajenom logikom
        queryset = self.get_queryset()
        response = super(ProductViewSet, self).list(request, *args, **kwargs)
        
        # Keširanje odgovora pre slanja
        cache.set(cache_key, response.data, 60*15)  # Keširajte na 15 minuta
        return response
   
    def get_serializer_context(self):
        """
        Dodaje informaciju o valuti u kontekst serializer-a za sve metode.
        """
        context = super().get_serializer_context()
        context['currency'] = self.request.headers.get('Currency', DEFAULT_CURRENCY)  # Podrazumevana valuta je USD

        prefetched_images = defaultdict(list)
        for image in ProductImage.objects.all():
            prefetched_images[image.product_id].append(image)
        context['prefetched_images'] = prefetched_images
        return context

    @action(detail=False, methods=['get'], url_path='new-arrivals')
    def new_arrivals(self, request, *args, **kwargs):
        currency = request.headers.get('Currency', DEFAULT_CURRENCY)  # Uzimanje valute iz zaglavlja zahteva
        cache_key = f"new_arrivals_{currency}"

        # Provera da li su podaci dostupni u kešu
        cached_data = cache.get(cache_key)
        if cached_data is not None:
            return Response(cached_data)  # Vraćanje keširanih podataka ako su dostupni

        # Ako podaci nisu u kešu, izvršite upit i serijalizujte podatke
        new_arrivals_products = self.get_queryset().filter(state=ProductState.IN_STOCK).order_by('-created_at')[:13]
        serializer = self.get_serializer(new_arrivals_products, many=True)

        # Keširanje odgovora pre slanja
        cache.set(cache_key, serializer.data, 60*15)  # Keširajte na 15 minuta
        return Response(serializer.data)

    
    @action(detail=False, methods=['get'], url_path='best-sellers')
    def best_selling(self, request, *args, **kwargs):
        currency = request.headers.get('Currency', DEFAULT_CURRENCY)  # Uzimanje valute iz zaglavlja zahteva
        cache_key = f"best_selling_{currency}"  # Kreiranje ključa keša koji uključuje valutu

        # Provera da li su podaci dostupni u kešu
        cached_data = cache.get(cache_key)
        if cached_data is not None:
            return Response(cached_data)  # Vraćanje keširanih podataka ako su dostupni

        # Ako podaci nisu u kešu, izvršite upit i serijalizujte podatke
        best_selling_products = self.get_queryset().filter(state=ProductState.IN_STOCK).order_by('-sales_count')[:13]
        serializer = self.get_serializer(best_selling_products, many=True)

        # Keširanje odgovora pre slanja
        cache.set(cache_key, serializer.data, 60*15)  # Keširajte na 15 minuta
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='mix-packs')
    def mix_packs(self, request, *args, **kwargs):
        """Svi mix pack / bundle proizvodi u katalogu (isti filteri kao ostali listingi)."""
        currency = request.headers.get('Currency', DEFAULT_CURRENCY)
        cache_key = f"mix_packs_{currency}"
        cached_data = cache.get(cache_key)
        if cached_data is not None:
            return Response(cached_data)
        qs = (
            self.get_queryset()
            .filter(is_mix_pack=True)
            .order_by('stock_order', '-sales_count')
        )
        serializer = self.get_serializer(qs[:80], many=True)
        cache.set(cache_key, serializer.data, 60 * 15)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'], url_path='offers')
    def offers(self, request, *args, **kwargs):
        """Proizvodi sa postavljenom discounted_price (na popustu), sortirani po sales_count."""
        currency = request.headers.get('Currency', DEFAULT_CURRENCY)
        cache_key = f"offers_{currency}"
        cached_data = cache.get(cache_key)
        if cached_data is not None:
            return Response(cached_data)
        qs = (
            self.get_queryset()
            .filter(state=ProductState.IN_STOCK, discounted_price__isnull=False)
            .filter(discounted_price__lt=F('price'))
            .order_by('-sales_count')[:80]
        )
        serializer = self.get_serializer(qs, many=True)
        cache.set(cache_key, serializer.data, 60 * 15)
        return Response(serializer.data)

    @action(detail=True, methods=['get'], url_path='recommended')
    def recommended_products(self, request, slug=None):
        """
        Preporuke za PDP: prvo in_stock, pa dopuna najprodavanijima, zatim ON_REQUEST.
        """
        product = get_object_or_404(Product, slug=slug)
        current_is_mix = MixPackLine.objects.filter(mix_product_id=product.id).exists()
        flavor_keywords = (product.flavor or "").split()
        base_queryset = queryset_with_is_mix_pack(self.get_filtered_queryset())

        in_stock_qs = base_queryset.filter(
            state=ProductState.IN_STOCK,
            is_mix_pack=current_is_mix,
        ).distinct()

        sellable_qs = base_queryset.filter(
            state__in=(ProductState.IN_STOCK, ProductState.ON_REQUEST),
            is_mix_pack=current_is_mix,
        ).distinct()

        flavor_query = Q()
        for keyword in flavor_keywords:
            flavor_query |= Q(flavor__icontains=keyword)

        nic = product.nicotine if product.nicotine is not None else Decimal('0')
        target_n = 10
        recommended_products = []

        if flavor_keywords:
            recommended_products = list(
                in_stock_qs.filter(flavor_query)
                .exclude(id=product.id)
                .order_by('nicotine')[:target_n]
            )
        else:
            recommended_products = list(
                in_stock_qs.exclude(id=product.id).order_by('nicotine')[:target_n]
            )

        def picked_ids():
            return {p.id for p in recommended_products} | {product.id}

        if len(recommended_products) < target_n:
            nicotine_tolerance = Decimal('2.0')
            min_nicotine = max(Decimal('0.0'), nic - nicotine_tolerance)
            max_nicotine = nic + nicotine_tolerance
            q = (
                Q(nicotine__gte=min_nicotine)
                & Q(nicotine__lte=max_nicotine)
                & ~Q(id__in=picked_ids())
                & ~Q(category=product.category)
            )
            if flavor_keywords:
                q &= ~flavor_query
            remaining = list(
                in_stock_qs.filter(q).order_by('nicotine')[
                    : (target_n - len(recommended_products))
                ]
            )
            recommended_products.extend(remaining)

        if len(recommended_products) < target_n:
            q = Q(category=product.category) & ~Q(id__in=picked_ids())
            if flavor_keywords:
                q &= ~flavor_query
            additional = list(
                in_stock_qs.filter(q).order_by('nicotine')[
                    : (target_n - len(recommended_products))
                ]
            )
            recommended_products.extend(additional)

        if len(recommended_products) < target_n:
            pad = list(
                in_stock_qs.exclude(id__in=picked_ids()).order_by('-sales_count')[
                    : (target_n - len(recommended_products))
                ]
            )
            recommended_products.extend(pad)

        if len(recommended_products) < target_n:
            pad = list(
                sellable_qs.exclude(id__in=picked_ids()).order_by('-sales_count')[
                    : (target_n - len(recommended_products))
                ]
            )
            recommended_products.extend(pad)

        seen = {}
        for prod in recommended_products:
            seen[prod.id] = prod
        recommended_products = list(seen.values())[:target_n]

        serializer = self.get_serializer(recommended_products, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class ProductBySKUView(views.APIView):
    permission_classes = [permissions.AllowAny]  # Set permissions as needed

    def get(self, request, sku):
        product = get_object_or_404(
            queryset_with_is_mix_pack(Product.objects.filter(is_deleted=False)),
            sku=sku,
        )
        serializer = ProductSerializer(product)
        return Response(serializer.data, status=status.HTTP_200_OK)

class ProductSearchViewSet(CatalogFilterMixin, viewsets.ViewSet):
    """
    ViewSet za pretragu proizvoda bez keširanja.
    """
    def get_queryset(self):
        return queryset_with_is_mix_pack(
            self.get_filtered_queryset().select_related("category").order_by(
                "category__name", "nicotine"
            )
        )
    
    def list(self, request):
        queryset = self.get_queryset()
        search_query = request.query_params.get('search', None)
        min_price = request.query_params.get('min_price', None)
        max_price = request.query_params.get('max_price', None)
        currency = request.headers.get('Currency', DEFAULT_CURRENCY)  
        
        
        # if search_query:
        #     queryset = queryset.annotate(
        #         category_name_name=Concat('category__name', Value(' '), 'name', output_field=CharField())
        #     ).filter(category_name_name__icontains=search_query)
        categories = []
        if search_query:
            # Podela upita na ključne reči
            search_terms = search_query.split()
            # Filtriraj proizvode na osnovu kombinacija ključnih reči
            for term in search_terms:
                queryset = queryset.filter(
                    Q(name__icontains=term) |
                    Q(category__name__icontains=term)
                )
            # Vratite sve kategorije koje se poklapaju
            categories = (
                queryset.values('category__id', 'category__name')
                .distinct()
                .order_by('category__name')
            )
            categories = [{'id': cat['category__id'], 'name': cat['category__name']} for cat in categories]

        try:
            if min_price is not None:
                min_price = Decimal(min_price)
                min_price = convert_currency(min_price, currency, DEFAULT_CURRENCY)
                queryset = queryset.filter(price__gte=min_price)
        except InvalidOperation:
            pass  # Obradite grešku ako je potrebno

        try:
            if max_price is not None:
                max_price = Decimal(max_price)
                max_price = convert_currency(min_price, currency, DEFAULT_CURRENCY)
                queryset = queryset.filter(price__lte=max_price)
        except InvalidOperation:
            pass  # Obradite grešku ako je potrebno

        products_serializer = ProductSerializer(queryset, many=True, context={'request': request})
        return Response({
            'products': products_serializer.data,
            'categories': categories
        })

class FeaturedGroupAPIView(APIView):
    def get(self, request, slug):
        featured_group = get_object_or_404(FeaturedGroup, slug=slug)

        # ekstra vrednosti iz zaglavlja
        currency = request.headers.get('Currency', DEFAULT_CURRENCY)

        # (opciono) ako hoćeš da prefetch-uješ slike za sve proizvode:
        # featured_group = FeaturedGroup.objects.prefetch_related(
        #     Prefetch('products__images')
        # ).get(slug=slug)

        serializer = FeaturedGroupSerializer(
            featured_group,
            context={
                'request': request,
                'currency': currency,
            }
        )
        return Response(serializer.data)
    
#CART
class ViewCartView(generics.ListAPIView):
    serializer_class = CartSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        return Cart.objects.filter(user=user)
    

class AddToCartView(generics.CreateAPIView):
    queryset = CartItem.objects.all()
    serializer_class = CartItemSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        cart, _ = Cart.objects.get_or_create(user=self.request.user)
        serializer.save(cart=cart)

class UpdateCartItemView(generics.UpdateAPIView):
    queryset = CartItem.objects.all()
    serializer_class = CartItemSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return CartItem.objects.filter(cart__user=self.request.user)

class RemoveFromCartView(generics.UpdateAPIView):
    queryset = CartItem.objects.all()
    serializer_class = CartItemSerializer  # Ako je potrebno za ažuriranje
    permission_classes = [permissions.IsAuthenticated]

    def update(self, request, *args, **kwargs):
        cart_item = self.get_object()
        quantity_to_remove = request.data.get('quantity', 1)
        quantity = cart_item.quantity - quantity_to_remove

        if quantity <= 0:
            cart_item.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        else:
            cart_item.quantity = quantity
            cart_item.save()
            return Response(self.get_serializer(cart_item).data, status=status.HTTP_200_OK)
        
class SyncCartView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        user = request.user
        cart, _ = Cart.objects.get_or_create(user=user)
        local_cart_items = request.data.get('items', [])

        for item in local_cart_items:
            product_id = item.get('product_id')
            quantity = item.get('quantity', 0)

            if quantity > 0:
                cart_item, created = CartItem.objects.update_or_create(
                    cart=cart,
                    product_id=product_id,
                    defaults={'quantity': quantity}
                )

        updated_cart_items = CartItem.objects.filter(cart=cart)
        serializer = CartItemSerializer(updated_cart_items, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

