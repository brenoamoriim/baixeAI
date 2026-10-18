from app.core.config import get_settings
from app.core.errors import AppError
from app.payments.provider import PaymentProvider

_override: PaymentProvider | None = None  # tests inject a fake provider


class PaymentsUnavailable(AppError):
    status_code = 503
    code = "payments_unavailable"


def get_provider() -> PaymentProvider:
    """Real provider only when credentials exist. Never a fake checkout in non-test environments."""
    if _override is not None:
        return _override
    settings = get_settings()
    if not settings.mp_access_token or not settings.mp_webhook_secret:
        raise PaymentsUnavailable("Pagamentos ainda não estão disponíveis.")
    from app.payments.mercadopago import MercadoPago

    return MercadoPago(
        settings.mp_access_token, settings.mp_webhook_secret, tolerance_seconds=settings.mp_webhook_tolerance_seconds
    )


def set_override(provider: PaymentProvider | None) -> None:
    global _override
    _override = provider
