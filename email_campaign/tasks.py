from celery import shared_task
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.utils.translation import activate

from backend.helpers import load_email_template



@shared_task
def send_subscribe_confirmation_email(subscriber_email, language='en'):
    try:
        activate(language)
        email_texts = load_email_template('new_subscriber', language)

        html = render_to_string("new_subscriber.html", {
            'title': email_texts['title'],
            'body': email_texts['body'],
            'button_text': email_texts['button_text'],
            'footer': email_texts['footer'],
        })
        text = strip_tags(html)

        msg = EmailMultiAlternatives(
            subject=email_texts['subject'],
            body=text,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[subscriber_email],
        )
        msg.attach_alternative(html, "text/html")
        sent = msg.send(fail_silently=False)
        return {"sent": sent}
    except Exception as e:
        raise e


@shared_task
def send_promotion_email_task(email, context, template_type):
    # Mapiranje tipova šablona na lokacije HTML šablona
    template_map = {
        'promo': 'promotion.html',
        'new_arrival': 'promotion.html',
        'discount': 'new_order.html',
    }
    template_path = template_map.get(template_type, 'promotion.html')

    try:
        html_content = render_to_string(template_path, {'context': context})
        text_content = strip_tags(html_content)

        # Dozvoli i string i listu emailova
        recipients = list(email) if isinstance(email, (list, tuple, set)) else [email]

        msg = EmailMultiAlternatives(
            subject=context.get('subject', 'Your Promotion'),
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=recipients,
            # bcc=["info@snusco.com"],  # ako želiš BCC, otkomentariši
        )
        msg.attach_alternative(html_content, "text/html")
        sent = msg.send(fail_silently=False)
        return {"sent": sent}
    except Exception as e:
        return {"error": str(e)}


@shared_task
def test_task():
    print("Celery is working!")
    return "Celery is working!"
