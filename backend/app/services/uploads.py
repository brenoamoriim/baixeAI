"""Uploads: stream to disk with a size cap -> sniff real format -> store -> probe in an isolated
worker (decode headers, duration, pixels) BEFORE any credit is charged.

An upload is owned by a user or by a guest's anonymous cookie (hashed). Jobs can only use an
upload that belongs to the same actor, is `ready` and has not expired.
"""

import logging
import re
import shutil
import tempfile
import uuid
from datetime import timedelta
from pathlib import Path
from typing import BinaryIO

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import clock
from app.core.config import get_settings
from app.core.errors import AppError, NotFound
from app.models import Upload
from app.security.crypto import keyed_hash
from app.security.file_sniffing import CATEGORY, SniffError, sniff
from app.services.settings import get_setting
from app.storage.base import get_storage, new_key
from app.tools.base import ToolSystemError, ToolUserError
from app.tools.converter import documents, images, matrix, media

log = logging.getLogger(__name__)
CHUNK = 1024 * 1024
CATEGORY_PT = {"document": "documentos", "image": "imagens", "audio": "áudio", "video": "vídeo"}


class TooLarge(AppError):
    status_code = 413
    code = "file_too_large"


def _owner_filter(actor):
    if actor.user_id is not None:
        return Upload.owner_user_id == actor.user_id
    return Upload.owner_anon_hash == keyed_hash(actor.guest_anon_id or "", purpose="guest")


def safe_display_name(name: str | None) -> str:
    """Kept only as metadata for the download filename; never used as a path."""
    base = (name or "arquivo").replace("\\", "/").rsplit("/", 1)[-1]
    base = re.sub(r"[\x00-\x1f\x7f]", "", base).strip()
    return base[:200] or "arquivo"


def _human_mb(n: int) -> str:
    return f"{n // (1024 * 1024)} MB"


def create(db: Session, actor, stream: BinaryIO, filename: str | None) -> Upload:
    limits = get_setting(db, "limits_bytes")
    db.commit()  # end the read-only transaction; the insert below opens its own
    hard_cap = max(limits.values())
    display = safe_display_name(filename)
    declared = display.rsplit(".", 1)[-1] if "." in display else ""

    with tempfile.TemporaryDirectory(prefix="upload-") as tmp:
        path = Path(tmp) / "incoming"
        size = 0
        with path.open("wb") as out:
            while chunk := stream.read(CHUNK):
                size += len(chunk)
                if size > hard_cap:
                    raise TooLarge(f"Arquivo grande demais (máximo {_human_mb(hard_cap)}).")
                out.write(chunk)
        if size == 0:
            raise AppError("O arquivo está vazio.", code="empty_file")
        try:
            detected = sniff(path, declared)
        except SniffError as exc:
            raise AppError(exc.message, code=exc.code) from None
        limit = int(limits[detected.category])
        if size > limit:
            raise TooLarge(f"Arquivo grande demais para {CATEGORY_PT[detected.category]} (máximo {_human_mb(limit)}).")

        upload_id = uuid.uuid4()
        key = new_key(f"uploads/{upload_id.hex}", detected.format)
        get_storage().save_file(key, path)

    upload = Upload(
        id=upload_id,
        owner_user_id=actor.user_id,
        owner_anon_hash=None if actor.user_id else keyed_hash(actor.guest_anon_id, purpose="guest"),
        storage_key=key,
        original_name=display,
        format=detected.format,
        category=detected.category,
        size_bytes=size,
        status="probing",
        meta={"declared_extension": declared.lower()},
        expires_at=clock.now() + timedelta(hours=get_settings().file_retention_hours),
    )
    with db.begin():
        db.add(upload)
    _dispatch_probe(db, upload)
    return upload


def _dispatch_probe(db: Session, upload: Upload) -> None:
    from app.workers.tasks import probe_upload

    try:
        probe_upload.apply_async(args=[str(upload.id)], queue=matrix.QUEUE_BY_CATEGORY[upload.category])
    except Exception:
        log.exception("probe enqueue failed")
        _finish(db, upload.id, error=("probe_unavailable", "Não foi possível analisar o arquivo agora."))


def get_owned(db: Session, actor, upload_id: uuid.UUID) -> Upload:
    upload = db.execute(select(Upload).where(Upload.id == upload_id, _owner_filter(actor))).scalar_one_or_none()
    if upload is None or upload.expires_at <= clock.now():
        raise NotFound("Arquivo não encontrado ou expirado. Envie novamente.", code="upload_not_found")
    return upload


# --------------------------------------------------------------------------- probe (worker side)


def _finish(db: Session, upload_id: uuid.UUID, *, meta: dict | None = None, fmt: str | None = None,
            error: tuple[str, str] | None = None) -> None:
    if db.in_transaction():
        db.commit()  # close reads done while probing (settings lookups)
    with db.begin():
        upload = db.get(Upload, upload_id, with_for_update=True)
        if upload is None or upload.status != "probing":
            return
        if error:
            upload.status, (upload.error_code, upload.error_message) = "rejected", error
            get_storage().delete(upload.storage_key)
            return
        upload.meta = {**upload.meta, **(meta or {})}
        if fmt and fmt != upload.format:
            upload.format = fmt
            upload.category = CATEGORY[fmt]
        upload.status = "ready"


def probe(db: Session, upload_id: uuid.UUID) -> None:
    upload = db.get(Upload, upload_id)
    if upload is None or upload.status != "probing":
        return
    fmt, category = upload.format, upload.category
    db.commit()
    work = Path(tempfile.mkdtemp(prefix="probe-"))
    try:
        local = work / f"input.{fmt}"
        shutil.copyfile(get_storage().open_path(upload.storage_key), local)
        meta, new_fmt = _probe_file(db, local, fmt, category, work)
        _finish(db, upload_id, meta=meta, fmt=new_fmt)
    except ToolUserError as exc:
        _finish(db, upload_id, error=(exc.code, exc.message))
    except (ToolSystemError, TimeoutError, OSError):
        log.exception("probe failed")
        _finish(db, upload_id, error=("probe_failed", "Não foi possível analisar o arquivo. Tente novamente."))
    finally:
        shutil.rmtree(work, ignore_errors=True)


def _probe_file(db: Session, path: Path, fmt: str, category: str, work: Path) -> tuple[dict, str]:
    if category == "image":
        width, height = images.dimensions(path, fmt, work)
        if width * height > int(get_setting(db, "image_max_pixels")):
            raise ToolUserError("image_too_large", "A imagem tem resolução grande demais (máximo 40 megapixels).")
        return {"width": width, "height": height}, fmt
    if category == "document":
        if fmt == "pdf":
            pages = documents.page_count(path, work)
            if pages > int(get_setting(db, "doc_max_pages")):
                raise ToolUserError("too_many_pages", "O documento tem páginas demais.")
            return {"pages": pages}, fmt
        return {}, fmt
    info = media.probe(path, fmt, work)
    duration = info["duration_seconds"]
    new_fmt = info.pop("format")
    if info["has_video"]:
        if duration > int(get_setting(db, "video_max_seconds")):
            raise ToolUserError("too_long", "O vídeo é longo demais (máximo 10 minutos).")
        if info["width"] * info["height"] > int(get_setting(db, "video_max_pixels")):
            raise ToolUserError("resolution_too_high", "Resolução de vídeo acima do suportado (máximo 4K).")
    elif duration > int(get_setting(db, "audio_max_seconds")):
        raise ToolUserError("too_long", "O áudio é longo demais (máximo 60 minutos).")
    return info, new_fmt


def cleanup_expired(db_factory) -> int:
    at = clock.now()
    with db_factory() as db:
        rows = db.execute(select(Upload.id, Upload.storage_key).where(Upload.expires_at <= at)).all()
    storage = get_storage()
    for upload_id, key in rows:
        storage.delete(key)
        with db_factory() as db, db.begin():
            row = db.get(Upload, upload_id)
            if row is not None:
                db.delete(row)
    return len(rows)
