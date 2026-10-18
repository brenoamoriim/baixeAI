"""Payment provider interface. Business rules (app/services/payments.py) only see these types."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime


class ProviderError(Exception):
    """Provider unreachable or returned an unexpected answer (retry later)."""


class InvalidWebhook(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass
class CheckoutSession:
    redirect_url: str
    provider_reference: str  # preference id


@dataclass
class SubscriptionSession:
    redirect_url: str
    provider_subscription_id: str  # preapproval id


@dataclass
class ProviderPayment:
    """Authoritative payment state, always fetched from the provider API (never from the webhook body)."""

    provider_payment_id: str
    status: (
        str  # normalized: pending | approved | rejected | cancelled | expired | refunded | charged_back | in_mediation
    )
    status_detail: str | None
    amount_cents: int
    currency: str
    external_reference: str | None
    method: str | None  # pix | credit_card | debit_card | account_money | ...
    approved_at: datetime | None
    refunded_cents: int = 0
    subscription_id: str | None = None  # provider subscription (preapproval) id, for recurring charges
    raw_status: str = ""


@dataclass
class ProviderSubscription:
    provider_subscription_id: str
    status: str  # pending | authorized | paused | cancelled
    external_reference: str | None
    amount_cents: int | None


@dataclass
class WebhookEvent:
    topic: str  # payment | subscription_preapproval | subscription_authorized_payment | chargebacks | ...
    resource_id: str
    action: str | None
    dedup_key: str
    payload: dict = field(default_factory=dict)


class PaymentProvider(ABC):
    name: str

    @abstractmethod
    def create_checkout(
        self, *, payment_id: str, title: str, amount_cents: int, payer_email: str, notification_url: str, back_url: str
    ) -> CheckoutSession: ...

    @abstractmethod
    def create_subscription(
        self, *, subscription_id: str, reason: str, amount_cents: int, payer_email: str, back_url: str
    ) -> SubscriptionSession: ...

    @abstractmethod
    def update_subscription_amount(self, provider_subscription_id: str, amount_cents: int) -> None: ...

    @abstractmethod
    def cancel_subscription(self, provider_subscription_id: str) -> None: ...

    @abstractmethod
    def get_payment(self, provider_payment_id: str) -> ProviderPayment: ...

    @abstractmethod
    def find_payments(self, external_reference: str) -> list[ProviderPayment]: ...

    @abstractmethod
    def get_subscription(self, provider_subscription_id: str) -> ProviderSubscription: ...

    @abstractmethod
    def get_subscription_charge(self, charge_id: str) -> ProviderPayment | None:
        """A recurring charge notification -> the underlying payment (None if not created yet)."""

    @abstractmethod
    def refund(self, provider_payment_id: str, amount_cents: int, idempotency_key: str) -> None: ...

    @abstractmethod
    def parse_webhook(self, headers: dict[str, str], query: dict[str, str], body: dict) -> WebhookEvent:
        """Verify authenticity (signature + timestamp) and return the event. Raise InvalidWebhook."""
