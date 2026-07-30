from django.contrib import admin
from .models import (
    Product,
    Category,
    Cart,
    CartItem,
    ProductImage,
    CategoryImage,
    FeaturedGroup,
    MixPackLine,
)
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
class MixPackLineInline(admin.TabularInline):
    model = MixPackLine
    fk_name = "mix_product"
    extra = 0
    autocomplete_fields = ("component_product",)


class HasDiscountFilter(admin.SimpleListFilter):
    title = "Ima popust"
    parameter_name = "has_discount"

    def lookups(self, request, model_admin):
        return [("yes", "Da — ima discounted_price"), ("no", "Ne")]

    def queryset(self, request, queryset):
        if self.value() == "yes":
            return queryset.filter(discounted_price__isnull=False)
        if self.value() == "no":
            return queryset.filter(discounted_price__isnull=True)
        return queryset


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    inlines = (MixPackLineInline,)
    list_display = ['get_category_name', 'name', 'sku', 'price', 'discounted_price', 'badge_text', 'state', 'stock', 'sales_count', 'is_deleted']
    list_filter = ['category', 'state', 'is_deleted', HasDiscountFilter]
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

@admin.register(FeaturedGroup)
class FeaturedGroupAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)} 
    filter_horizontal = ("products",)