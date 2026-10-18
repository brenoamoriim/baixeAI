"""Sandbox validation of the points the docs left open (run with Mercado Pago TEST credentials in .env).

    docker compose exec api python -m app.payments.sandbox_check
    docker compose exec api python -m app.payments.sandbox_check --payment 1234567890

It creates (never charges) a R$ 1,00 test preference and a pending R$ 1,00 test subscription and
reports what the API actually returned. Refuses to run with production credentials.
"""

import argparse
import uuid

from app.core.config import get_settings
from app.payments.mercadopago import MercadoPago
from app.payments.provider import ProviderError


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--payment", help="also fetch this payment id and print its normalized state")
    parser.add_argument("--email", default="test_user_baixeai@testuser.com")
    args = parser.parse_args()
    settings = get_settings()
    if not settings.mp_access_token:
        raise SystemExit("MP_ACCESS_TOKEN vazio: configure as credenciais de TESTE no .env")
    if settings.is_production:
        raise SystemExit("Recusado: use apenas com APP_ENV de desenvolvimento e credenciais de teste.")
    mp = MercadoPago(settings.mp_access_token, settings.mp_webhook_secret or "unset")
    base = (settings.api_public_url or settings.app_base_url).rstrip("/")
    results = {}
    ref = str(uuid.uuid4())
    try:
        session = mp.create_checkout(payment_id=ref, title="BaixeAI teste sandbox", amount_cents=100,
                                     payer_email=args.email, notification_url=f"{base}/api/webhooks/mercadopago",
                                     back_url=f"{settings.app_base_url}/pagamento/retorno?ref={ref}")
        results["checkout_pro_preference"] = f"OK -> abra para pagar com cartão de teste: {session.redirect_url}"
    except ProviderError as exc:
        results["checkout_pro_preference"] = f"FALHOU: {exc}"
    try:
        sub = mp.create_subscription(subscription_id=str(uuid.uuid4()), reason="BaixeAI teste sandbox",
                                     amount_cents=100, payer_email=args.email,
                                     back_url=f"{settings.app_base_url}/pagamento/retorno")
        results["preapproval_pending_has_init_point"] = f"OK (verificado) -> {sub.redirect_url}"
        mp.cancel_subscription(sub.provider_subscription_id)
        results["preapproval_cancel"] = "OK"
    except ProviderError as exc:
        results["preapproval_pending_has_init_point"] = f"FALHOU (ponto NÃO VERIFICADO confirmado como problema): {exc}"
    if args.payment:
        try:
            p = mp.get_payment(args.payment)
            results["payment"] = (f"status={p.status} ({p.raw_status}/{p.status_detail}) amount={p.amount_cents} "
                                  f"method={p.method} ref={p.external_reference}")
        except ProviderError as exc:
            results["payment"] = f"FALHOU: {exc}"
    for key, value in results.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
