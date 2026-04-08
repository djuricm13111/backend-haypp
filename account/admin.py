from django.contrib import admin
from .models import CustomUser, AddressBook, Order, OrderItem, Voucher, Referral, UserInteraction, PointsHistory, Blog, UserPoints, PaymentDetails, ProductSubscription, SubscriptionItem
from django.utils.html import format_html

from django.urls import path
from django.shortcuts import render
from django import forms
from modeltranslation.admin import TranslationAdmin


# Register your models here.
admin.site.register(CustomUser)
@admin.register(AddressBook)
class AddressBookAdmin(admin.ModelAdmin):
    list_display = ('user', 'street', 'city', 'country', 'is_primary')  # Dodajte polja koja želite da prikažete
    list_filter = ('is_primary', 'user')  # Omogućite filtriranje po primarnoj adresi i korisniku
    search_fields = ('user__email', 'street', 'city', 'country')  # Omogućite pretragu po email-u korisnika i adresi

    def get_queryset(self, request):
        # Prilagođen QuerySet za sortiranje adresa tako da primarne adrese budu prvo
        qs = super().get_queryset(request)
        return qs.order_by('-is_primary', 'user', 'city')
class SubscriptionItemInline(admin.TabularInline):
    model = SubscriptionItem
    extra = 0


@admin.register(ProductSubscription)
class ProductSubscriptionAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "interval_days", "status", "next_order_at", "created_at")
    list_filter = ("status", "interval_days")
    search_fields = ("user__email",)
    inlines = [SubscriptionItemInline]


admin.site.register(Referral)
admin.site.register(Voucher)


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0  # Ne prikazuj dodatne prazne redove za nove stavke
    fields = ('product', 'special_offer', 'quantity', 'price', 'is_shipped', 'shipped_at')
    readonly_fields = ('price',)  # Uklonite 'product' i 'quantity' iz readonly_fields
    can_delete = True  # Omogućite brisanje stavki direktno iz narudžbine

from django import forms
from django.utils.safestring import mark_safe
import matplotlib.pyplot as plt
import base64
import io
import pandas as pd
import logging
import matplotlib.dates as mdates
from django.utils import timezone
import calendar
logging.getLogger('matplotlib.font_manager').setLevel(logging.ERROR)
logging.getLogger('PIL').setLevel(logging.ERROR)
logging.getLogger('matplotlib').setLevel(logging.ERROR)

class SalesReportForm(forms.Form):
    today = timezone.now().date()
    first_day_of_month = today.replace(day=1)
    last_day_of_month = today.replace(day=calendar.monthrange(today.year, today.month)[1])
    
    start_date = forms.DateField(widget=forms.SelectDateWidget, initial=first_day_of_month)
    end_date = forms.DateField(widget=forms.SelectDateWidget, initial=last_day_of_month)
    chart_type = forms.ChoiceField(choices=[('line', 'Line Chart'), ('bar', 'Bar Chart')])



def get_sales_data(start_date, end_date):
    orders = Order.objects.filter(created_at__range=[start_date, end_date])
    data = []
    cross_revenue = 0
    shipping = 0
    net_revenue = 0

    for order in orders:
        cross_revenue += order.total_price.amount
        shipping += order.shipping_cost.amount
        net_revenue += order.total_price.amount - order.shipping_cost.amount
        for item in order.order_items.all():
            product_name =item.product.category.name  + ' ' +  item.product.name  if item.product else item.special_offer.name
            category_name = item.product.category.name if item.product else 'Special Offer'
            data.append({
                'order_id': order.id,
                'product_name': product_name,
                'category_name': category_name,
                'quantity': item.quantity,
                'price': item.price.amount,
                'total_price': order.total_price.amount,
                'created_at': order.created_at
            })
    
    df = pd.DataFrame(data)

    # Calculating additional metrics
    df['day'] = df['created_at'].dt.date
    daily_sales = df.groupby('day')['total_price'].sum()
    max_sales_date = daily_sales.idxmax()
    max_sales_value = daily_sales.max()
    min_sales_date = daily_sales.idxmin()
    min_sales_value = daily_sales.min()
    median_sales_value = daily_sales.median()

    summary = {
        'cross_revenue': cross_revenue,
        'shipping': shipping,
        'net_revenue': net_revenue,
        'max_sales_date': max_sales_date,
        'max_sales_value': max_sales_value,
        'min_sales_date': min_sales_date,
        'min_sales_value': min_sales_value,
        'median_sales_value': median_sales_value
    }
    return df, summary

def generate_date_range(start_date, end_date):
    return pd.date_range(start=start_date, end=end_date)

def plot_sales_data(df, start_date, end_date, chart_type='line'):
    plt.style.use('ggplot')

    df['day'] = df['created_at'].dt.date
    daily_sales = df.groupby('day')['total_price'].sum()

    all_days = generate_date_range(start_date, end_date)
    all_days_df = pd.DataFrame(all_days, columns=['day'])
    all_days_df['day'] = all_days_df['day'].dt.date

    daily_sales = all_days_df.set_index('day').join(daily_sales, how='left').fillna(0)
    
    fig, axes = plt.subplots(nrows=2, ncols=1, figsize=(15, 9), gridspec_kw={'height_ratios': [2, 1]})

    if chart_type == 'line':
        axes[0].plot(daily_sales.index, daily_sales['total_price'].values, color='blue', linestyle='-', linewidth=2)
    elif chart_type == 'bar':
        axes[0].bar(daily_sales.index, daily_sales['total_price'].values, color='blue')
    
    axes[0].set_title('Daily Sales', fontsize=16, fontweight='bold')
    axes[0].set_xlabel('Day', fontsize=14, fontweight='bold')
    axes[0].set_ylabel('Total Sales', fontsize=14, fontweight='bold')
    axes[0].grid(True, linestyle='--', alpha=0.7)
    axes[0].xaxis.set_major_locator(mdates.DayLocator(interval=5))
    axes[0].xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))

    category_sales = df.groupby('category_name')['quantity'].sum()
    
    # Subplot grid for the second row
    subfig = fig.add_subplot(212)
    subfig1 = subfig.inset_axes([0.0, 0.0, 0.5, 1.0])
    subfig2 = subfig.inset_axes([0.55, 0.0, 0.45, 1.0])

    # Pie chart for categories
    category_sales.plot(kind='pie', ax=subfig1, autopct='%1.1f%%', startangle=90)
    subfig1.set_title('Sales by Category', fontsize=14, fontweight='bold')
    subfig1.set_ylabel('')

    # Pie chart for the top products in the best selling category
    best_category = category_sales.idxmax()
    best_category_df = df[df['category_name'] == best_category]
    best_category_products = best_category_df.groupby('product_name')['quantity'].sum()
    best_category_products.plot(kind='pie', ax=subfig2, autopct='%1.1f%%', startangle=90)
    subfig2.set_title(f'Top Products in {best_category}', fontsize=14, fontweight='bold')
    subfig2.set_ylabel('')
    subfig2.set_facecolor('none')  # Remove background color

    plt.tight_layout()
    return fig
def fig_to_base64(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format='png')
    buf.seek(0)
    image_base64 = base64.b64encode(buf.read()).decode('utf-8')
    return image_base64

    


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('order_id', 'user_email', 'total_price_with_currency', 'order_status', 'payment_method', 'created_at')
    list_filter = ('order_status', 'payment_method', 'created_at')
    search_fields = ('user__email', 'id', 'customer_order_id')
    inlines = [OrderItemInline]
    readonly_fields = (
        'formatted_address',
        'customer_order_id',
        'created_at',
        'updated_at',
    )
    fieldsets = (
        (None, {
            'fields': (
                'customer_order_id',
                'user',
                'order_status',
                'payment_method',
                'transport_method',
                'subtotal',
                'shipping_cost',
                'total_price',
                'note',
                'created_at',
                'updated_at',
            ),
        }),
        ('Shipping', {
            'fields': ('formatted_address', 'address'),
        }),
    )

    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = 'User Email'

    def order_id(self, obj):
        return f"Order #{obj.id}"
    order_id.short_description = 'Order ID'

    def total_price_with_currency(self, obj):
        return format_html(f"{obj.total_price} {obj.total_price.currency}")
    total_price_with_currency.short_description = 'Total Price'

    def formatted_address(self, obj):
        if not obj.address:
            return "—"
        a = obj.address
        line1 = " ".join(
            p for p in (a.street, a.street_number or "") if p
        ).strip()
        lines = []
        if line1:
            lines.append(line1)
        if a.secondary_street:
            lines.append(a.secondary_street)
        city_line = " ".join(
            p for p in (a.postal_code, a.city) if p
        ).strip()
        if city_line:
            lines.append(city_line)
        if a.country:
            lines.append(a.country)
        if a.building_number:
            lines.append(f"Building: {a.building_number}")
        if a.phone_number:
            lines.append(f"Tel: {a.phone_number}")
        if not lines:
            return "—"
        return format_html("<br>".join(lines))
    formatted_address.short_description = 'Delivery address'


    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('sales-report/', self.admin_site.admin_view(self.sales_report), name='sales-report')
        ]
        return custom_urls + urls

    def sales_report(self, request):
        if request.method == 'POST':
            form = SalesReportForm(request.POST)
            if form.is_valid():
                start_date = form.cleaned_data['start_date']
                end_date = form.cleaned_data['end_date']
                chart_type = form.cleaned_data['chart_type']
                df, summary = get_sales_data(start_date, end_date)
                fig = plot_sales_data(df, start_date, end_date, chart_type)
                image_base64 = fig_to_base64(fig)
                context = dict(
                    self.admin_site.each_context(request),
                    form=form,
                    image_base64=image_base64,
                    summary=summary
                )
                return render(request, 'admin/sales_report.html', context)
        else:
            form = SalesReportForm()

        context = dict(
            self.admin_site.each_context(request),
            form=form,
            image_base64=None,
            summary=None
        )
        return render(request, 'admin/sales_report.html', context)


admin.site.register(UserPoints)
admin.site.register(PointsHistory)
admin.site.register(UserInteraction)
admin.site.register(PaymentDetails)
@admin.register(Blog)
class BlogAdmin(TranslationAdmin):
    list_display = ['title']

    class Media:
        js = (
            'https://ajax.googleapis.com/ajax/libs/jquery/3.5.1/jquery.min.js',  # Ažurirana verzija
            'https://ajax.googleapis.com/ajax/libs/jqueryui/1.12.1/jquery-ui.min.js',  # Ažurirana verzija
            'modeltranslation/js/tabbed_translation_fields.js',
        )
        css = {
            'all': ('modeltranslation/css/tabbed_translation_fields.css',),
        }


