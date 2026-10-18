import hashlib
import hmac
import json
import time

import httpx
import pytest

from app.payments.mercadopago import MercadoPago, normalize_status
from app.payments.provider import InvalidWebhook, ProviderError

SECRET = "s3cr3t"


def _client(handler):
    return MercadoPago("TEST-abc", SECRET, transport=httpx.MockTransport(handler))


def test_preference_body_uses_server_amount_and_reference():
    seen = {}

    def handler(request: httpx.Request):
        seen["path"] = request.url.path
        seen["auth"] = request.headers["authorization"]
        seen["idem"] = request.headers.get("x-idempotency-key")
        seen["body"] = json.loads(request.content)
        return httpx.Response(201, json={"id": "pref-1", "init_point": "https://www.mercadopago.com.br/checkout/x"})

    session = _client(handler).create_checkout(payment_id="pay-1", title="10 fichas", amount_cents=490,
                                               payer_email="a@b.com", notification_url="https://api/x",
                                               back_url="https://site/r")
    body = seen["body"]
    assert seen["path"] == "/checkout/preferences" and seen["auth"] == "Bearer TEST-abc" and seen["idem"] == "pref-pay-1"
    assert body["items"][0]["unit_price"] == 4.90 and body["items"][0]["currency_id"] == "BRL"
    assert body["external_reference"] == "pay-1" and body["notification_url"] == "https://api/x"
    assert body["payment_methods"]["excluded_payment_types"] == [{"id": "ticket"}]  # Pix/credit/debit only
    assert session.redirect_url.endswith("/checkout/x") and session.provider_reference == "pref-1"


def test_subscription_is_created_pending_without_card_data():
    seen = {}

    def handler(request):
        seen["body"] = json.loads(request.content)
        return httpx.Response(201, json={"id": "pre-1", "init_point": "https://mp/sub"})

    _client(handler).create_subscription(subscription_id="sub-1", reason="BaixeAI Pro", amount_cents=2490,
                                         payer_email="a@b.com", back_url="https://site/r")
    body = seen["body"]
    assert body["status"] == "pending" and "card_token_id" not in body
    assert body["auto_recurring"] == {"frequency": 1, "frequency_type": "months", "currency_id": "BRL",
                                      "transaction_amount": 24.90}
    assert body["external_reference"] == "sub-1"


def test_refund_sends_idempotency_key_and_amount():
    seen = {}

    def handler(request):
        seen.update(path=request.url.path, idem=request.headers["x-idempotency-key"], body=json.loads(request.content))
        return httpx.Response(201, json={"id": 1})

    _client(handler).refund("123", 294, idempotency_key="refund-x")
    assert seen == {"path": "/v1/payments/123/refunds", "idem": "refund-x", "body": {"amount": 2.94}}


def test_payment_parsing_and_status_normalization():
    def handler(request):
        return httpx.Response(200, json={"id": 9, "status": "approved", "status_detail": "accredited",
                                         "transaction_amount": 24.9, "currency_id": "BRL",
                                         "external_reference": "ref", "payment_type_id": "bank_transfer",
                                         "date_approved": "2026-10-18T12:00:00.000-03:00"})

    p = _client(handler).get_payment("9")
    assert (p.status, p.amount_cents, p.method, p.external_reference) == ("approved", 2490, "bank_transfer", "ref")
    assert p.approved_at.utcoffset().total_seconds() == -3 * 3600
    assert normalize_status("in_process", None) == "pending"
    assert normalize_status("authorized", None) == "pending"  # never grants on "authorized"
    assert normalize_status("cancelled", "expired") == "expired"
    assert normalize_status("something_new", None) == "pending"


def test_provider_http_errors_raise():
    with pytest.raises(ProviderError):
        _client(lambda r: httpx.Response(500, json={})).get_payment("1")
    with pytest.raises(ProviderError):
        _client(lambda r: httpx.Response(201, json={"id": "x"})).create_checkout(
            payment_id="p", title="t", amount_cents=1, payer_email="a@b.c", notification_url="n", back_url="b")


def _sign(data_id, request_id, ts, secret=SECRET):
    manifest = f"id:{data_id};request-id:{request_id};ts:{ts};"
    return hmac.new(secret.encode(), manifest.encode(), hashlib.sha256).hexdigest()


@pytest.mark.parametrize("ts", [int(time.time()), int(time.time() * 1000)])  # docs show seconds and ms
def test_webhook_signature_accepts_valid(ts):
    mp = _client(lambda r: httpx.Response(200))
    v1 = _sign("123", "req-1", ts)
    event = mp.parse_webhook({"X-Signature": f"ts={ts},v1={v1}", "X-Request-Id": "req-1"},
                             {"data.id": "123", "type": "payment"}, {"type": "payment", "action": "payment.updated"})
    assert (event.topic, event.resource_id, event.dedup_key) == ("payment", "123", "req-1")


def test_webhook_alphanumeric_id_is_lowercased_in_manifest():
    mp = _client(lambda r: httpx.Response(200))
    ts = int(time.time())
    v1 = _sign("abc123", "r", ts)
    event = mp.parse_webhook({"x-signature": f"ts={ts},v1={v1}", "x-request-id": "r"}, {"data.id": "ABC123"},
                             {"type": "subscription_preapproval"})
    assert event.resource_id == "abc123"


@pytest.mark.parametrize("headers,reason", [
    ({}, "missing_signature"),
    ({"x-signature": "ts=1,v1=deadbeef", "x-request-id": "r"}, "bad_signature"),
])
def test_webhook_rejections(headers, reason):
    with pytest.raises(InvalidWebhook) as exc:
        _client(lambda r: httpx.Response(200)).parse_webhook(headers, {"data.id": "1"}, {"type": "payment"})
    assert exc.value.reason == reason


def test_webhook_stale_timestamp_is_replay():
    ts = int(time.time()) - 3600
    with pytest.raises(InvalidWebhook) as exc:
        _client(lambda r: httpx.Response(200)).parse_webhook(
            {"x-signature": f"ts={ts},v1={_sign('1', 'r', ts)}", "x-request-id": "r"}, {"data.id": "1"},
            {"type": "payment"})
    assert exc.value.reason == "stale_timestamp"


def test_webhook_without_secret_is_never_accepted():
    mp = MercadoPago("TEST", "", transport=httpx.MockTransport(lambda r: httpx.Response(200)))
    with pytest.raises(InvalidWebhook):
        mp.parse_webhook({"x-signature": "ts=1,v1=x"}, {"data.id": "1"}, {"type": "payment"})
