from django.db import models

# Create your models here.
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.utils import timezone
from product.models import Product, SpecialOffer
from djmoney.models.fields import MoneyField
from decimal import Decimal
from django.utils.translation import gettext_lazy as _
import secrets
import string
from django.core.exceptions import ValidationError
import uuid
from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver
from scripts.currency_converter import DEFAULT_CURRENCY
from django.utils.text import slugify
from djmoney.money import Money
import random
import datetime
from .tasks import send_verification_code
from backend.settings import DEFAULT_DOMAIN
from django.utils.crypto import get_random_string

import logging
logger = logging.getLogger(__name__)
class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, domain=None, **extra_fields):
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)
        if not email:
            raise ValueError('The Email must be set')

        email = self.normalize_email(email)
        domain = domain or DEFAULT_DOMAIN  
        user = self.model(email=email, domain=domain, **extra_fields)
        user.set_password(password)
        user.is_active = True
        user.is_email_verified = False
        user.save()
        return user

    def create_superuser(self, email, password=None, domain=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(email, password, domain=domain, **extra_fields)

    def generate_verification_code(self):
        return random.randint(1000, 9999)  # Generiše četvorocifreni kod

class CustomUser(AbstractBaseUser, PermissionsMixin):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(blank=False, default='', unique=True)
    first_name = models.CharField(max_length=30, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    phone_number = models.CharField(max_length=15, blank=True, null=True)

    # Track the domain where the user was created
    domain = models.CharField(max_length=255, blank=True, null=True)
    
    is_active = models.BooleanField(default=True)  # Korisnik nije aktivan dok ne potvrdi email
    is_email_verified = models.BooleanField(default=False)  # Polje za potvrdu emaila
    verification_code = models.CharField(max_length=4, blank=True, null=True)  # Verifikacioni kod
    verification_code_expires_at = models.DateTimeField(null=True, blank=True)  # Vreme isteka verifikacionog koda

    is_superuser = models.BooleanField(default=False)
    is_staff = models.BooleanField(default=False)

    date_joined = models.DateTimeField(default=timezone.now)
    last_login = models.DateTimeField(blank=True, null=True)

    #ME
    referral_code = models.CharField(max_length=100, unique=True, blank=True, null=True)

    #
    total_orders = models.IntegerField(default=0)
    last_order_date = models.DateTimeField(null=True, blank=True)

    objects = CustomUserManager()

    USERNAME_FIELD = 'email'
    EMAIL_FIELD = 'email'
    REQUIRED_FIELDS = []


    class Meta:
        verbose_name = 'User'
        verbose_name_plural = 'Users'
    def get_full_name(self):
        # Vraća puno ime korisnika
        full_name = f'{self.first_name} {self.last_name}'
        return full_name.strip()

    def get_short_name(self):
        # Vraća kratko ime, ili email do @
        return self.first_name or self.email.split('@')[0]
    
    def save(self, *args, **kwargs):
        if not self.referral_code:
            self.referral_code = self.generate_referral_code()

        domain = getattr(self, 'domain', DEFAULT_DOMAIN)

        super().save(*args, **kwargs)
        
        # Ensure UserPoints exists for the user and domain
        UserPoints.objects.get_or_create(user=self, domain=domain)

    def generate_referral_code(self):
        # Generišite siguran nasumičan string od 10 karaktera koji će služiti kao referral kod
        # Kombinacija velikih slova, malih slova i cifara osigurava dovoljnu kompleksnost
        characters = string.ascii_letters + string.digits
        referral_code = ''.join(secrets.choice(characters) for _ in range(10))

        # Proverite da li generisani kod već postoji u bazi
        if CustomUser.objects.filter(referral_code=referral_code).exists():
            # Ako postoji, rekurzivno pozovite funkciju dok ne dobijete jedinstveni kod
            return self.generate_referral_code()
        return referral_code
    
    


class UserPoints(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='user_points')
    domain = models.CharField(max_length=255)  # The domain where points/levels apply
    vip_points = models.DecimalField(max_digits=12, decimal_places=6, default=0)  # Points that don't reset
    points = models.DecimalField(max_digits=12, decimal_places=6, default=0)  # Points that may reset
    level = models.IntegerField(default=1)  # User's level for this domain

    def __str__(self):
        return f'{self.user.email} - {self.domain} - Points: {self.points}'

    class Meta:
        unique_together = ('user', 'domain')  # Ensures uniqueness per user/domain combination

    def add_points(self, points):
        self.points += points
        self.vip_points += points
        self.save()
        self.check_level_up()

    def check_level_up(self):
        # Checks if the user should level up based on their VIP points
        if self.vip_points >= 150 and self.level < 3:
            self.level = 3  # Diamond level
        elif self.vip_points >= 75 and self.level < 2:
            self.level = 2  # Gold level
        self.save()

    
class AddressType(models.TextChoices):
    HOME = 'Home', _('Home')
    WORK = 'Work', _('Work')
    OTHER = 'Other', _('Other')

class AddressBook(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='addresses')
    country = models.CharField(max_length=100)
    city = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=10)
    street = models.CharField(max_length=255)
    street_number = models.CharField(max_length=10, blank=True, null=True)
    secondary_street = models.CharField(max_length=255, blank=True, null=True) 
    building_number = models.CharField(max_length=10, blank=True, null=True)
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    type = models.CharField(max_length=20, choices=AddressType.choices, default=AddressType.HOME)

    # Geolokacijski podaci
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)

    is_primary = models.BooleanField(default=False, verbose_name='Primary Address for Shipping')

    def save(self, *args, **kwargs):
        if self.is_primary:
            # Resetujte sve prethodne primarne adrese ovog korisnika
            AddressBook.objects.filter(user=self.user, is_primary=True).update(is_primary=False)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.street}, {self.city}, {self.country}"
    

class Referral(models.Model):
    referrer = models.ForeignKey(CustomUser, related_name='referrals_made', on_delete=models.CASCADE)
    referred = models.ForeignKey(CustomUser, related_name='referred_by', on_delete=models.CASCADE)
    has_completed_first_order = models.BooleanField(default=False) 
    created_at = models.DateTimeField(auto_now_add=True)
    #has_made_purchase = models.BooleanField(default=False)  # Da li je preporučeni korisnik izvršio kupovinu

    def __str__(self):
        return f"{self.referrer.email} referred {self.referred.email}"

class Voucher(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='vouchers')
    code = models.UUIDField(default=uuid.uuid4, editable=False, unique=True) 
    points = models.DecimalField(max_digits=12, decimal_places=6)
    amount = MoneyField(max_digits=14, decimal_places=2, default_currency=DEFAULT_CURRENCY)
    is_used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.amount} Voucher ({self.points} points) for {self.user.email}"


class OrderStatus(models.TextChoices):
    PENDING = 'Pending', _('Pending')
    SHIPPED = 'Shipped', _('Shipped')
    DELIVERED = 'Delivered', _('Delivered')
    CANCELED = 'Canceled', _('Canceled')
    PAID = 'Paid', _('Paid')

class PaymentMethod(models.TextChoices):
    COD = 'cod', _('Cash on Delivery')
    CARD = 'card', _('Credit Card')
    PAYPAL = 'paypal', _('PayPal')

class PaymentDetails(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE)
    stripe_customer_id = models.CharField(max_length=255, unique=True)
    payment_method_id = models.CharField(max_length=255, blank=True, null=True)
    email = models.EmailField()

    def __str__(self):
        return f"{self.user.email} - {self.payment_method_id}"
    
class TransportMethod(models.TextChoices):
    DHL_STANDARD = 'DHL Standard', _('DHL Standard')
    POST_AT = 'Post - AT', _('Post - AT')
    DHL_EXPRESS_SAVER = 'DHL Express Saver', _('DHL Express Saver')

class SubscriptionStatus(models.TextChoices):
    ACTIVE = 'active', _('Active')
    CANCELLED = 'cancelled', _('Cancelled')


class ProductSubscription(models.Model):
    """Ponavljajuća isporuka: prva narudžbina odmah, sledeće po intervalu (dani)."""
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='product_subscriptions')
    interval_days = models.PositiveSmallIntegerField()
    status = models.CharField(max_length=20, choices=SubscriptionStatus.choices, default=SubscriptionStatus.ACTIVE)
    address = models.ForeignKey(AddressBook, on_delete=models.PROTECT, related_name='product_subscriptions')
    payment_method = models.CharField(max_length=20, choices=PaymentMethod.choices, default=PaymentMethod.COD)
    transport_method = models.CharField(max_length=20, choices=TransportMethod.choices, default=TransportMethod.POST_AT)
    note = models.TextField(blank=True, null=True)
    next_order_at = models.DateTimeField()
    cancelled_at = models.DateTimeField(null=True, blank=True)
    domain = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Subscription #{self.pk} {self.user.email} every {self.interval_days}d"


class SubscriptionItem(models.Model):
    subscription = models.ForeignKey(ProductSubscription, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ['id']
        constraints = [
            models.UniqueConstraint(
                fields=['subscription', 'product'],
                name='account_subscriptionitem_subscription_product_uniq',
            ),
        ]

    def __str__(self):
        return f"{self.product_id} x{self.quantity} (sub {self.subscription_id})"


class Order(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='orders')
    address = models.ForeignKey(AddressBook, on_delete=models.SET_NULL, null=True, blank=True, related_name='deliveries')
    subscription = models.ForeignKey(
        'ProductSubscription',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='orders',
    )
    subtotal = MoneyField(max_digits=14, decimal_places=2, default_currency=DEFAULT_CURRENCY, null=True)
    total_price = MoneyField(max_digits=14, decimal_places=2, default_currency=DEFAULT_CURRENCY, null=True)
    shipping_cost = MoneyField(max_digits=10, decimal_places=2, default_currency=DEFAULT_CURRENCY, default=0)

    order_status = models.CharField(max_length=20, choices=OrderStatus.choices, default=OrderStatus.PENDING)

    payment_method = models.CharField(max_length=20, choices=PaymentMethod.choices, default=PaymentMethod.COD)
    transport_method = models.CharField(max_length=20, choices=TransportMethod.choices, default=TransportMethod.DHL_STANDARD)

    note = models.TextField(blank=True, null=True)  
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    purchase_date = models.DateTimeField(default=timezone.now)

    domain = models.CharField(max_length=255, blank=True, null=True)
    added_points = models.BooleanField(default=False)
    gs = models.BooleanField(default=False)
    customer_order_id = models.CharField(max_length=20, unique=True, blank=True, null=True)


    def __str__(self):
        return f"Order #{self.customer_order_id} – {self.user.email} – {self.created_at.strftime('%Y-%m-%d')}"
    @staticmethod
    def generate_customer_order_id():
        return f"ID-{get_random_string(length=8, allowed_chars='ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789')}"

    def save(self, *args, **kwargs):
        if not self.customer_order_id:
            while True:
                new_id = self.generate_customer_order_id()
                if not Order.objects.filter(customer_order_id=new_id).exists():
                    self.customer_order_id = new_id
                    break
        super().save(*args, **kwargs)

    def complete_order(self):
        if self.order_status == OrderStatus.DELIVERED:
            points_to_add = self.subtotal.amount / 100  # Ili neka druga logika za dodelu poena

            domain = self.user.domain  # Assuming domain is stored in the order

            # Retrieve or create `UserSiteData` for the user and the current domain
            user_points, created = UserPoints.objects.get_or_create(user=self.user, domain=domain)

            # Add points to the site's specific user data
            user_points.points += points_to_add
            user_points.vip_points += points_to_add
            user_points.points = round(user_points.points, 6)
            user_points.vip_points = round(user_points.vip_points, 6)
            user_points.save()

            self.added_points = True
            self.user.save()

            PointsHistory.objects.create(
                user=self.user,
                points=points_to_add,
                point_type=PointsHistory.PointType.LOYALTY,
                status=PointsHistory.Status.APPROVED,
                reason=f'Points awarded for order {self.id}'
            )
             # Proveravamo da li je korisnik referisan
            referral = Referral.objects.filter(referred=self.user).first()
            if referral:
                # Dodela zarade refereru (procenat zarade, npr. 2%)
                referral_percentage = Decimal(0.02)  # 2% zarade za referera
                referral_reward = (self.subtotal.amount * referral_percentage) / Decimal(100)

                # Retrieve or create `UserPoints` for the referrer
                referrer_user_points, created = UserPoints.objects.get_or_create(user=referral.referrer, domain=domain)
                referrer_user_points.points += referral_reward
                referrer_user_points.points = round(referrer_user_points.points, 6)
                referrer_user_points.save()

                # Kreiramo zapis u istoriji poena za referera
                PointsHistory.objects.create(
                    user=referral.referrer,
                    points=referral_reward,
                    point_type=PointsHistory.PointType.REFERRAL,
                    status=PointsHistory.Status.APPROVED,
                    reason=f'Referral points for order {self.id}'
                )

                # Obeležavamo da je referalni korisnik završio prvu narudžbu
                if not referral.has_completed_first_order:
                    referral.has_completed_first_order = True
                    referral.save()
            self.save()
    def revoke_points(self):
        if self.order_status !=  OrderStatus.DELIVERED and self.added_points:
            points_to_deduct = self.subtotal.amount / 100  # Ili neka druga logika za oduzimanje poena

            self.user.vip_points -= points_to_deduct
            self.user.vip_points = round(self.user.vip_points, 6)  
            self.user.points -= points_to_deduct
            self.user.points = round(self.user.points, 6)

            domain = self.user.domain
            user_points = UserPoints.objects.get(user=self.user, domain=domain)
            user_points.points -= points_to_deduct
            user_points.vip_points -= points_to_deduct
            user_points.points = round(user_points.points, 6)
            user_points.vip_points = round(user_points.vip_points, 6)
            user_points.save()
            
            self.added_points = False
            self.user.save()

            PointsHistory.objects.create(
                user=self.user,
                points=-points_to_deduct,
                point_type=PointsHistory.PointType.REDEEM,
                status=PointsHistory.Status.APPROVED,
                reason=f'Points deducted for canceled order {self.id}'
            )
            # Proveravamo da li je korisnik referisan
            referral = Referral.objects.filter(referred=self.user).first()
            if referral:
                # Oduzimanje poena refereru (procenat kao u `complete_order`)
                referral_percentage = Decimal(0.02)  # 2% zarade za referera
                referral_reward = (self.subtotal.amount * referral_percentage) / Decimal(100) 

                referral.referrer.points -= referral_reward
                referral.referrer.points = round(referral.referrer.points, 6)
                referral.referrer.save()
                
                # Retrieve `UserPoints` for the referrer and domain, then deduct points
                referrer_points = UserPoints.objects.get(user=referral.referrer, domain=domain)
                referrer_points.points -= referral_reward
                referrer_points.points = round(referrer_points.points, 6)
                referrer_points.save()

                PointsHistory.objects.create(
                    user=referral.referrer,
                    points=-referral_reward,
                    point_type=PointsHistory.PointType.REDEEM,
                    status=PointsHistory.Status.APPROVED,
                    reason=f'Referral points deducted for canceled order {self.id}'
                )
            self.save()

class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='order_items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, null=True, blank=True)
    special_offer = models.ForeignKey(SpecialOffer, on_delete=models.CASCADE, null=True, blank=True)
    quantity = models.IntegerField(default=1)
    price = MoneyField(max_digits=14, decimal_places=2, default_currency=DEFAULT_CURRENCY)  # Price at the time of the order
    discounted_price = MoneyField(max_digits=14, decimal_places=2, default_currency=DEFAULT_CURRENCY, default=Money(0, DEFAULT_CURRENCY))
    is_shipped = models.BooleanField(default=False)
    shipped_at = models.DateTimeField(null=True, blank=True)

    def clean(self):
        # Ensure that exactly one of `product` or `special_offer` is set
        if (self.product is None and self.special_offer is None) or (self.product and self.special_offer):
            raise ValidationError('An OrderItem must be associated with either a Product or a SpecialOffer, but not both.')

    def save(self, *args, **kwargs):
        self.clean()  # Call the clean method to run the validation
        super(OrderItem, self).save(*args, **kwargs)

    def __str__(self):
        if self.product:
            return f" {self.product.category.name} {self.product.name} - {self.quantity}"
        else:
            return f"{self.special_offer.name} - {self.quantity}"






class PointsHistory(models.Model):
    class PointType(models.TextChoices):
        LOYALTY = 'Loyalty', ('Loyalty')
        REDEEM = 'Redeem', ('Redeem')
        REFERRAL = 'Referral', ('Referral')
        BONUS = 'Bonus', ('Bonus')
        # Dodajte druge tipove po potrebi

    class Status(models.TextChoices):
        PENDING = 'Pending', ('Pending')
        APPROVED = 'Approved', ('Approved')
        CANCELLED = 'Cancelled', ('Cancelled')
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='points_history')
    points = models.DecimalField(max_digits=12, decimal_places=6)
    point_type = models.CharField(max_length=50, choices=PointType.choices, default=PointType.LOYALTY)
    status = models.CharField(max_length=50, choices=Status.choices, default=Status.PENDING)
    reason = models.CharField(max_length=255)  # Razlog dobijanja ili trošenja poena
    date = models.DateTimeField(auto_now_add=True)  # Datum i vreme dobijanja ili trošenja poena

    class Meta:
        verbose_name = 'Points History'
        verbose_name_plural = 'Points Histories'

    def __str__(self):
        return f'{self.user.get_full_name()} {self.points} points for {self.reason}'

    def approve_points(self):
        self.status = self.Status.APPROVED
        self.save()

    def cancel_points(self):
        self.status = self.Status.CANCELLED
        self.save()





#USER ACTIVITY
class UserInteraction(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='interactions')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, null=True, blank=True, related_name='interactions')
    interaction_type = models.CharField(max_length=50)  # Tipovi kao što su 'view', 'purchase', 'search', 'rate', itd.
    details = models.JSONField(null=True, blank=True)  # Detalji kao što su product_id, search_query, rating_value, itd.
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        if self.product:
            return f"{self.user.email} - {self.product.name} - {self.interaction_type}"
        else:
            return f"{self.user.email} - {self.interaction_type}"
        


class Blog(models.Model):
    title = models.CharField(max_length=200)
    slug = models.SlugField(unique=True, blank=True, null=True)
    subtitles = models.JSONField(blank=True, default=list)
    paragraphs = models.JSONField(blank=True, default=list)
    published_date = models.DateTimeField(auto_now_add=True)
    updated_date = models.DateTimeField(auto_now=True)
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)