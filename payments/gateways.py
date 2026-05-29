from dataclasses import dataclass
from uuid import uuid4

from django.conf import settings
from django.utils.translation import gettext_lazy as _

from catalog.models import CustomBuildPayment


class PaymentConfigurationError(Exception):
    pass


class PaymentGatewayError(Exception):
    pass


@dataclass
class CheckoutSession:
    provider: str
    environment: str
    external_order_id: str
    redirect_url: str = ""
    message: str = ""


class BasePaymentGateway:
    provider_key = ""

    def create_order(self, payment, return_url="", cancel_url=""):
        raise NotImplementedError

    def capture_order(self, payment, payer_context=None):
        raise NotImplementedError

    def verify_webhook(self, payload, headers=None):
        raise NotImplementedError


class SimulatedPaymentGateway(BasePaymentGateway):
    provider_key = CustomBuildPayment.Provider.SIMULATED

    def create_order(self, payment, return_url="", cancel_url=""):
        if not settings.SIMULATED_PAYMENTS_ENABLED:
            raise PaymentConfigurationError(_("I pagamenti simulati sono disattivati in questo ambiente."))
        return CheckoutSession(
            provider=self.provider_key,
            environment="dev",
            external_order_id=payment.external_order_id or f"SIM-{uuid4().hex[:14].upper()}",
            message=_("Checkout simulato pronto. Completa il test con esito positivo o negativo."),
        )

    def capture_order(self, payment, payer_context=None):
        return {
            "transaction_id": f"SIMTX-{uuid4().hex[:14].upper()}",
        }

    def verify_webhook(self, payload, headers=None):
        return True


class PayPalGateway(BasePaymentGateway):
    provider_key = CustomBuildPayment.Provider.PAYPAL

    def create_order(self, payment, return_url="", cancel_url=""):
        # Future hook: create PayPal Orders API order and persist the external order id.
        if not settings.PAYPAL_CLIENT_ID or not settings.PAYPAL_CLIENT_SECRET:
            raise PaymentConfigurationError(_("Configurazione PayPal mancante nelle variabili ambiente."))

        raise PaymentGatewayError(
            _(
                "Il provider PayPal e gia predisposto a livello architetturale, ma il checkout reale non e ancora attivato. "
                "Mantieni PAYMENT_PROVIDER=simulated finche non colleghi le API Orders di PayPal."
            )
        )

    def capture_order(self, payment, payer_context=None):
        # Future hook: capture the approved PayPal order and save the transaction id.
        raise PaymentGatewayError(_("La capture PayPal reale non e ancora attiva in questo ambiente."))

    def verify_webhook(self, payload, headers=None):
        # Future hook: validate and process PayPal webhook events.
        raise PaymentGatewayError(_("La verifica webhook PayPal reale non e ancora attiva in questo ambiente."))
