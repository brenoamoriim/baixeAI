"""Egress filtering proxy: the ONLY way worker-download reaches the internet.

    python -m app.security.egress_proxy          (listens on 0.0.0.0:3128)

For every connection (the user's URL, each redirect, each media/segment URL found by the
extractor) it resolves the host itself, requires that every resolved address is public
(`ssrf.check_host`), and connects to that already-validated IP. Because the check and the
connection use the same address, DNS rebinding cannot swap in an internal IP afterwards.

Supported: `CONNECT host:port` (HTTPS tunnels) and plain HTTP with an absolute URI.
Ports 80/443 only. One request per plain-HTTP connection (Connection: close).
"""

import asyncio
import contextlib
import logging
import os
from urllib.parse import urlsplit

from app.security import ssrf

log = logging.getLogger("egress")
MAX_HEADER = 16 * 1024
CONNECT_TIMEOUT = 10
IDLE_TIMEOUT = 120
MAX_CONNECTIONS = int(os.environ.get("EGRESS_MAX_CONNECTIONS", "64"))
_slots = asyncio.Semaphore(MAX_CONNECTIONS)


_test_allowlist = ssrf.test_allowlist


def pick_address(host: str, port: int) -> str:
    return ssrf.check_host(host, port)[0]


async def _pipe(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    try:
        while data := await asyncio.wait_for(reader.read(65536), IDLE_TIMEOUT):
            writer.write(data)
            await writer.drain()
    except (TimeoutError, ConnectionError, asyncio.IncompleteReadError):
        pass
    finally:
        with contextlib.suppress(Exception):
            writer.close()


async def _reply(writer: asyncio.StreamWriter, status: str) -> None:
    writer.write(f"HTTP/1.1 {status}\r\nConnection: close\r\nContent-Length: 0\r\n\r\n".encode())
    await writer.drain()
    writer.close()


async def _open(host: str, port: int):
    address = await asyncio.get_running_loop().run_in_executor(None, pick_address, host, port)
    return await asyncio.wait_for(asyncio.open_connection(address, port), CONNECT_TIMEOUT)


async def handle(client_reader: asyncio.StreamReader, client_writer: asyncio.StreamWriter) -> None:
    async with _slots:
        try:
            head = await asyncio.wait_for(client_reader.readuntil(b"\r\n\r\n"), 30)
        except (asyncio.LimitOverrunError, asyncio.IncompleteReadError, TimeoutError, ConnectionError):
            client_writer.close()
            return
        if len(head) > MAX_HEADER:
            await _reply(client_writer, "431 Request Header Fields Too Large")
            return
        lines = head.decode("latin-1").split("\r\n")
        try:
            method, target, version = lines[0].split(" ")
        except ValueError:
            await _reply(client_writer, "400 Bad Request")
            return

        try:
            if method.upper() == "CONNECT":
                host, _, port_text = target.rpartition(":")
                host = host.strip("[]")
                port = int(port_text)
                upstream_reader, upstream_writer = await _open(host, port)
                client_writer.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")
                await client_writer.drain()
            else:
                parts = urlsplit(target)
                if parts.scheme != "http" or not parts.hostname:
                    await _reply(client_writer, "400 Bad Request")
                    return
                host, port = parts.hostname, parts.port or 80
                upstream_reader, upstream_writer = await _open(host, port)
                path = parts.path or "/"
                if parts.query:
                    path += "?" + parts.query
                headers = [h for h in lines[1:] if h and not h.lower().startswith(("proxy-", "connection:"))]
                request = f"{method} {path} {version}\r\n" + "\r\n".join(headers) + "\r\nConnection: close\r\n\r\n"
                upstream_writer.write(request.encode("latin-1"))
                await upstream_writer.drain()
        except ssrf.UnsafeUrl as exc:
            if exc.code == "dns_failed":
                log.warning("dns failed: %s", target[:200])
                await _reply(client_writer, "502 Bad Gateway")
            else:
                log.warning("blocked %s: %s", exc.code, target[:200])
                await _reply(client_writer, "403 Blocked By Egress Policy")
            return
        except (ValueError, OSError, TimeoutError):
            await _reply(client_writer, "502 Bad Gateway")
            return

        await asyncio.gather(_pipe(client_reader, upstream_writer), _pipe(upstream_reader, client_writer))


async def serve(host: str = "0.0.0.0", port: int = 3128) -> None:  # noqa: S104 - container-internal
    server = await asyncio.start_server(handle, host, port, limit=MAX_HEADER * 2)
    async with server:
        await server.serve_forever()


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    asyncio.run(serve(port=int(os.environ.get("EGRESS_PORT", "3128"))))


if __name__ == "__main__":
    main()
