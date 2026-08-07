from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
from celery import shared_task
from backend.helpers import load_email_template
from django.utils.translation import activate
from django.core.mail import send_mail


def _email_subscription_freq_line(days, email_texts):
    """Isti smisao kao PRODUCT.SUBSCRIBE_FREQ_LABEL_* u korpi."""
    try:
        d = int(days)
    except (TypeError, ValueError):
        return ""
    if d == 14:
        return email_texts.get("subscribe_freq_14d", "Every 14 days")
    if d == 31:
        return email_texts.get("subscribe_freq_31d", "Every month")
    if d == 62:
        return email_texts.get("subscribe_freq_62d", "Every 2 months")
    return email_texts.get("subscription_every_n_days", "Every {days} days").format(
        days=d
    )


def _annotate_order_email_subscription_lines(data, email_texts):
    """
    Na svakoj pretplatnoj stavci postavi subscription_freq_line;
    vrati podnaslov za sekciju kao u korpi (jedan interval ili mixed).
    """
    subs = data.get("products_subscription") or []
    if not subs:
        return None
    day_values = []
    for p in subs:
        d = p.get("subscription_interval_days")
        p["subscription_freq_line"] = _email_subscription_freq_line(d, email_texts)
        if d is not None:
            try:
                day_values.append(int(d))
            except (TypeError, ValueError):
                pass
    unique = set(day_values)
    if len(unique) > 1:
        return email_texts.get(
            "subscription_section_mixed_freq", "Different delivery schedules"
        )
    if len(unique) == 1:
        return _email_subscription_freq_line(unique.pop(), email_texts)
    return None


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

        subscription_section_subtitle = _annotate_order_email_subscription_lines(
            data, email_texts
        )

        greeting_text = email_texts['greeting'].format(first_name=data['first_name'])

        subscription_schedules = []
        has_subscription = bool(data.get("subscription_schedules"))
        if has_subscription:
            for s in data["subscription_schedules"]:
                d_int = s.get("interval_days")
                if d_int == 1:
                    phrase = email_texts.get(
                        "subscription_every_1_day", "Every day"
                    )
                elif d_int is not None:
                    phrase = _email_subscription_freq_line(d_int, email_texts)
                else:
                    phrase = "—"
                subscription_schedules.append(
                    {
                        "interval_days": d_int,
                        "interval_phrase": phrase,
                        "next_order_at_display": s.get("next_order_at_display")
                        or "—",
                    }
                )

        context = {
            'title': email_texts['title'],
            'greeting': greeting_text,
            'has_subscription': has_subscription,
            'subscription_banner_note': email_texts.get(
                "subscription_banner_note",
                "Automatic re-orders apply to the subscription items below; each line shows its schedule.",
            ),
            'subscription_schedules': subscription_schedules,
            'subscription_next_order_label': email_texts.get(
                'subscription_next_order_label', 'Next automatic order'
            ),
            'subscription_interval_label': email_texts.get(
                'subscription_interval_label', 'Delivery interval'
            ),
            'panel_your_products': email_texts.get(
                'panel_your_products', 'Your products'
            ),
            'subscription_section_title': email_texts.get(
                'subscription_section_title', 'Subscription'
            ),
            'subscription_section_subtitle': subscription_section_subtitle,
            'quantity_label': email_texts.get('quantity_label', 'Quantity'),
            'order_summary': email_texts['order_summary'],
            'order_id': email_texts['order_id'],
            'subtotal': email_texts['subtotal'],
            'shipping': email_texts['shipping'],
            'summary_in_total': email_texts.get('SUMMARY_IN_TOTAL', 'In total:'),
            'summary_vat_label': email_texts.get('SUMMARY_VAT_LABEL', 'VAT'),
            'summary_vat_included': email_texts.get('SUMMARY_VAT_INCLUDED', 'Included'),
            'shipping_free': email_texts.get('SHIPPING_FREE', 'Free'),
            'free_delivery_hint': (
                email_texts.get('FREE_DELIVERY_HINT', '').format(
                    min=int(data.get('free_shipping_threshold_eur', 50))
                )
                if not data.get('shipping_is_free')
                else ''
            ),
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
            bcc=["uros@snuswe.com", "snuswe.com@gmail.com"],  # zadržano BCC
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
            is_oos = False
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
                    is_oos = True
                else:
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

            if is_oos and oos_payload and oos_email:
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
            recipient_list=["info@snuswe.com"],
            html_message="<p>Ovo je <strong>Mailjet SMTP</strong> test poruka.</p>",
            fail_silently=False,
        )
        if sent == 1:
            print("✅ Email poslat preko Mailjet SMTP-a.")
        else:
            print("⚠️ Nije poslato. Vraćeno:", sent)
    except Exception as e:
        print("❌ Greška:", str(e))