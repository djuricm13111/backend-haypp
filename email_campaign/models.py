from django.db import models
from django.utils import timezone
from datetime import timedelta
from django.conf import settings
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from product.models import Product, SpecialOffer






class ProductPromotion(models.Model):
    def get_remaining_time(self):
        #if self.start_date:
        #    return None  # Ako je posatavljen start date to znaci da je neki event 2/3 dana npr.

        now = timezone.now()
        remaining_time = self.end_date - now

        if remaining_time.total_seconds() <= 0:
            return None  # Promocija je istekla

        # Izračunaj dane, sate, minute i sekunde
        days, remainder = divmod(remaining_time.total_seconds(), 86400)  # 86400 sekundi u danu
        hours, remainder = divmod(remainder, 3600)  # 3600 sekundi u satu
        minutes, seconds = divmod(remainder, 60)

        return {
            'days': int(days),
            'hours': int(hours),
            'minutes': int(minutes),
            'seconds': int(seconds),
        }
    TEMPLATE_CHOICES = [
        ('promo', 'Promotional Email'),
        ('new_arrival', 'New Arrival Email'),
        ('discount', 'Discount Email'),
        # Dodajte još opcija ako je potrebno
    ]

    products = models.ManyToManyField(Product, related_name='promotions', null=True, blank=True)
    title =  models.CharField(max_length=1024, null=True, blank=True)
    subtitle =  models.CharField(max_length=1024, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    start_date = models.DateTimeField(null=True, blank=True)
    end_date = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=False)
    email_template = models.CharField(max_length=50, choices=TEMPLATE_CHOICES, default='promo')

    def __str__(self):
        return ', '.join([f"{product.category.name} {product.name}" for product in self.products.all()])

    def eligible_users(self):
        from account.models import CustomUser
        if not hasattr(self, 'criteria') or not self.criteria:
            return CustomUser.objects.none()  # Ako nema kriterijuma, nema ni eligible korisnika
        
        criteria = self.criteria
        last_order_threshold = timezone.now() - timedelta(days=criteria.days_since_last_order)
        return CustomUser.objects.filter(total_orders__gt=criteria.min_orders, last_order_date__lt=last_order_threshold)

    def send_promotion_emails(self):
        from .tasks import send_promotion_email_task
        products_data = []
        for product in self.products.all():
            primary_image = product.images.filter(is_primary=True).first()
            product_data = {
                'name': product.name,
                'category_name': product.category.name,
                'image': primary_image.get_image_url() if primary_image else None
            }
            products_data.append(product_data)
        context = {
            'title': self.title,
            'subtitle': self.subtitle,
            'description': self.description,
            'remaining_time': self.get_remaining_time(),
            'email_template': self.email_template,
            'products':products_data
        }
        if not self.is_active:
            send_promotion_email_task.delay(settings.DEFAULT_FROM_EMAIL, context, self.email_template)
            self.is_active = True
            self.save()
            return
        users = self.eligible_users()
        for user in users:
            send_promotion_email_task.delay(user.email, context, self.email_template)

class PromotionCriteria(models.Model):
    promotion = models.OneToOneField(ProductPromotion, on_delete=models.CASCADE, related_name='criteria')
    min_orders = models.IntegerField(default=5)
    days_since_last_order = models.IntegerField(default=14)

    def __str__(self):
        product_names = ', '.join([f"{product.category.name} {product.name}" for product in self.promotion.products.all()])
        return f"Criteria for promotion: {product_names}"


class Subscriber(models.Model):
    email = models.EmailField(unique=True)
    subscribed_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.email