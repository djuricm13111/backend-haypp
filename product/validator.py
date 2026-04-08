from django.dispatch import receiver
from django.forms import ValidationError
from product.models import DomainMapping, SpecialOffer
from django.db.models.signals import m2m_changed

# da ne bi dozvolio kreiranje SpecialOffera sa dva ili vise proizvoda koji ne pripadaju istoj domeni
@receiver(m2m_changed, sender=SpecialOffer.products.through)
def validate_same_domain(sender, instance, action, **kwargs):
    if action == "pre_add":
        product_ids = kwargs.get('pk_set', set())
        if not product_ids:
            return
 
        domain_ids = DomainMapping.objects.filter(
            products__id__in=product_ids
        ).values_list('domain', flat=True).distinct()
        
        if domain_ids.count() > 1:
            # TODO: neki drugi nacin da ne bi vracao http status code 500 nazad na /api/admin
            raise ValidationError("Neki od odabranih proizvoda ne pripadaju istom domenu")
