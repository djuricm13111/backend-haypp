from django.contrib import admin
from .models import Product, Category, Cart, CartItem, SpecialOffer, ProductImage, CategoryImage, FeaturedGroup
from modeltranslation.admin import TranslationAdmin



admin.site.register(ProductImage)
admin.site.register(CategoryImage)


# Admin for Category
@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):  # Using ModelAdmin instead of TranslationAdmin
    list_display = ['name']
    search_fields = ['name']

    class Media:
        js = (
            'https://ajax.googleapis.com/ajax/libs/jquery/3.5.1/jquery.min.js',  # Updated version
            'https://ajax.googleapis.com/ajax/libs/jqueryui/1.12.1/jquery-ui.min.js',  # Updated version
        )
        css = {
            'all': ('modeltranslation/css/tabbed_translation_fields.css',),  # Can be removed if not used elsewhere
        }
@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):  # Koristi ModelAdmin umesto TranslationAdmin
    list_display = ['get_category_name', 'name', 'sku', 'price', 'state', 'stock', 'sales_count', 'is_deleted']
    list_filter = ['category', 'state', 'is_deleted']
    search_fields = ['name', 'sku']
    
    def get_category_name(self, obj):
        return obj.category.name
    get_category_name.admin_order_field = 'category'  # Omogućava sortiranje po ovom polju
    get_category_name.short_description = 'Category Name'
    
    def get_queryset(self, request):
        # Koristi _base_manager da dohvati sve proizvode, uključujući i logički obrisane
        return self.model._base_manager.all()

    class Media:
        js = (
            'https://ajax.googleapis.com/ajax/libs/jquery/3.5.1/jquery.min.js',  # Ažurirana verzija
            'https://ajax.googleapis.com/ajax/libs/jqueryui/1.12.1/jquery-ui.min.js',  # Ažurirana verzija
        )
        css = {
            'all': ('modeltranslation/css/tabbed_translation_fields.css',),
        }
# admin.site.register(CartItem)
# admin.site.register(Cart)

@admin.register(SpecialOffer)
class SpecialOfferAdmin(admin.ModelAdmin):  # Koristi ModelAdmin umesto TranslationAdmin
    list_display = ['name', 'price', 'state', 'is_deleted']
    list_filter = ['state', 'is_deleted']
    filter_horizontal = ['products']
    search_fields = ['name']
    
    def get_queryset(self, request):
        # Koristi _base_manager da dohvati sve proizvode, uključujući i logički obrisane
        return self.model._base_manager.all()

    class Media:
        js = (
            'https://ajax.googleapis.com/ajax/libs/jquery/3.5.1/jquery.min.js',  # Ažurirana verzija
            'https://ajax.googleapis.com/ajax/libs/jqueryui/1.12.1/jquery-ui.min.js',  # Ažurirana verzija
        )
        css = {
            'all': ('modeltranslation/css/tabbed_translation_fields.css',),
        }
@admin.register(FeaturedGroup)
class FeaturedGroupAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)} 
    filter_horizontal = ("products",)