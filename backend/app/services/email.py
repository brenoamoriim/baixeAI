"""E-mail delivery. Development uses the console; a real provider is wired in a later phase."""

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
    # console: never used in production (no real delivery). Links contain one-time tokens,
    # which is acceptable only on a developer machine.
    log.info("EMAIL to=%s subject=%s\n%s", to, subject, body)
