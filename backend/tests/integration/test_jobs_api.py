import time
import uuid
from datetime import timedelta

from sqlalchemy import select, update

from app.core import clock
from app.core.db import SessionLocal
from app.models import (
    CreditCostRule,
    CreditReservation,
    Plan,
    ProcessingJob,
    Subscription,
    SystemSetting,
    ToolCapability,
    UsageRecord,
)
from app.services import jobs
from tests.conftest import make_user


def _credits(client) -> int:
    return client.get("/api/v1/me/credits").json()["total_general"]


def _logged(client, **kwargs):
    user = make_user(**kwargs)
    client.login(user.email)
    return user


# ---------------------------------------------------------------- happy path & refunds


def test_job_completes_charges_one_and_downloads(client):
    _logged(client)
    r = client.create_echo(text="conteúdo de teste")
    assert r.status_code == 201, r.text
    job = r.json()
    assert job["status"] == "completed" and job["credit_cost"] == 1
    assert _credits(client) == 4

    link = client.post(f"/api/v1/jobs/{job['id']}/download-link").json()["url"]
    file = client.get(link)
    assert file.status_code == 200 and file.text == "conteúdo de teste"
    assert "attachment" in file.headers["content-disposition"]


def test_system_failure_refunds(client):
    _logged(client)
    job = client.create_echo(simulate="system_error").json()
    assert job["status"] == "failed" and job["error_class"] == "system"
    assert _credits(client) == 5


def test_user_input_failure_is_charged(client):
    _logged(client)
    job = client.create_echo(simulate="user_error").json()
    assert job["status"] == "failed" and job["error_class"] == "user_input"
    assert _credits(client) == 4


def test_timeout_refunds(client, monkeypatch):
    from app.tools.echo.handler import EchoHandler

    def boom(self, options, work_dir):
        raise TimeoutError

    monkeypatch.setattr(EchoHandler, "execute", boom)
    _logged(client)
    job = client.create_echo().json()
    assert job["status"] == "failed" and job["error_class"] == "timeout"
    assert _credits(client) == 5  # D11


def test_invalid_options_cost_nothing(client):
    _logged(client)
    r = client.create_echo(text="")
    assert r.status_code == 400 and r.json()["error"]["code"] == "invalid_options"
    assert _credits(client) == 5


def test_unavailable_capability_is_rejected_before_charge(client):
    _logged(client)
    with SessionLocal() as db, db.begin():
        db.execute(update(ToolCapability).values(status="planned"))
    assert client.create_echo().status_code == 404
    r = client.post("/api/v1/jobs", json={"tool_id": "converter", "input_format": "docx",
                                          "output_format": "pdf"}, headers={"Idempotency-Key": uuid.uuid4().hex})
    assert r.status_code == 404
    assert _credits(client) == 5


def test_no_cancel_endpoint(client):
    """D12: a started action consumes the credit; there is no cancel route."""
    _logged(client)
    job = client.create_echo().json()
    assert client.post(f"/api/v1/jobs/{job['id']}/cancel").status_code in (404, 405)
    assert client.delete(f"/api/v1/jobs/{job['id']}").status_code in (404, 405)


# ---------------------------------------------------------------- idempotency


def test_same_idempotency_key_returns_same_job_without_new_charge(client):
    _logged(client)
    first = client.create_echo(key="chave-fixa-123")
    second = client.create_echo(key="chave-fixa-123")
    assert first.status_code == 201 and second.status_code == 200
    assert first.json()["id"] == second.json()["id"]
    assert _credits(client) == 4


def test_idempotency_key_required_and_validated(client):
    _logged(client)
    r = client.post("/api/v1/jobs", json={"tool_id": "echo", "input_format": "text",
                                          "output_format": "txt", "options": {"text": "x"}})
    assert r.status_code == 422
    r = client.create_echo(key="curta")
    assert r.status_code == 400


# ---------------------------------------------------------------- guest


def test_guest_gets_one_credit_once(client):
    first = client.create_echo()
    assert first.status_code == 201 and first.json()["charged_from"] == "guest"
    second = client.create_echo()
    assert second.status_code == 402
    assert "Crie uma conta" in second.json()["error"]["message"]


def test_guest_refunded_on_system_failure_can_retry(client):
    assert client.create_echo(simulate="system_error").json()["status"] == "failed"
    assert client.create_echo().status_code == 201


def test_guest_ip_daily_cap(new_client):
    # default: 3 new guest allowances per IP per day; each new client = new cookie, same IP
    codes = [new_client().create_echo().status_code for _ in range(4)]
    assert codes == [201, 201, 201, 429]


def test_guest_can_download_own_file_but_not_others(new_client):
    owner, stranger = new_client(), new_client()
    job = owner.create_echo(text="do visitante").json()
    link = owner.post(f"/api/v1/jobs/{job['id']}/download-link").json()["url"]
    assert owner.get(link).text == "do visitante"
    assert stranger.get(f"/api/v1/jobs/{job['id']}").status_code == 404
    assert stranger.get(link).status_code == 404  # signature alone is not enough


# ---------------------------------------------------------------- authorization / IDOR


def test_user_cannot_read_or_download_another_users_job(new_client):
    alice, bob = new_client(), new_client()
    _logged(alice)
    _logged(bob)
    job = alice.create_echo(text="segredo").json()
    link = alice.post(f"/api/v1/jobs/{job['id']}/download-link").json()["url"]
    assert bob.get(f"/api/v1/jobs/{job['id']}").status_code == 404
    assert bob.post(f"/api/v1/jobs/{job['id']}/download-link").status_code == 404
    assert bob.get(link).status_code == 404
    assert all(j["id"] != job["id"] for j in bob.get("/api/v1/jobs").json()["jobs"])


def test_download_link_tampering_and_expiry(client):
    _logged(client)
    job = client.create_echo().json()
    url = client.post(f"/api/v1/jobs/{job['id']}/download-link").json()["url"]
    tampered = url[:-4] + ("0000" if not url.endswith("0000") else "1111")
    assert client.get(tampered).status_code == 404
    expired = url.replace(f"exp={url.split('exp=')[1].split('&')[0]}", f"exp={int(time.time()) - 10}")
    assert client.get(expired).status_code == 404


# ---------------------------------------------------------------- pricing (D1) and limits


def test_cost_rule_by_category_is_applied(client):
    _logged(client)
    with SessionLocal() as db, db.begin():
        db.add(CreditCostRule(tool_id="echo", category="text", cost=2, priority=5))
    job = client.create_echo().json()
    assert job["credit_cost"] == 2 and _credits(client) == 3


def test_operation_costing_more_than_balance_is_refused(client):
    _logged(client)
    with SessionLocal() as db, db.begin():
        db.add(CreditCostRule(tool_id="echo", category="text", cost=6, priority=5))
    r = client.create_echo()
    assert r.status_code == 402 and _credits(client) == 5


def test_lifetime_is_not_charged_but_has_fair_use_caps(client):
    user = _logged(client)
    with SessionLocal() as db, db.begin():
        plan = db.execute(select(Plan).where(Plan.code == "lifetime")).scalar_one()
        db.add(Subscription(user_id=user.id, plan_id=plan.id, kind="lifetime", status="active",
                            renewal_mode="admin"))
        db.execute(update(SystemSetting).where(SystemSetting.key == "lifetime_daily_cap").values(value=3))
    for _ in range(3):
        job = client.create_echo().json()
        assert job["status"] == "completed" and job["charged_from"] == "lifetime"
    r = client.create_echo()
    assert r.status_code == 429 and r.json()["error"]["code"] == "fair_use_limit"
    with SessionLocal() as db:
        assert db.execute(select(CreditReservation)).first() is None  # no ledger usage
        assert {u.credits_charged for u in db.execute(select(UsageRecord)).scalars()} == {0}


def test_lifetime_concurrency_cap(client, monkeypatch):
    user = _logged(client)
    monkeypatch.setattr(jobs, "dispatch", lambda db, job: None)  # keep jobs queued
    with SessionLocal() as db, db.begin():
        plan = db.execute(select(Plan).where(Plan.code == "lifetime")).scalar_one()
        db.add(Subscription(user_id=user.id, plan_id=plan.id, kind="lifetime", status="active",
                            renewal_mode="admin"))
    assert client.create_echo().status_code == 201
    assert client.create_echo().status_code == 201
    assert client.create_echo().status_code == 429  # 2 simultaneous max (D4)


# ---------------------------------------------------------------- maintenance


def test_stuck_job_is_failed_and_refunded(client, monkeypatch):
    _logged(client)
    monkeypatch.setattr(jobs, "dispatch", lambda db, job: None)
    job = client.create_echo().json()
    assert job["status"] == "queued" and _credits(client) == 4
    assert jobs.sweep_stuck_jobs(SessionLocal, at=clock.now() + timedelta(hours=1)) == 1
    assert client.get(f"/api/v1/jobs/{job['id']}").json()["error_code"] == "stuck"
    assert _credits(client) == 5


def test_run_is_idempotent_when_task_is_redelivered(client):
    _logged(client)
    job = client.create_echo().json()
    with SessionLocal() as db:
        jobs.run(db, uuid.UUID(job["id"]))  # acks_late redelivery: must be a no-op
    assert _credits(client) == 4
    with SessionLocal() as db:
        assert db.execute(select(UsageRecord)).scalars().all().__len__() == 1


def test_expired_outputs_are_deleted(client):
    _logged(client)
    job = client.create_echo().json()
    assert jobs.cleanup_expired_outputs(SessionLocal, at=clock.now() + timedelta(hours=3)) == 1
    assert client.get(f"/api/v1/jobs/{job['id']}").json()["status"] == "expired"
    assert client.post(f"/api/v1/jobs/{job['id']}/download-link").status_code == 404
    with SessionLocal() as db:
        assert db.get(ProcessingJob, uuid.UUID(job["id"])).output_key is not None


def test_tools_listing_exposes_only_available(client):
    tools = {t["id"]: t for t in client.get("/api/v1/tools").json()["tools"]}
    assert tools["echo"]["status"] == "available"
    for real in ("video_downloader", "converter", "background_remover", "object_remover"):
        assert tools[real]["status"] == "coming_soon" and tools[real]["capabilities"] == []
