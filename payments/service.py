from django.conf import settings
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from catalog.models import Build, CustomBuildPayment, CustomBuildRequest

from .gateways import (
    CheckoutSession,
    PayPalGateway,
    PaymentConfigurationError,
    PaymentGatewayError,
    SimulatedPaymentGateway,
)


class PaymentStateError(Exception):
    pass


def get_payment_gateway():
    provider = getattr(settings, "PAYMENT_PROVIDER", CustomBuildPayment.Provider.SIMULATED)
    if provider == CustomBuildPayment.Provider.PAYPAL:
        return PayPalGateway()
    return SimulatedPaymentGateway()


def start_custom_request_checkout(custom_request, *, user, checkout_method, return_url="", cancel_url=""):
    if custom_request.user_id != user.pk:
        raise PaymentStateError(_("Non puoi pagare una richiesta che non ti appartiene."))
    if not custom_request.is_payment_available:
        raise PaymentStateError(_("La richiesta non e ancora pronta per il pagamento."))
    if custom_request.approved_price is None:
        raise PaymentStateError(_("Prezzo finale non disponibile."))
    if checkout_method not in CustomBuildPayment.CheckoutMethod.values:
        raise PaymentStateError(_("Metodo di pagamento non valido."))

    gateway = get_payment_gateway()

    with transaction.atomic():
        locked_request = CustomBuildRequest.objects.select_for_update().get(pk=custom_request.pk)
        open_payment = locked_request.payments.filter(
            provider=gateway.provider_key,
            status__in=[CustomBuildPayment.Status.CREATED, CustomBuildPayment.Status.PENDING],
        ).order_by("-initiated_at").first()

        if open_payment:
            payment = open_payment
        else:
            payment = CustomBuildPayment.objects.create(
                user=user,
                custom_request=locked_request,
                amount=locked_request.approved_price,
                currency=locked_request.currency,
                provider=gateway.provider_key,
                checkout_method=checkout_method,
            )

        session = gateway.create_order(payment, return_url=return_url, cancel_url=cancel_url)
        payment.checkout_method = checkout_method
        payment.amount = locked_request.approved_price
        payment.currency = locked_request.currency
        payment.external_order_id = session.external_order_id
        payment.environment = session.environment
        payment.status = CustomBuildPayment.Status.PENDING
        payment.save(update_fields=["checkout_method", "amount", "currency", "external_order_id", "environment", "status", "updated_at"])

        locked_request.status = CustomBuildRequest.Status.PAYMENT_PENDING
        locked_request.save(update_fields=["status", "updated_at"])

    return payment, session


def finalize_simulated_payment(payment, *, success):
    if payment.provider != CustomBuildPayment.Provider.SIMULATED:
        raise PaymentStateError(_("Il pagamento selezionato non usa il provider simulato."))
    if payment.status not in {CustomBuildPayment.Status.CREATED, CustomBuildPayment.Status.PENDING}:
        raise PaymentStateError(_("Questo tentativo di pagamento non puo piu essere completato."))

    gateway = SimulatedPaymentGateway()

    with transaction.atomic():
        locked_payment = CustomBuildPayment.objects.select_for_update().get(pk=payment.pk)
        custom_request = CustomBuildRequest.objects.select_for_update().get(pk=locked_payment.custom_request_id)

        was_paid = custom_request.status == CustomBuildRequest.Status.PAID

        if success:
            capture_data = gateway.capture_order(locked_payment)
            locked_payment.mark_succeeded(transaction_id=capture_data["transaction_id"])
            custom_request.status = CustomBuildRequest.Status.PAID
            custom_request.paid_at = timezone.now()
            custom_request.save(update_fields=["status", "paid_at", "updated_at"])
            if not was_paid and custom_request.requested_build_id:
                Build.objects.filter(pk=custom_request.requested_build_id).update(sold_count=F("sold_count") + 1)
        else:
            locked_payment.mark_failed(admin_notes=str(_("Esito simulato negativo.")))
            custom_request.status = CustomBuildRequest.Status.PAYMENT_FAILED
            custom_request.save(update_fields=["status", "updated_at"])

    return locked_payment


def get_paypal_runtime_summary():
    return {
        "provider": getattr(settings, "PAYMENT_PROVIDER", CustomBuildPayment.Provider.SIMULATED),
        "currency": getattr(settings, "PAYMENT_DEFAULT_CURRENCY", "EUR"),
        "paypal_environment": getattr(settings, "PAYPAL_ENVIRONMENT", "sandbox"),
        "paypal_configured": bool(getattr(settings, "PAYPAL_CLIENT_ID", "")) and bool(getattr(settings, "PAYPAL_CLIENT_SECRET", "")),
    }


__all__ = [
    "CheckoutSession",
    "PaymentConfigurationError",
    "PaymentGatewayError",
    "PaymentStateError",
    "finalize_simulated_payment",
    "get_payment_gateway",
    "get_paypal_runtime_summary",
    "start_custom_request_checkout",
]
