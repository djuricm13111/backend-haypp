from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CategoryListView,ProductViewSet,AddToCartView, UpdateCartItemView, RemoveFromCartView, ViewCartView, SyncCartView, CategoryProductsView, ProductSearchViewSet, ProductBySKUView, SpecialOfferViewSet
from .views import FeaturedGroupAPIView


router = DefaultRouter()
router.register(r'products', ProductViewSet, basename='product')
router.register(r'search', ProductSearchViewSet, basename='product-search')
router.register(r'special-offers', SpecialOfferViewSet, basename='special-offer')
urlpatterns = [
    path('', include(router.urls)),  # Uključivanje URL-ova generisanih od strane router-a
    
    path('cart/', ViewCartView.as_view(), name='view-cart'),
    path('cart/add/', AddToCartView.as_view(), name='add-to-cart'),
    path('cart/update/<int:pk>/', UpdateCartItemView.as_view(), name='update-cart-item'),
    path('cart/remove/<int:pk>/', RemoveFromCartView.as_view(), name='remove-from-cart'),
    path('cart/sync/', SyncCartView.as_view(), name='sync-cart'),
    path('category/<slug:slug>/', CategoryProductsView.as_view(), name='category-products'),
    path('product/by-sku/<str:sku>/', ProductBySKUView.as_view(), name='product-by-sku'),
    path('categories/', CategoryListView.as_view(), name='category-list'),
    path("featured-group/<slug:slug>/", FeaturedGroupAPIView.as_view(), name="featured-group-detail"),
]

