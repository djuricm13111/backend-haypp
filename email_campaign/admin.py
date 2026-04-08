from django.contrib import admin

# Register your models here.
from django.urls import path, reverse
from django.http import HttpResponseRedirect
from django.utils.html import format_html
from django.shortcuts import render
from .models import ProductPromotion, PromotionCriteria, Subscriber

class PromotionCriteriaInline(admin.StackedInline):
    model = PromotionCriteria
    can_delete = False

class ProductPromotionAdmin(admin.ModelAdmin):
    list_display = ('get_products', 'is_active', 'review_button')
    inlines = [PromotionCriteriaInline]
    filter_horizontal = ('products',)  # ili filter_vertical = ('products',)

    def get_products(self, obj):
        return ", ".join([f"{product.category.name} {product.name}"  for product in obj.products.all()])
    get_products.short_description = 'Products'

    def review_button(self, obj):
        return format_html('<a class="button" href="{}">Review & Send Emails</a>', 
                           self.get_review_url(obj))
    review_button.short_description = 'Review & Send Emails'

    def get_review_url(self, obj):
        return reverse('admin:promotion-review', args=[obj.pk])

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                '<int:promotion_id>/review/',
                self.admin_site.admin_view(self.process_review),
                name='promotion-review',
            ),
        ]
        return custom_urls + urls

    def process_review(self, request, promotion_id, *args, **kwargs):
        promotion = ProductPromotion.objects.get(pk=promotion_id)
        users = promotion.eligible_users()
        if 'send_emails' in request.POST:
            promotion.send_promotion_emails()
            self.message_user(request, "Emails sent successfully.")
            return HttpResponseRedirect("..")
        return render(request, "admin/promotion_review.html", {'promotion': promotion, 'users': users})

admin.site.register(ProductPromotion, ProductPromotionAdmin)

admin.site.register(Subscriber)
