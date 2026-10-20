"""E-mail delivery: console (development), memory (tests), SMTP (production, sent by the default worker)."""

import logging
from dataclasses import dataclass

from app.core.config import get_settings

log = logging.getLogger("app.email")


@dataclass
class EmailMessage:
    to: str
    subject: str
    body: str


# Messages captured when EMAIL_PROVIDER=memory (automated tests).
outbox: list[EmailMessage] = []


def send(to: str, subject: str, body: str) -> None:
    message = EmailMessage(to=to, subject=subject, body=body)
    provider = get_settings().email_provider
    if provider == "memory":
        outbox.append(message)
        return
    if provider == "smtp":
        # Queued: a slow or failing SMTP server must not break sign-up; the task retries.
        from app.workers.tasks import send_email_task

        send_email_task.apply_async(args=[to, subject, body], queue="default")
        return
    # console: never used in production (refused by settings). Links contain one-time tokens,
    # which is acceptable only on a developer machine.
    log.info("EMAIL to=%s subject=%s\n%s", to, subject, body)


def deliver_smtp(to: str, subject: str, body: str) -> None:
    """Send one plain-text message over SMTP with TLS (STARTTLS on 587 or implicit TLS on 465)."""
    import smtplib
    import ssl
    from email.message import EmailMessage as Message
    from email.utils import make_msgid

    settings = get_settings()
    msg = Message()
    msg["From"] = settings.email_from
    msg["To"] = to
    msg["Subject"] = subject
    msg["Message-ID"] = make_msgid(domain=settings.email_from.rsplit("@", 1)[-1])
    msg.set_content(body)
    context = ssl.create_default_context()  # certificate and hostname verified
    if settings.smtp_security == "ssl":
        server = smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=20, context=context)
    else:
        server = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20)
        server.starttls(context=context)
    with server:
        if settings.smtp_user:
            server.login(settings.smtp_user, settings.smtp_password)
        server.send_message(msg)
