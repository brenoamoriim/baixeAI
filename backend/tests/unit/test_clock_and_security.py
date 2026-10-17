from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from app.core import clock
from app.security import crypto
from app.storage.base import LocalStorage, new_key


@pytest.mark.parametrize(
    ("start", "expected"),
    [
        (datetime(2026, 1, 15, 12, tzinfo=UTC), datetime(2026, 2, 15, 12, tzinfo=UTC)),
        (datetime(2026, 1, 31, 12, tzinfo=UTC), datetime(2026, 2, 28, 12, tzinfo=UTC)),
        (datetime(2028, 1, 31, 12, tzinfo=UTC), datetime(2028, 2, 29, 12, tzinfo=UTC)),  # leap
        (datetime(2026, 12, 10, tzinfo=UTC), datetime(2027, 1, 10, tzinfo=UTC)),
        (datetime(2026, 3, 31, tzinfo=UTC), datetime(2026, 4, 30, tzinfo=UTC)),
    ],
)
def test_add_months_clamps_to_month_end(start, expected):
    assert clock.add_months(start, 1) == expected


def test_business_day_is_sao_paulo_midnight():
    start, end = clock.local_day_bounds(date(2026, 10, 17))
    # America/Sao_Paulo is UTC-3 (no DST since 2019).
    assert start == datetime(2026, 10, 17, 3, tzinfo=UTC)
    assert end == datetime(2026, 10, 18, 3, tzinfo=UTC)
    assert clock.local_date(datetime(2026, 10, 18, 2, 59, tzinfo=UTC)) == date(2026, 10, 17)
    assert clock.local_date(datetime(2026, 10, 18, 3, 0, tzinfo=UTC)) == date(2026, 10, 18)


def test_freeze_requires_aware_datetime():
    with pytest.raises(ValueError):
        clock.freeze(datetime(2026, 1, 1))  # noqa: DTZ001


def test_password_hash_is_argon2id_and_verifies():
    hashed = crypto.hash_password("uma-senha-boa")
    assert hashed.startswith("$argon2id$")
    assert crypto.verify_password(hashed, "uma-senha-boa")
    assert not crypto.verify_password(hashed, "errada")
    assert not crypto.verify_password(None, "qualquer")
    assert not crypto.verify_password("lixo-que-nao-e-hash", "x")


def test_signature_detects_tampering():
    sig = crypto.sign("job:123:u:1")
    assert crypto.verify_signature("job:123:u:1", sig)
    assert not crypto.verify_signature("job:124:u:1", sig)
    assert not crypto.verify_signature("job:123:u:1", "0" * 64)


def test_storage_rejects_path_traversal(tmp_path: Path):
    storage = LocalStorage(str(tmp_path))
    for bad in ("../etc/passwd", "jobs/../../x", "/abs/path", "jobs/\\x", "JOBS/A"):
        with pytest.raises(ValueError):
            storage.open_path(bad)


def test_storage_keys_are_server_generated(tmp_path: Path):
    key = new_key("jobs/abc", "../../EXE")
    assert key.startswith("jobs/abc/") and key.endswith(".exe") and ".." not in key
    source = tmp_path / "src.txt"
    source.write_text("x")
    storage = LocalStorage(str(tmp_path / "root"))
    storage.save_file(key, source)
    assert storage.open_path(key).read_text() == "x"
    storage.delete(key)
    assert not storage.exists(key)
