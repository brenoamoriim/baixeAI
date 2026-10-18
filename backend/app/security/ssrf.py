"""SSRF defenses for user-supplied URLs (CLAUDE.md, docs/architecture/08 T1).

`validate_url` is the cheap, early check in the API. The authoritative check happens again for
EVERY connection inside the egress proxy (`app.security.egress_proxy`), which also pins the
resolved IP, so redirects and DNS rebinding cannot reach internal addresses.
"""

import ipaddress
import os
import socket
from dataclasses import dataclass
from urllib.parse import urlsplit

ALLOWED_SCHEMES = {"http", "https"}
ALLOWED_PORTS = {80, 443}
MAX_URL_LENGTH = 2048

# Ranges that is_global misses or that we never want, regardless of ipaddress' classification.
_EXTRA_BLOCKED = [
    ipaddress.ip_network(n)
    for n in ("100.64.0.0/10", "192.0.0.0/24", "198.18.0.0/15", "0.0.0.0/8", "169.254.0.0/16",
              "64:ff9b::/96", "64:ff9b:1::/48", "2002::/16", "fc00::/7", "fe80::/10")
]


class UnsafeUrl(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class SafeTarget:
    url: str
    host: str
    port: int
    addresses: tuple[str, ...]


def is_public_ip(value: str) -> bool:
    try:
        ip = ipaddress.ip_address(value)
    except ValueError:
        return False
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped  # ::ffff:127.0.0.1 is loopback
    if not ip.is_global or ip.is_multicast or ip.is_reserved or ip.is_unspecified:
        return False
    return not any(ip in net for net in _EXTRA_BLOCKED if net.version == ip.version)


def resolve(host: str, port: int) -> tuple[str, ...]:
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except (socket.gaierror, UnicodeError):
        raise UnsafeUrl("dns_failed", "Não foi possível encontrar este endereço.") from None
    return tuple(dict.fromkeys(info[4][0] for info in infos))


def test_allowlist() -> set[str]:
    """Hosts allowed to be private ONLY in automated tests (local fixture server).
    Ignored unless APP_ENV=test; a test asserts it is ignored in production."""
    if os.environ.get("APP_ENV") != "test":
        return set()
    return {h.strip().lower() for h in os.environ.get("EGRESS_TEST_ALLOW_PRIVATE", "").split(",") if h.strip()}


def check_host(host: str, port: int) -> tuple[str, ...]:
    """Resolve and require that EVERY address is public (no mixed answers)."""
    if host.lower() in test_allowlist():
        return resolve(host, port)
    if port not in ALLOWED_PORTS:
        raise UnsafeUrl("port_not_allowed", "Endereço não permitido.")
    if host.lower() in ("localhost", "localhost.localdomain") or host.lower().endswith(".localhost"):
        raise UnsafeUrl("private_address", "Endereço não permitido.")
    addresses = resolve(host, port)
    if not addresses or not all(is_public_ip(a) for a in addresses):
        raise UnsafeUrl("private_address", "Endereço não permitido.")
    return addresses


def validate_url(raw: str) -> SafeTarget:
    url = (raw or "").strip()
    if not url or len(url) > MAX_URL_LENGTH or any(ch in url for ch in "\r\n\t\x00 "):
        raise UnsafeUrl("invalid_url", "Link inválido.")
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError:
        raise UnsafeUrl("invalid_url", "Link inválido.") from None
    if parts.scheme.lower() not in ALLOWED_SCHEMES:
        raise UnsafeUrl("scheme_not_allowed", "Use um link http:// ou https://.")
    if parts.username or parts.password or "@" in parts.netloc:
        raise UnsafeUrl("credentials_in_url", "Links com usuário ou senha não são aceitos.")
    host = parts.hostname
    if not host:
        raise UnsafeUrl("invalid_url", "Link inválido.")
    port = port or (443 if parts.scheme.lower() == "https" else 80)
    addresses = check_host(host, port)
    return SafeTarget(url=url, host=host, port=port, addresses=addresses)


def domain_of(url: str) -> str:
    """Registrable-ish domain for statistics (no path, no query: no personal data)."""
    host = (urlsplit(url).hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    return host[:100]
