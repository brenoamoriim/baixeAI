import asyncio
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from app.security import egress_proxy, ssrf

PUBLIC = "93.184.215.14"


@pytest.fixture
def fake_dns(monkeypatch):
    table: dict[str, list[str]] = {}

    def resolve(host, port):
        if host in table:
            return tuple(table[host])
        if host.replace(".", "").isdigit() or ":" in host:
            return (host,)
        raise ssrf.UnsafeUrl("dns_failed", "x")

    monkeypatch.setattr(ssrf, "resolve", resolve)
    return table


@pytest.mark.parametrize("url,code", [
    ("http://127.0.0.1/", "private_address"),
    ("http://localhost/", "private_address"),
    ("http://sub.localhost/", "private_address"),
    ("http://169.254.169.254/latest/meta-data/", "private_address"),
    ("http://[::1]/", "private_address"),
    ("http://[::ffff:127.0.0.1]/", "private_address"),
    ("http://10.0.0.5/", "private_address"),
    ("http://192.168.1.1/", "private_address"),
    ("http://172.16.0.1/", "private_address"),
    ("http://100.64.0.1/", "private_address"),
    ("http://0.0.0.0/", "private_address"),
    ("http://[fd00::1]/", "private_address"),
    ("http://[fe80::1]/", "private_address"),
    ("file:///etc/passwd", "scheme_not_allowed"),
    ("ftp://example.com/x", "scheme_not_allowed"),
    ("gopher://example.com:70/_x", "scheme_not_allowed"),
    ("javascript:alert(1)", "scheme_not_allowed"),
    ("http://user:pass@example.com/", "credentials_in_url"),
    ("http://example.com@127.0.0.1/", "credentials_in_url"),
    ("http://example.com:8080/", "port_not_allowed"),
    ("http://example.com:22/", "port_not_allowed"),
    ("https://example.com:6379/", "port_not_allowed"),
    ("http://exa mple.com/", "invalid_url"),
    ("http://example.com/\r\nHost: evil", "invalid_url"),
    ("", "invalid_url"),
])
def test_rejected_urls(fake_dns, url, code):
    fake_dns["example.com"] = [PUBLIC]
    with pytest.raises(ssrf.UnsafeUrl) as exc:
        ssrf.validate_url(url)
    assert exc.value.code == code


def test_hostname_resolving_to_private_ip_is_rejected(fake_dns):
    fake_dns["evil.example"] = ["10.1.2.3"]
    with pytest.raises(ssrf.UnsafeUrl):
        ssrf.validate_url("https://evil.example/video")


def test_mixed_public_and_private_answers_are_rejected(fake_dns):
    fake_dns["mixed.example"] = [PUBLIC, "127.0.0.1"]
    with pytest.raises(ssrf.UnsafeUrl):
        ssrf.validate_url("https://mixed.example/")


def test_decimal_ip_encoding_is_resolved_and_blocked():
    # 2130706433 == 127.0.0.1 (real resolver, no network needed)
    with pytest.raises(ssrf.UnsafeUrl):
        ssrf.validate_url("http://2130706433/")


def test_public_url_is_accepted(fake_dns):
    fake_dns["videos.example"] = [PUBLIC]
    target = ssrf.validate_url("https://videos.example/watch?v=1")
    assert target.addresses == (PUBLIC,) and target.port == 443
    assert ssrf.domain_of("https://www.Videos.Example/watch?v=1&user=x") == "videos.example"


# ---------------------------------------------------------------- egress proxy


async def _proxy_request(raw: bytes) -> bytes:
    server = await asyncio.start_server(egress_proxy.handle, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    async with server:
        reader, writer = await asyncio.open_connection("127.0.0.1", port)
        writer.write(raw)
        await writer.drain()
        data = b""
        while chunk := await asyncio.wait_for(reader.read(65536), 10):  # until the proxy closes
            data += chunk
        writer.close()
    return data


@pytest.mark.parametrize("request_line", [
    b"CONNECT 127.0.0.1:443 HTTP/1.1\r\n\r\n",
    b"CONNECT 169.254.169.254:80 HTTP/1.1\r\n\r\n",
    b"CONNECT [::1]:443 HTTP/1.1\r\n\r\n",
    b"CONNECT example.com:5432 HTTP/1.1\r\n\r\n",
    b"GET http://localhost/ HTTP/1.1\r\nHost: localhost\r\n\r\n",
    b"GET http://10.0.0.1/ HTTP/1.1\r\nHost: x\r\n\r\n",
])
def test_proxy_blocks_internal_destinations(request_line):
    assert asyncio.run(_proxy_request(request_line)).startswith(b"HTTP/1.1 403")


def test_proxy_blocks_redirect_target_resolving_to_private(fake_dns):
    """Every hop is a new connection through the proxy: a redirect to an internal host is refused."""
    fake_dns["redirected.example"] = ["192.168.0.10"]
    raw = b"CONNECT redirected.example:443 HTTP/1.1\r\n\r\n"
    assert asyncio.run(_proxy_request(raw)).startswith(b"HTTP/1.1 403")


def test_proxy_connects_to_the_validated_ip_not_the_name(monkeypatch):
    """DNS rebinding: the address checked is the address dialled (the name is never re-resolved)."""
    answers = iter([[PUBLIC], ["127.0.0.1"]])  # a rebinding server would flip on the 2nd lookup
    monkeypatch.setattr(ssrf, "resolve", lambda host, port: tuple(next(answers)))
    dialled = {}

    async def fake_open(host, port):
        dialled["host"] = host
        raise OSError("stop here")

    monkeypatch.setattr(asyncio, "open_connection", fake_open)

    async def go():
        try:
            await egress_proxy._open("rebind.example", 443)
        except OSError:
            pass

    asyncio.run(go())
    assert dialled["host"] == PUBLIC


def test_proxy_forwards_plain_http_to_allowed_target(monkeypatch):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            body = f"path={self.path}".encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    httpd = HTTPServer(("127.0.0.1", 0), Handler)
    port = httpd.server_address[1]
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    monkeypatch.setattr(egress_proxy, "pick_address", lambda host, p: "127.0.0.1")  # pretend it is public
    try:
        raw = f"GET http://public.example:{port}/v.mp4?x=1 HTTP/1.1\r\nHost: public.example\r\nProxy-Authorization: x\r\n\r\n"
        data = asyncio.run(_proxy_request(raw.encode()))
    finally:
        httpd.shutdown()
    assert data.startswith(b"HTTP/1.0 200") and data.endswith(b"path=/v.mp4?x=1")


def test_test_allowlist_is_ignored_outside_test_env(monkeypatch):
    monkeypatch.setenv("EGRESS_TEST_ALLOW_PRIVATE", "fixture")
    monkeypatch.setenv("APP_ENV", "production")
    assert egress_proxy._test_allowlist() == set()
    monkeypatch.setenv("APP_ENV", "test")
    assert egress_proxy._test_allowlist() == {"fixture"}
