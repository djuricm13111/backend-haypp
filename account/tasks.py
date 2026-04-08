from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
from celery import shared_task
from backend.helpers import load_email_template
from django.utils.translation import activate
from django.core.mail import send_mail



@shared_task
def send_verification_code(email, code, language='en'):
    activate(language)
    email_texts = load_email_template('verification', language)

    context = {
        'code': code,
        'title': email_texts['title'],
        'code_label': email_texts['code_label'],
        'body': email_texts['body'],
        'thanks': email_texts['thanks'],
        'team': email_texts['team']
    }

    try:
        html = render_to_string("verification.html", context)
        text = strip_tags(html)

        msg = EmailMultiAlternatives(
            subject=email_texts['title'],
            body=text,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[email],
        )
        msg.attach_alternative(html, "text/html")
        sent = msg.send(fail_silently=False)

        return {"sent": sent}
    except Exception as e:
        raise e


@shared_task
def send_order_confirmation_email(email, data, language='en'):
    try:
        activate(language)
        email_texts = load_email_template('new_order', language)

        # Zaokruživanje cena
        data['subtotal'] = round(data['subtotal'], 2)
        data['shipping_cost'] = round(data['shipping_cost'], 2)
        data['total_price'] = round(data['total_price'], 2)
        if 'original_price' in data:
            data['original_price'] = round(data['original_price'], 2)
        if 'discount_price' in data:
            data['discount_price'] = round(data['discount_price'], 2)

        greeting_text = email_texts['greeting'].format(first_name=data['first_name'])

        subscription_banner_body = ""
        has_subscription = bool(data.get("subscription"))
        if has_subscription:
            subd = data["subscription"]
            subscription_banner_body = email_texts.get(
                "subscription_banner_body",
                "This order is part of your subscription: every {days} days. Next automatic order: {date}.",
            ).format(
                days=subd["interval_days"],
                date=subd.get("next_order_at_display") or "—",
            )

        context = {
            'title': email_texts['title'],
            'greeting': greeting_text,
            'has_subscription': has_subscription,
            'subscription_banner_title': email_texts.get(
                'subscription_banner_title', 'Auto-reorder'
            ),
            'subscription_banner_body': subscription_banner_body,
            'order_summary': email_texts['order_summary'],
            'order_id': email_texts['order_id'],
            'subtotal': email_texts['subtotal'],
            'shipping': email_texts['shipping'],
            'taxes': email_texts['taxes'],
            'total': email_texts['total'],
            'customer_info': email_texts['customer_info'],
            'delivery_address': email_texts['delivery_address'],
            'payment_method': email_texts['payment_method'],
            'original_price': email_texts.get('original_price'),
            'discount_price': email_texts.get('discount_price'),
            'view_order': email_texts['view_order'],
            'data': data
        }

        html = render_to_string('new_order_1.html', context)
        text = strip_tags(html)

        msg = EmailMultiAlternatives(
            subject=email_texts['subject'],
            body=text,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[email],
            bcc=["uros@snusco.com", "snusco.com@gmail.com"],  # zadržano BCC
        )
        msg.attach_alternative(html, "text/html")
        sent = msg.send(fail_silently=False)

        return {"sent": sent}
    except Exception as e:
        raise e


@shared_task
def send_reset_password_email(email, reset_link, language, first_name):
    activate(language)
    email_texts = load_email_template('reset_password', language)
    greeting_text = email_texts['greeting'].format(first_name=first_name)

    context = {
        'reset_link': reset_link,
        'greeting': greeting_text,
        'email_texts': email_texts,
    }

    try:
        html = render_to_string("reset_password.html", context)
        text = strip_tags(html)

        msg = EmailMultiAlternatives(
            subject=email_texts['title'],
            body=text,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[email],
        )
        msg.attach_alternative(html, "text/html")
        sent = msg.send(fail_silently=False)

        return {"sent": sent}
    except Exception as e:
        raise e


@shared_task
def send_subscription_oos_email(email, payload, language="en"):
    """Poziva se kada automatska pretplatna porudžbina ne može zbog zalihe/stanja proizvoda."""
    try:
        activate(language)
        email_texts = load_email_template("subscription_oos", language)
        first_name = (payload.get("first_name") or "").strip() or "there"
        greeting = email_texts["greeting"].format(first_name=first_name)
        product_lines = []
        for p in payload.get("products") or []:
            line = email_texts["product_line"].format(
                name=p.get("product_name", "?"),
                quantity=p.get("quantity", 1),
            )
            product_lines.append(line)
        retry_line = email_texts["retry"].format(
            retry_days=payload.get("retry_days", 7),
            next_retry=payload.get("next_retry_display") or "—",
        )
        schedule_line = email_texts["schedule"].format(
            interval_days=payload.get("interval_days", ""),
        )
        context = {
            "email_texts": email_texts,
            "greeting": greeting,
            "product_lines": product_lines,
            "retry_line": retry_line,
            "schedule_line": schedule_line,
        }
        html = render_to_string("subscription_oos.html", context)
        text = strip_tags(html)
        msg = EmailMultiAlternatives(
            subject=email_texts["subject"],
            body=text,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[email],
        )
        msg.attach_alternative(html, "text/html")
        return {"sent": msg.send(fail_silently=False)}
    except Exception as e:
        raise e


@shared_task
def process_due_subscriptions():
    """
    Periodično kreira narudžbine za aktivne pretplate čiji je next_order_at u prošlosti.
    Pokreće se preko Celery Beat ili: python manage.py process_subscriptions
    """
    import logging
    from datetime import timedelta

    from django.db import transaction
    from django.utils import timezone

    from django.utils import formats

    from .models import ProductSubscription, SubscriptionStatus
    from .order_email_data import build_order_confirmation_email_data
    from .subscription_availability import (
        SUBSCRIPTION_OOS_RETRY_DAYS,
        bump_next_order_after_oos,
        get_unavailable_subscription_items,
    )
    from .subscription_orders import create_authenticated_order

    log = logging.getLogger(__name__)
    now = timezone.now()
    ids = list(
        ProductSubscription.objects.filter(
            status=SubscriptionStatus.ACTIVE,
            next_order_at__lte=now,
        ).values_list("id", flat=True)
    )
    for sid in ids:
        try:
            oos_payload = None
            oos_email = None
            sub_for_confirmation = None
            with transaction.atomic():
                sub = (
                    ProductSubscription.objects.select_for_update()
                    .filter(
                        pk=sid,
                        status=SubscriptionStatus.ACTIVE,
                        next_order_at__lte=timezone.now(),
                    )
                    .first()
                )
                if not sub:
                    continue
                if not sub.items.exists():
                    sub.delete()
                    continue
                unavailable = get_unavailable_subscription_items(sub)
                if unavailable:
                    bump_next_order_after_oos(sub)
                    sub.refresh_from_db()
                    oos_email = sub.user.email
                    oos_payload = {
                        "first_name": sub.user.first_name or "",
                        "products": unavailable,
                        "next_retry_display": formats.date_format(
                            sub.next_order_at, "SHORT_DATETIME_FORMAT"
                        ),
                        "retry_days": SUBSCRIPTION_OOS_RETRY_DAYS,
                        "interval_days": sub.interval_days,
                    }
                    continue
                order_items = [
                    {"product": it.product_id, "quantity": it.quantity} for it in sub.items.all()
                ]
                create_authenticated_order(
                    user=sub.user,
                    address_id=sub.address_id,
                    order_items=order_items,
                    payment_method=sub.payment_method,
                    transport_method=sub.transport_method,
                    note=sub.note or "",
                    subscription=sub,
                )
                sub.next_order_at = timezone.now() + timedelta(days=sub.interval_days)
                sub.save(update_fields=["next_order_at", "updated_at"])
                sub_for_confirmation = sub.pk

            if oos_payload and oos_email:
                send_subscription_oos_email.delay(oos_email, oos_payload, "en")
                continue

            if sub_for_confirmation:
                sub = ProductSubscription.objects.get(pk=sub_for_confirmation)
                order = sub.orders.order_by("-id").first()
                if order:
                    data = build_order_confirmation_email_data(order)
                    send_order_confirmation_email.delay(sub.user.email, data, "en")
        except Exception:
            log.exception("process_due_subscriptions failed for subscription_id=%s", sid)


def test_mailjet():
    # Brza provera da li su setovani kredencijali i FROM
    missing = [k for k in ("EMAIL_HOST_USER", "EMAIL_HOST_PASSWORD", "DEFAULT_FROM_EMAIL")
               if not getattr(settings, k, None)]
    if missing:
        print("⚠️ Nedostaju u settings:", ", ".join(missing))
        return

    try:
        sent = send_mail(
            subject="✅ Mailjet test",
            message="Plain-text fallback.",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=["info@snusco.com"],
            html_message="<p>Ovo je <strong>Mailjet SMTP</strong> test poruka.</p>",
            fail_silently=False,
        )
        if sent == 1:
            print("✅ Email poslat preko Mailjet SMTP-a.")
        else:
            print("⚠️ Nije poslato. Vraćeno:", sent)
    except Exception as e:
        print("❌ Greška:", str(e))