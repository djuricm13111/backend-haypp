from django.db import models
from enum import Enum
from django.core.validators import MaxValueValidator, MinValueValidator
from django.utils.translation import gettext_lazy as _
from djmoney.models.fields import MoneyField
from decimal import Decimal
from django.conf import settings
from django.utils import timezone
from django.utils.text import slugify
from scripts.currency_converter import DEFAULT_CURRENCY
from django.core.exceptions import ValidationError

#promotion

from django.utils import timezone
from datetime import timedelta
# Create your models here.


class ProductQuerySet(models.QuerySet):
    def active(self):
        """Metoda za filtriranje samo aktivnih (neobrisanih) proizvoda."""
        return self.filter(is_deleted=False)
    def best_selling(self):
        """Metoda za dohvatanje najprodavanijih proizvoda."""
        return self.order_by('-sales_count')

    def by_category(self, category_name):
        """Metoda za filtriranje proizvoda po kategoriji."""
        return self.filter(category__name=category_name)

class ProductManager(models.Manager):
    def get_queryset(self):
        return ProductQuerySet(self.model, using=self._db).active()

    def best_selling(self, *args, **kwargs):
        """Delegira poziv na best_selling metodu QuerySet-a."""
        return self.get_queryset().best_selling(*args, **kwargs)

    def by_category(self, *args, **kwargs):
        """Delegira poziv na by_category metodu QuerySet-a."""
        return self.get_queryset().by_category(*args, **kwargs)
    
    def all_including_deleted(self):
        """Vraća sve proizvode, uključujući i one koji su obrisani."""
        return ProductQuerySet(self.model, using=self._db)

    # Delegirajte dodatne metode po potrebi
class ProductState(models.TextChoices):
    IN_STOCK = 'in_stock', 'Na stanju'
    ON_REQUEST = 'on_request', 'Dostupno na upit'
    OUT_OF_STOCK = 'out_of_stock', 'Nema na stanju'


class Category(models.Model):
    name = models.CharField(max_length=50)
    slug = models.SlugField(unique=True, blank=True, null=True)
    color = models.CharField(max_length=7, blank=True, null=True)
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super(Category, self).save(*args, **kwargs)
    def __str__(self):
        return self.name
    

PRICE_CURRENCIES = (
    ('USD', 'US Dollar'),
    ('EUR', 'Euro'),
)

class Product(models.Model):
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True, default="", blank=True)

    # sada mogu ostati prazni i naknadno se popuniti
    nicotine = models.DecimalField(
        max_digits=4,
        decimal_places=1,
        validators=[MinValueValidator(0.0)],
        null=True,
        blank=True,
    )
    price = MoneyField(
        max_digits=14,
        decimal_places=2,
        default_currency=DEFAULT_CURRENCY,
        null=True,
        blank=True,
    )
    discounted_price = MoneyField(
        max_digits=14,
        decimal_places=2,
        default_currency=DEFAULT_CURRENCY,
        null=True,
        blank=True,
    )

    currency = models.CharField(
        max_length=3,
        choices=PRICE_CURRENCIES,
        default=DEFAULT_CURRENCY,
    )
    recommended = models.BooleanField(default=False)
    pouches_per_can = models.IntegerField(blank=True, null=True)
    format = models.CharField(max_length=50, blank=True, null=True)
    flavor = models.CharField(max_length=50, blank=True, null=True)
    net_weight = models.DecimalField(max_digits=5, decimal_places=1, blank=True, null=True)
    manufacturer = models.CharField(max_length=100, blank=True, null=True)
    sku = models.CharField(max_length=50, null=True, blank=True, unique=True)

    badge_text = models.CharField(max_length=30, blank=True, null=True)

    sales_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False)

    state = models.CharField(
        max_length=20,
        choices=ProductState.choices,
        default=ProductState.IN_STOCK,
    )
    stock = models.PositiveIntegerField(default=0)

    objects = ProductManager()

    def clean(self):
        nic = self.nicotine
        if nic is None:
            return
        max_n = getattr(settings, 'MAX_NICOTINE_MG_PER_POUCH', 999)
        if nic > max_n:
            raise ValidationError(
                f"Proizvod ima {nic} mg nikotina po kesici, a dozvoljeni maksimum je {max_n} mg."
            )

    def save(self, *args, **kwargs):
        if not self.slug:
            # automatsko postavljanje slug-a
            self.slug = slugify(f"{self.name}")
        super().save(*args, **kwargs)

    def _mix_availability(self):
        """
        Za proizvod koji ima mix_lines: (broj kompletnih bundle-ova, state).
        None ako nije mix pack.
        """
        lines = list(self.mix_lines.select_related("component_product").all())
        if not lines:
            return None
        effective = None
        for line in lines:
            c = line.component_product
            if c.is_deleted or c.state != ProductState.IN_STOCK:
                eligible = 0
            else:
                q = line.quantity or 1
                eligible = c.stock // q
            effective = eligible if effective is None else min(effective, eligible)
        effective = max(0, effective if effective is not None else 0)
        st = (
            ProductState.IN_STOCK
            if effective > 0
            else ProductState.OUT_OF_STOCK
        )
        return effective, st

    def effective_mix_bundle_count(self):
        """Broj prodajnih bundle jedinica; None ako proizvod nije mix pack."""
        r = self._mix_availability()
        return None if r is None else r[0]

    def display_catalog_state(self):
        """Stanje za API / katalog: mix pack zavisi od komponenti."""
        r = self._mix_availability()
        if r is None:
            return self.state
        return r[1]

    def refresh_mixpack_from_components(self, save=True):
        """Sinhronizuje Product.stock i Product.state sa komponentama (samo mix packovi)."""
        r = self._mix_availability()
        if r is None:
            return
        effective, st = r
        if save:
            Product._base_manager.filter(pk=self.pk).update(
                stock=effective,
                state=st,
            )
        else:
            self.stock = effective
            self.state = st

    def __str__(self):
        return f"{self.name}"


class MixPackLine(models.Model):
    """
    Jedan red bundle-a: mix_product (bundle SKU) sadrži quantity × component_product.
    Stanje bundle-a = min(component.stock // quantity) dok su sve komponente in_stock.
    """

    mix_product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="mix_lines",
    )
    component_product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="mix_used_in",
    )
    quantity = models.PositiveIntegerField(
        default=1,
        help_text="Koliko komada ove komponente treba za jedan bundle (npr. 10 limenki).",
    )

    class Meta:
        verbose_name = "Mix pack linija"
        verbose_name_plural = "Mix pack linije"
        constraints = [
            models.UniqueConstraint(
                fields=["mix_product", "component_product"],
                name="product_mixpack_unique_component",
            ),
        ]

    def clean(self):
        if self.component_product_id and self.mix_product_id:
            if self.component_product_id == self.mix_product_id:
                raise ValidationError(
                    "Mix pack ne može da bude komponenta sam sebi."
                )

    def __str__(self):
        return f"{self.mix_product.slug} ← {self.quantity}× {self.component_product.slug}"


def refresh_all_mixpack_bundles():
    """Pozovi nakon masovnog ažuriranja stanja komponenti (npr. GS skripta)."""
    mix_ids = MixPackLine.objects.values_list("mix_product_id", flat=True).distinct()
    for pid in mix_ids:
        p = Product._base_manager.get(pk=pid)
        p.refresh_mixpack_from_components(save=True)


import os

IMAGE_PREFIX = 'https://snus-s3.s3.eu-north-1.amazonaws.com/wholesale'

class ProductImage(models.Model):
    product = models.ForeignKey(Product, related_name='images', on_delete=models.CASCADE)
    original_image_key = models.CharField(max_length=1024, null=True, blank=True)  # Ključ originalne slike na S3
    is_primary = models.BooleanField(default=False)
    def _get_extension_folder(self):
        """
        Dobija podfolder na osnovu ekstenzije originalne slike (npr. 'PNG', 'JPG', 'WEBP').
        """
        if self.original_image_key:
            ext = os.path.splitext(self.original_image_key)[1][1:]  # Ekstenzija bez tačke
            return ext.upper()  # Pretvara ekstenziju u velika slova
        return ''

    def get_image_url(self):
        return f'{IMAGE_PREFIX}/{self.original_image_key}'

    def get_thumbnail_image_url(self):
        return f'{IMAGE_PREFIX}/{self.original_image_key}'

    def get_large_image_url(self):
        return f'{IMAGE_PREFIX}/{self.original_image_key}'
    def __str__(self):
        return f" {self.product.name}"


class CategoryImage(models.Model):
    category = models.ForeignKey(Category, related_name='images', on_delete=models.CASCADE)
    desktop_image_key = models.CharField(max_length=1024, null=True, blank=True)  # Key for desktop image on S3
    mobile_image_key = models.CharField(max_length=1024, null=True, blank=True)   # Key for mobile image on S3
    def __str__(self):
        return f"{self.category.name}"

class CartItem(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.IntegerField(default=1)
    added_on = models.DateTimeField(auto_now_add=True)
    def __str__(self):
        return f" {self.product.name} - qty: {self.quantity}"

class Cart(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    items = models.ManyToManyField(CartItem, blank=True)
    created_on = models.DateTimeField(auto_now_add=True)
    def __str__(self):
        return f"{self.user.first_name} {self.user.last_name} - {self.user.email}"
    

class FeaturedGroup(models.Model):
    name = models.CharField(max_length=255)  # Naziv grupe
    slug = models.SlugField(unique=True, blank=True, null=True)  # Jedinstveni identifikator
    products = models.ManyToManyField("Product")  # Povezivanje proizvoda

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)  # Automatski generisanje sluga
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name
