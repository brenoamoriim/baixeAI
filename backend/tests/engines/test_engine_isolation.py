"""Run INSIDE a live engine worker (worker-light / worker-media / worker-ai):

    docker compose exec -T -e TESTS_NO_DB=1 worker-light python -m pytest tests/engines/test_engine_isolation.py \
        -o addopts="" -p no:cacheprovider

Engine workers process untrusted files with large native code (LibreOffice, libvips, FFmpeg, ONNX). If one of
them is exploited, the attacker must find no database, no secrets, no internet and no cloud metadata.
"""

import os
import socket
from pathlib import Path

import pytest

in_engine = pytest.mark.skipif(
    b"PROCESS_ROLE=engine" not in Path("/proc/1/environ").read_bytes() if Path("/proc/1/environ").exists() else True,
    reason="runs inside a live engine worker container",
)


def _tcp(host: str, port: int) -> bool:
    try:
        socket.create_connection((host, port), timeout=4).close()
        return True
    except OSError:
        return False


@in_engine
def test_engine_cannot_reach_database_internet_or_metadata():
    assert not _tcp("db", 5432), "engine worker must not reach Postgres"
    assert not _tcp("api", 8000), "engine worker must not reach the API"
    assert not _tcp("1.1.1.1", 443), "engine worker must not have internet"
    assert not _tcp("169.254.169.254", 80), "cloud metadata must be unreachable"
    assert _tcp("redis", 6379), "the broker is required"


@in_engine
def test_engine_process_environment_has_no_secrets():
    # /proc/1/environ is the worker's ORIGINAL environment (what an exploited child process could read)
    names = {item.split(b"=", 1)[0].decode() for item in Path("/proc/1/environ").read_bytes().split(b"\0") if item}
    forbidden = {"DATABASE_URL", "TEST_DATABASE_URL", "SECRET_KEY", "SIGNED_URL_SECRET", "GUEST_ID_HMAC_SECRET",
                 "MP_ACCESS_TOKEN", "MP_WEBHOOK_SECRET", "POSTGRES_PASSWORD"}
    assert not (names & forbidden), names & forbidden


@in_engine
def test_engine_runs_unprivileged_on_read_only_root():
    assert os.getuid() != 0
    with pytest.raises(OSError):
        Path("/app-write-test").write_text("x")
    status = Path("/proc/self/status").read_text()
    cap_eff = next(line for line in status.splitlines() if line.startswith("CapEff:")).split()[1]
    assert int(cap_eff, 16) == 0, "no Linux capabilities"
    assert "NoNewPrivs:\t1" in status
