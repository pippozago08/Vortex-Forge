import logging

from django.conf import settings
from django.core.mail import send_mail
from django.urls import reverse
from django.utils.translation import gettext as _

from core.models import SiteSetting


logger = logging.getLogger(__name__)


def build_public_url(request, path):
    public_base = getattr(settings, "SITE_PUBLIC_URL", "").strip().rstrip("/")
    if request is not None:
        current_host = request.get_host()
        if public_base and current_host in {"127.0.0.1:8000", "localhost:8000", "testserver"}:
            return f"{public_base}{path}"
        return request.build_absolute_uri(path)
    return f"{public_base}{path}" if public_base else path


def send_safe_mail(subject, message, recipients):
    recipients = [item for item in recipients if item]
    if not recipients:
        return

    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=recipients,
            fail_silently=False,
        )
    except Exception:
        logger.exception("Unable to send transactional email.")


def notify_custom_request_submitted(custom_request, request=None):
    site_settings = SiteSetting.load()
    dashboard_url = build_public_url(request, reverse("backoffice:requests"))
    origin_line = custom_request.origin_label
    build_line = custom_request.requested_build.localized_name if custom_request.requested_build_id and custom_request.requested_build else "-"
    send_safe_mail(
        subject=_("Nuova richiesta build %(reference)s") % {"reference": custom_request.reference_code},
        message=_(
            "E stata inviata una nuova richiesta build.\n\n"
            "Riferimento: %(reference)s\n"
            "Origine: %(origin)s\n"
            "Build collegata: %(build)s\n"
            "Cliente: %(email)s\n"
            "Budget: %(budget)s\n"
            "Dashboard: %(url)s"
        )
        % {
            "reference": custom_request.reference_code,
            "origin": origin_line,
            "build": build_line,
            "email": custom_request.user.email,
            "budget": custom_request.budget_range_display,
            "url": dashboard_url,
        },
        recipients=[site_settings.support_email],
    )


def notify_custom_request_approved(custom_request, request=None):
    payment_url = build_public_url(request, reverse("catalog:custom_request_payment", kwargs={"pk": custom_request.pk}))
    send_safe_mail(
        subject=_("La tua richiesta %(reference)s e stata approvata") % {"reference": custom_request.reference_code},
        message=_(
            "La tua richiesta build e stata approvata.\n\n"
            "Riferimento: %(reference)s\n"
            "Prezzo finale: %(price)s\n"
            "Stato: %(status)s\n"
            "Checkout: %(url)s\n\n"
            "Apri la pagina checkout per controllare il riepilogo completo e procedere al pagamento."
        )
        % {
            "reference": custom_request.reference_code,
            "price": custom_request.approved_price_display,
            "status": custom_request.get_status_display(),
            "url": payment_url,
        },
        recipients=[custom_request.user.email],
    )


def notify_custom_request_paid(custom_request, payment, request=None):
    dashboard_url = build_public_url(request, reverse("accounts:dashboard"))
    send_safe_mail(
        subject=_("Pagamento confermato per %(reference)s") % {"reference": custom_request.reference_code},
        message=_(
            "Il pagamento della tua richiesta build e stato confermato.\n\n"
            "Riferimento: %(reference)s\n"
            "Pagamento: %(payment_reference)s\n"
            "Metodo: %(checkout_method)s\n"
            "Importo: %(amount)s %(currency)s\n"
            "Provider: %(provider)s\n"
            "Order ID: %(order_id)s\n"
            "Transaction ID: %(transaction_id)s\n"
            "Dashboard: %(url)s"
        )
        % {
            "reference": custom_request.reference_code,
            "payment_reference": payment.reference_code,
            "checkout_method": payment.get_checkout_method_display(),
            "amount": f"{payment.amount:.2f}",
            "currency": payment.currency,
            "provider": payment.get_provider_display(),
            "order_id": payment.external_order_id or "-",
            "transaction_id": payment.external_transaction_id or "-",
            "url": dashboard_url,
        },
        recipients=[custom_request.user.email],
    )


def notify_admin_payment_received(custom_request, payment, request=None):
    site_settings = SiteSetting.load()
    dashboard_url = build_public_url(request, reverse("backoffice:custom_request_review", kwargs={"pk": custom_request.pk}))
    send_safe_mail(
        subject=_("Pagamento ricevuto per %(reference)s") % {"reference": custom_request.reference_code},
        message=_(
            "Una richiesta build risulta pagata.\n\n"
            "Riferimento: %(reference)s\n"
            "Pagamento: %(payment_reference)s\n"
            "Metodo: %(checkout_method)s\n"
            "Cliente: %(email)s\n"
            "Importo: %(amount)s %(currency)s\n"
            "Ordine esterno: %(order_id)s\n"
            "Transaction ID: %(transaction_id)s\n"
            "Dashboard: %(url)s"
        )
        % {
            "reference": custom_request.reference_code,
            "payment_reference": payment.reference_code,
            "checkout_method": payment.get_checkout_method_display(),
            "email": custom_request.user.email,
            "amount": f"{payment.amount:.2f}",
            "currency": payment.currency,
            "order_id": payment.external_order_id or "-",
            "transaction_id": payment.external_transaction_id or "-",
            "url": dashboard_url,
        },
        recipients=[site_settings.support_email],
    )
