"""Mercado Pago implementation (REST API via httpx; no SDK).

Verified against the official docs on 17-18/10/2026 (docs/architecture/06):
- Checkout Pro: POST /checkout/preferences -> init_point (hosted page: Pix, credit, debit, account money)
- Subscriptions: POST /preapproval with status "pending" (payer completes on Mercado Pago; no card data
  ever reaches our servers); PUT /preapproval/{id} to change amount or cancel
- Payments: GET /v1/payments/{id}; GET /v1/payments/search?external_reference=
- Refunds: POST /v1/payments/{id}/refunds (X-Idempotency-Key required)
- Webhook signature: x-signature "ts=..,v1=..", manifest "id:{data.id};request-id:{x-request-id};ts:{ts};",
  HMAC-SHA256 hex with the secret from the Webhooks panel.
NOT VERIFIED until the sandbox run (Phase 4 checklist): `init_point` in the pending /preapproval response
and the exact shape of GET /authorized_payments/{id}.
"""

import hashlib
import hmac
import time
import uuid
from datetime import datetime

import httpx

from app.payments.provider import (
    CheckoutSession,
    InvalidWebhook,
    PaymentProvider,
    ProviderError,
    ProviderPayment,
    ProviderSubscription,
    SubscriptionSession,
    WebhookEvent,
)

API = "https://api.mercadopago.com"
STATUS = {
    "approved": "approved",
    "authorized": "pending",
    "pending": "pending",
    "in_process": "pending",
    "action_required": "pending",
    "in_mediation": "in_mediation",
    "rejected": "rejected",
    "cancelled": "cancelled",
    "refunded": "refunded",
    "charged_back": "charged_back",
}
EXPIRED_DETAILS = {"expired", "pix_expired", "expired_payment"}


def _cents(value) -> int:
    return int(round(float(value) * 100))


def _reais(cents: int) -> float:
    return round(cents / 100, 2)


def _dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def normalize_status(raw: str, detail: str | None) -> str:
    if raw == "cancelled" and (detail or "").lower() in EXPIRED_DETAILS:
        return "expired"
    return STATUS.get(raw, "pending")  # unknown -> pending (never grants)


class MercadoPago(PaymentProvider):
    name = "mercadopago"

    def __init__(
        self,
        access_token: str,
        webhook_secret: str,
        *,
        tolerance_seconds: int = 300,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.webhook_secret = webhook_secret
        self.tolerance = tolerance_seconds
        self.client = httpx.Client(
            base_url=API, timeout=20, transport=transport, headers={"Authorization": f"Bearer {access_token}"}
        )

    # ------------------------------------------------------------------ http
    def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict | None = None,
        params: dict | None = None,
        idempotency_key: str | None = None,
    ) -> dict:
        headers = {"X-Idempotency-Key": idempotency_key or str(uuid.uuid4())} if method != "GET" else {}
        try:
            response = self.client.request(method, path, json=json, params=params, headers=headers)
        except httpx.HTTPError as exc:
            raise ProviderError(f"{method} {path}: {type(exc).__name__}") from exc
        if response.status_code >= 400:
            raise ProviderError(f"{method} {path}: HTTP {response.status_code}")
        return response.json() if response.content else {}

    # ------------------------------------------------------------------ checkout
    def create_checkout(self, *, payment_id, title, amount_cents, payer_email, notification_url, back_url):
        body = {
            "items": [
                {
                    "id": payment_id,
                    "title": title[:250],
                    "quantity": 1,
                    "currency_id": "BRL",
                    "unit_price": _reais(amount_cents),
                }
            ],
            "external_reference": payment_id,
            "payer": {"email": payer_email},
            "notification_url": notification_url,
            "back_urls": {k: back_url for k in ("success", "pending", "failure")},
            "auto_return": "approved",
            "payment_methods": {"excluded_payment_types": [{"id": "ticket"}], "installments": 1},
            "statement_descriptor": "BAIXEAI",
        }
        data = self._request("POST", "/checkout/preferences", json=body, idempotency_key=f"pref-{payment_id}")
        if not data.get("init_point") or not data.get("id"):
            raise ProviderError("preference without init_point")
        return CheckoutSession(redirect_url=data["init_point"], provider_reference=str(data["id"]))

    def create_subscription(self, *, subscription_id, reason, amount_cents, payer_email, back_url):
        body = {
            "reason": reason[:250],
            "external_reference": subscription_id,
            "payer_email": payer_email,
            "auto_recurring": {
                "frequency": 1,
                "frequency_type": "months",
                "currency_id": "BRL",
                "transaction_amount": _reais(amount_cents),
            },
            "back_url": back_url,
            "status": "pending",
        }
        data = self._request("POST", "/preapproval", json=body, idempotency_key=f"sub-{subscription_id}")
        if not data.get("init_point") or not data.get("id"):
            raise ProviderError("preapproval without init_point")
        return SubscriptionSession(redirect_url=data["init_point"], provider_subscription_id=str(data["id"]))

    def update_subscription_amount(self, provider_subscription_id, amount_cents):
        self._request(
            "PUT",
            f"/preapproval/{provider_subscription_id}",
            json={"auto_recurring": {"transaction_amount": _reais(amount_cents), "currency_id": "BRL"}},
        )

    def cancel_subscription(self, provider_subscription_id):
        self._request("PUT", f"/preapproval/{provider_subscription_id}", json={"status": "cancelled"})

    # ------------------------------------------------------------------ reads (authoritative)
    def _to_payment(self, data: dict) -> ProviderPayment:
        refunded = sum(_cents(r.get("amount", 0)) for r in data.get("refunds", []) or [])
        return ProviderPayment(
            provider_payment_id=str(data["id"]),
            status=normalize_status(str(data.get("status", "")), data.get("status_detail")),
            status_detail=data.get("status_detail"),
            amount_cents=_cents(data.get("transaction_amount", 0)),
            currency=str(data.get("currency_id", "")),
            external_reference=data.get("external_reference"),
            method=data.get("payment_type_id"),
            approved_at=_dt(data.get("date_approved")),
            refunded_cents=refunded or _cents(data.get("transaction_amount_refunded", 0) or 0),
            subscription_id=(data.get("metadata") or {}).get("preapproval_id") or data.get("preapproval_id"),
            raw_status=str(data.get("status", "")),
        )

    def get_payment(self, provider_payment_id):
        return self._to_payment(self._request("GET", f"/v1/payments/{provider_payment_id}"))

    def find_payments(self, external_reference):
        data = self._request(
            "GET",
            "/v1/payments/search",
            params={"external_reference": external_reference, "sort": "date_created", "criteria": "desc"},
        )
        return [self._to_payment(r) for r in data.get("results", [])]

    def get_subscription(self, provider_subscription_id):
        data = self._request("GET", f"/preapproval/{provider_subscription_id}")
        amount = (data.get("auto_recurring") or {}).get("transaction_amount")
        return ProviderSubscription(
            provider_subscription_id=str(data["id"]),
            status=str(data.get("status", "")),
            external_reference=data.get("external_reference"),
            amount_cents=_cents(amount) if amount is not None else None,
        )

    def get_subscription_charge(self, charge_id):
        data = self._request("GET", f"/authorized_payments/{charge_id}")
        payment = data.get("payment") or {}
        if not payment.get("id"):
            return None
        result = self.get_payment(str(payment["id"]))
        result.subscription_id = result.subscription_id or data.get("preapproval_id")
        return result

    def refund(self, provider_payment_id, amount_cents, idempotency_key):
        self._request(
            "POST",
            f"/v1/payments/{provider_payment_id}/refunds",
            json={"amount": _reais(amount_cents)},
            idempotency_key=idempotency_key,
        )

    # ------------------------------------------------------------------ webhook
    def parse_webhook(self, headers, query, body):
        lowered = {k.lower(): v for k, v in headers.items()}
        signature = lowered.get("x-signature", "")
        request_id = lowered.get("x-request-id", "")
        parts = dict(p.strip().split("=", 1) for p in signature.split(",") if "=" in p)
        ts, v1 = parts.get("ts"), parts.get("v1")
        if not ts or not v1 or not self.webhook_secret:
            raise InvalidWebhook("missing_signature")
        data_id = str(query.get("data.id") or (body.get("data") or {}).get("id") or "")
        if data_id.isalnum():
            data_id = data_id.lower()  # docs: alphanumeric ids are lower-cased in the manifest
        manifest = ""
        if data_id:
            manifest += f"id:{data_id};"
        if request_id:
            manifest += f"request-id:{request_id};"
        manifest += f"ts:{ts};"
        expected = hmac.new(self.webhook_secret.encode(), manifest.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, v1):
            raise InvalidWebhook("bad_signature")
        try:
            sent = int(ts)
        except ValueError:
            raise InvalidWebhook("bad_timestamp") from None
        sent_seconds = sent / 1000 if sent > 10**12 else sent  # docs show both s and ms examples
        if abs(time.time() - sent_seconds) > self.tolerance:
            raise InvalidWebhook("stale_timestamp")  # replay protection
        topic = str(body.get("type") or query.get("type") or query.get("topic") or "")
        if not topic or not data_id:
            raise InvalidWebhook("missing_resource")
        action = body.get("action")
        dedup = request_id or f"{topic}:{data_id}:{action}"
        return WebhookEvent(topic=topic, resource_id=data_id, action=action, dedup_key=dedup[:200], payload=body)
