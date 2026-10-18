"""Admin command line.  Run inside the API container, e.g.:

    docker compose exec api python -m app.cli create-admin --email voce@exemplo.com
    docker compose exec api python -m app.cli grant-plan --email x@y.com --plan pro

Payments are Phase 4: until then plans/packages are granted here, never from the web.
"""

import argparse
import getpass
import json
import sys
import uuid

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core import clock
from app.core.config import get_settings
from app.core.db import SessionLocal
from app.models import (
    AuditEvent,
    CreditCostRule,
    CreditPackage,
    Plan,
    Subscription,
    SystemSetting,
    ToolCapability,
    ToolDefinition,
    User,
)
from app.security.crypto import hash_password
from app.services import credits
from app.services.settings import DEFAULTS
from app.tools.converter import matrix

PLANS = [
    {"code": "free", "name": "Gratuita", "kind": "free", "price_cents": 0},
    {"code": "pro", "name": "Pro", "kind": "recurring", "price_cents": 2490, "credits_per_cycle": 300},
    {"code": "premium", "name": "Premium", "kind": "recurring", "price_cents": 3990, "credits_per_cycle": 800},
    {"code": "lifetime", "name": "Vitalícia", "kind": "lifetime", "price_cents": 12000, "is_unlimited": True},
]
TOOLS = [
    {
        "id": "video_downloader",
        "display_name": "Baixador de vídeos",
        "package_display_name": "Baixador de vídeos",
        "queue": "download",
        "sort_order": 1,
    },
    {
        "id": "converter",
        "display_name": "Conversores",
        "package_display_name": "Conversores",
        "queue": "light",
        "sort_order": 2,
    },
    {
        "id": "background_remover",
        "display_name": "Removedor de fundo",
        "package_display_name": "Removedor de fundo",
        "queue": "ai",
        "sort_order": 3,
    },
    {
        "id": "object_remover",
        "display_name": "Removedor de objetos",
        "package_display_name": "Removedor de objetos",
        "queue": "ai",
        "sort_order": 4,
    },
]
DEV_TOOL = {
    "id": "echo",
    "display_name": "Eco (teste)",
    "package_display_name": "Eco",
    "queue": "default",
    "sort_order": 99,
    "dev_only": True,
}
PACKAGES = [
    {"code": "pack_video_downloader_10", "tool_id": "video_downloader", "credits": 10, "price_cents": 990},
    {"code": "pack_converter_10", "tool_id": "converter", "credits": 10, "price_cents": 490},
    {"code": "pack_object_remover_10", "tool_id": "object_remover", "credits": 10, "price_cents": 490},
    {"code": "pack_background_remover_10", "tool_id": "background_remover", "credits": 10, "price_cents": 490},
]


def _insert_missing(db, model, rows, key):
    for row in rows:
        db.execute(pg_insert(model).values(**row).on_conflict_do_nothing(index_elements=[key]))


def seed() -> None:
    """Idempotent: creates missing rows, never overwrites values edited by an admin."""
    with SessionLocal() as db, db.begin():
        _insert_missing(db, Plan, [{"id": uuid.uuid4(), **p} for p in PLANS], "code")
        _insert_missing(db, ToolDefinition, TOOLS, "id")
        _insert_missing(db, CreditPackage, [{"id": uuid.uuid4(), **p} for p in PACKAGES], "code")
        _insert_missing(
            db,
            SystemSetting,
            [{"key": k, "value": v, "description": d} for k, (v, d) in DEFAULTS.items()],
            "key",
        )
        for key, (value, _) in DEFAULTS.items():  # fill settings that exist but were never decided (null)
            if value is not None:
                db.execute(
                    text(
                        "UPDATE system_settings SET value = CAST(:v AS jsonb) WHERE key = :k AND value = 'null'::jsonb"
                    ),
                    {"v": json.dumps(value), "k": key},
                )
        if not db.execute(select(CreditCostRule.id).limit(1)).first():
            db.add_all(
                [
                    CreditCostRule(tool_id="converter", category="video", cost=2, priority=10),
                    CreditCostRule(tool_id="video_downloader", min_duration_seconds=121, cost=2, priority=10),
                ]
            )
        _sync_converter_capabilities(db)
        _sync_ai_capabilities(db)
        _sync_downloader_capabilities(db)
        if not get_settings().is_production:
            _insert_missing(db, ToolDefinition, [DEV_TOOL], "id")
            db.execute(
                pg_insert(ToolCapability)
                .values(
                    id=uuid.uuid4(),
                    tool_id="echo",
                    category="text",
                    input_format="text",
                    output_format="txt",
                    status="available",
                    engine="python",
                    options_schema={},
                    notes="Ferramenta de teste (somente dev/test)",
                )
                .on_conflict_do_nothing(constraint="uq_tool_capabilities_io")
            )
    print("seed ok")


def _sync_converter_capabilities(db) -> None:
    """Availability follows verification: only combinations listed in verified.json (a real
    conversion passed in the worker image) are `available`; every other candidate is `planned`."""
    verified = matrix.verified_keys()
    for c in matrix.candidates():
        status = "available" if c.key in verified else "planned"
        db.execute(
            pg_insert(ToolCapability)
            .values(
                id=uuid.uuid4(),
                tool_id="converter",
                category=c.category,
                input_format=c.input_format,
                output_format=c.output_format,
                status=status,
                engine=c.engine,
                options_schema={},
                notes=c.note(),
            )
            .on_conflict_do_update(
                constraint="uq_tool_capabilities_io",
                set_={"status": status, "engine": c.engine, "notes": c.note(), "category": c.category},
            )
        )


def _sync_ai_capabilities(db) -> None:
    """Same rule for the AI tools: `available` only if app/tools/ai/verified.json lists it."""
    from app.tools.ai import verify as ai_verify

    verified = ai_verify.verified_keys()
    engine = {"background_remover": "isnet-onnx", "object_remover": "lama-onnx"}
    for c in ai_verify.candidates():
        status = "available" if c.key in verified else "planned"
        db.execute(
            pg_insert(ToolCapability)
            .values(
                id=uuid.uuid4(),
                tool_id=c.tool_id,
                category="image",
                input_format=c.input_format,
                output_format=c.output_format,
                status=status,
                engine=engine[c.tool_id],
                options_schema={},
            )
            .on_conflict_do_update(constraint="uq_tool_capabilities_io", set_={"status": status})
        )


def _sync_downloader_capabilities(db) -> None:
    """`available` only if the real integration check (downloader/verified.json) passed."""
    from app.tools.downloader import verify as dl_verify

    verified = dl_verify.verified_keys()
    for key in dl_verify.CAPABILITIES:
        output = key.split("->")[1]
        status = "available" if key in verified else "planned"
        db.execute(
            pg_insert(ToolCapability)
            .values(
                id=uuid.uuid4(),
                tool_id="video_downloader",
                category="video",
                input_format="url",
                output_format=output,
                status=status,
                engine="yt-dlp",
                options_schema={},
            )
            .on_conflict_do_update(constraint="uq_tool_capabilities_io", set_={"status": status})
        )


def _user(db, email: str) -> User:
    user = db.execute(select(User).where(User.email == email.lower())).scalar_one_or_none()
    if user is None:
        sys.exit(f"usuário não encontrado: {email}")
    return user


def _audit(db, action: str, target: User, **meta) -> None:
    db.add(AuditEvent(actor_type="cli", action=action, target_type="user", target_id=str(target.id), metadata_=meta))


def create_admin(email: str, password: str | None) -> None:
    password = password or getpass.getpass("Senha (mín. 10 caracteres): ")
    if len(password) < 10:
        sys.exit("senha curta demais")
    with SessionLocal() as db, db.begin():
        existing = db.execute(select(User).where(User.email == email.lower())).scalar_one_or_none()
        if existing:
            existing.role = "admin"
            user = existing
        else:
            user = User(
                email=email.lower(), password_hash=hash_password(password), role="admin", email_verified_at=clock.now()
            )
            db.add(user)
            db.flush()
        _audit(db, "cli_create_admin", user)
    print(f"admin ok: {email}")


def grant_plan(email: str, plan_code: str) -> None:
    now = clock.now()
    with SessionLocal() as db, db.begin():
        user = _user(db, email)
        plan = db.execute(select(Plan).where(Plan.code == plan_code, Plan.kind == "recurring")).scalar_one()
        sub = Subscription(user_id=user.id, plan_id=plan.id, kind="recurring", status="active", renewal_mode="admin")
        db.add(sub)
        db.flush()
        credits.start_plan_cycle(db, sub, period_start=now, at=now, actor="cli")
        _audit(db, "cli_grant_plan", user, plan=plan_code)
    print(f"plano {plan_code} concedido a {email}")


def set_next_plan(email: str, plan_code: str) -> None:
    with SessionLocal() as db, db.begin():
        user = _user(db, email)
        sub = credits.active_recurring(db, user.id, clock.now())
        if sub is None:
            sys.exit("sem assinatura ativa")
        plan = db.execute(select(Plan).where(Plan.code == plan_code, Plan.kind == "recurring")).scalar_one()
        sub.next_plan_id = None if plan.id == sub.plan_id else plan.id
        _audit(db, "cli_set_next_plan", user, plan=plan_code)
    print(f"troca para {plan_code} agendada para o próximo ciclo")


def renew_plan(email: str) -> None:
    """Simulates a confirmed renewal (Phase 4 will call the same service from the webhook)."""
    now = clock.now()
    with SessionLocal() as db, db.begin():
        user = _user(db, email)
        sub = db.execute(
            select(Subscription).where(
                Subscription.user_id == user.id,
                Subscription.kind == "recurring",
                Subscription.status.in_(("active", "past_due")),
            )
        ).scalar_one()
        start = max(sub.current_period_end, now) if sub.current_period_end else now
        credits.start_plan_cycle(db, sub, period_start=start, at=now, actor="cli")
        _audit(db, "cli_renew_plan", user)
    print("ciclo renovado")


def grant_package(email: str, tool_id: str) -> None:
    now = clock.now()
    with SessionLocal() as db, db.begin():
        user = _user(db, email)
        package = db.execute(select(CreditPackage).where(CreditPackage.tool_id == tool_id)).scalar_one()
        credits.lock_user(db, user.id)
        credits.grant_package(db, user.id, package, at=now, actor="cli")
        _audit(db, "cli_grant_package", user, package=package.code)
    print(f"pacote {package.code} concedido")


def grant_lifetime(email: str) -> None:
    with SessionLocal() as db, db.begin():
        user = _user(db, email)
        plan = db.execute(select(Plan).where(Plan.code == "lifetime")).scalar_one()
        db.add(
            Subscription(
                user_id=user.id,
                plan_id=plan.id,
                kind="lifetime",
                status="active",
                renewal_mode="admin",
                current_period_start=clock.now(),
            )
        )
        _audit(db, "cli_grant_lifetime", user)
    print("vitalício concedido")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("seed")
    p = sub.add_parser("create-admin")
    p.add_argument("--email", required=True)
    p.add_argument("--password", help="omita para digitar sem eco")
    for name in ("grant-plan", "set-next-plan"):
        p = sub.add_parser(name)
        p.add_argument("--email", required=True)
        p.add_argument("--plan", required=True, choices=["pro", "premium"])
    p = sub.add_parser("renew-plan")
    p.add_argument("--email", required=True)
    p = sub.add_parser("grant-package")
    p.add_argument("--email", required=True)
    p.add_argument("--tool", required=True)
    p = sub.add_parser("grant-lifetime")
    p.add_argument("--email", required=True)
    args = parser.parse_args(argv)

    match args.cmd:
        case "seed":
            seed()
        case "create-admin":
            create_admin(args.email, args.password)
        case "grant-plan":
            grant_plan(args.email, args.plan)
        case "set-next-plan":
            set_next_plan(args.email, args.plan)
        case "renew-plan":
            renew_plan(args.email)
        case "grant-package":
            grant_package(args.email, args.tool)
        case "grant-lifetime":
            grant_lifetime(args.email)


if __name__ == "__main__":
    main()
