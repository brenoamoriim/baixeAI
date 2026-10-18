"""Runtime settings stored in `system_settings` (editable by admins, no deploy)."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import SystemSetting

# Defaults used by the seed and as fallback when a key is missing.
DEFAULTS: dict[str, tuple[Any, str]] = {
    "daily_free_credits": (5, "Fichas diárias da conta gratuita"),
    "guest_credits": (1, "Fichas do visitante (uma única vez)"),
    "guest_max_per_ip_per_day": (3, "Novas permissões de visitante por IP por dia"),
    "require_verified_email_for_credits": (
        True,
        "Conta precisa de e-mail verificado para usar fichas diárias",
    ),
    "credit_consumption_order": (
        ["daily", "compensation", "plan", "package"],
        "Ordem de consumo das fichas (PRD §4)",
    ),
    "package_validity_days": (90, "Validade das fichas avulsas em dias"),
    "compensation_validity_hours": (24, "Validade da ficha devolvida após o vencimento do bucket"),
    "lifetime_max_concurrent_jobs": (2, "Vitalício: jobs simultâneos"),
    "lifetime_daily_cap": (50, "Vitalício: operações por dia"),
    "lifetime_max_seats": (None, "Vitalício: vagas do lote (None = sem venda definida)"),
    "max_pending_jobs_per_user": (5, "Jobs em fila/processamento por usuário (não vitalício)"),
    "job_stuck_after_seconds": (1800, "Job sem conclusão após este tempo é considerado preso"),
    "limits_bytes": (
        {
            "image": 20 * 1024 * 1024,
            "document": 25 * 1024 * 1024,
            "audio": 50 * 1024 * 1024,
            "video": 95 * 1024 * 1024,
        },
        "Limites de upload por categoria (PRD §6.2, D10)",
    ),
    "video_max_seconds": (600, "Duração máxima de vídeo (segundos)"),
    "video_max_pixels": (3840 * 2160, "Resolução máxima de vídeo (pixels por quadro)"),
    "audio_max_seconds": (3600, "Duração máxima de áudio (segundos)"),
    "image_max_pixels": (40_000_000, "Resolução máxima de imagem (pixels)"),
    "doc_max_pages": (300, "Máximo de páginas de PDF"),
}


def get_setting(db: Session, key: str) -> Any:
    row = db.execute(select(SystemSetting.value).where(SystemSetting.key == key)).scalar_one_or_none()
    if row is not None:
        return row
    if key in DEFAULTS:
        return DEFAULTS[key][0]
    raise KeyError(key)
