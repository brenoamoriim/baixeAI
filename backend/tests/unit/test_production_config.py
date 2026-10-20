"""Production refuses unsafe configuration; SMTP delivery uses verified TLS before authenticating."""

import pytest

from app.core.config import Settings

STRONG = {"secret_key": "s" * 40, "signed_url_secret": "u" * 40, "guest_id_hmac_secret": "g" * 40}
PROD_OK = {**STRONG, "app_env": "production", "email_provider": "smtp", "smtp_host": "smtp.example.com",
           "cookie_secure": True}


def test_valid_production_settings_load():
    assert Settings(**PROD_OK).is_production


@pytest.mark.parametrize("override", [
    {"secret_key": "short"},
    {"email_provider": "console"},
    {"smtp_host": ""},
    {"cookie_secure": False},
])
def test_production_refuses_unsafe_settings(override):
    with pytest.raises(ValueError):
        Settings(**{**PROD_OK, **override})


def test_engine_role_has_no_secrets_and_no_database_even_in_production():
    s = Settings(app_env="production", process_role="engine")
    assert s.secret_key == s.signed_url_secret == s.guest_id_hmac_secret == ""
    assert "invalid" in s.database_url


def test_crypto_refuses_empty_keys(monkeypatch):
    from app.security import crypto

    monkeypatch.setattr(crypto, "get_settings", lambda: Settings(process_role="engine"))
    with pytest.raises(RuntimeError):
        crypto.sign("x")
    with pytest.raises(RuntimeError):
        crypto.keyed_hash("1.2.3.4", purpose="ip")


class FakeSMTP:
    calls: list = []

    def __init__(self, host, port, timeout=None, context=None):
        FakeSMTP.calls.append(("connect", host, port, context is not None))

    def starttls(self, context=None):
        FakeSMTP.calls.append(("starttls", context.check_hostname, context.verify_mode))

    def login(self, user, password):
        FakeSMTP.calls.append(("login", user))

    def send_message(self, msg):
        FakeSMTP.calls.append(("send", msg["To"], msg["Subject"], msg["From"]))

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        FakeSMTP.calls.append(("quit",))


@pytest.mark.parametrize("security", ["starttls", "ssl"])
def test_smtp_uses_verified_tls_before_login(monkeypatch, security):
    import smtplib
    import ssl

    from app.services import email

    FakeSMTP.calls = []
    monkeypatch.setattr(smtplib, "SMTP", FakeSMTP)
    monkeypatch.setattr(smtplib, "SMTP_SSL", FakeSMTP)
    monkeypatch.setattr(email, "get_settings", lambda: Settings(
        email_provider="smtp", smtp_host="smtp.example.com", smtp_port=587 if security == "starttls" else 465,
        smtp_user="u", smtp_password="p", smtp_security=security, email_from="nao-responda@baixeai.com.br"))
    email.deliver_smtp("a@b.com", "Assunto", "corpo")
    kinds = [c[0] for c in FakeSMTP.calls]
    if security == "starttls":
        assert kinds == ["connect", "starttls", "login", "send", "quit"]
        assert FakeSMTP.calls[1][1] is True and FakeSMTP.calls[1][2] == ssl.CERT_REQUIRED
    else:
        assert kinds == ["connect", "login", "send", "quit"] and FakeSMTP.calls[0][3] is True
    assert FakeSMTP.calls[-2][1:] == ("a@b.com", "Assunto", "nao-responda@baixeai.com.br")


def test_smtp_provider_queues_instead_of_sending_inline(monkeypatch):
    from app.services import email
    from app.workers import tasks

    sent = []
    monkeypatch.setattr(email, "get_settings", lambda: Settings(email_provider="smtp", smtp_host="h"))
    monkeypatch.setattr(tasks.send_email_task, "apply_async", lambda args, queue: sent.append((args, queue)))
    email.send("a@b.com", "s", "b")
    assert sent == [(["a@b.com", "s", "b"], "default")]
