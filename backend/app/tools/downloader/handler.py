from pathlib import Path

from app.core.errors import AppError
from app.tools.base import ToolHandler, ToolResult, ToolSystemError
from app.tools.downloader.extractor import AUDIO_OUTPUTS, VIDEO_OUTPUTS

TERMS_VERSION = "2026-10-18"


class VideoDownloaderHandler(ToolHandler):
    """Executed remotely by worker-download (`remote_queue`); never runs inside jobs.run()."""

    tool_id = "video_downloader"
    requires_inspection = True
    remote_queue = "download"
    required_terms = ("video_rights", TERMS_VERSION)

    def queue_for(self, category: str) -> str | None:
        return "download"

    def public_info(self, db) -> dict:
        from app.services.downloads import limits

        return {"limits": limits(db), "terms_version": TERMS_VERSION}

    def validate_options(self, input_format, output_format, options, upload_meta):
        meta = upload_meta or {}
        unknown = set(options) - {"inspection_id", "quality", "accept_rights"}
        if unknown:
            raise AppError(f"Opção inválida: {sorted(unknown)[0]}.", code="invalid_options")
        if output_format in AUDIO_OUTPUTS:
            if not meta.get("has_audio"):
                raise AppError("Este vídeo não tem áudio disponível.", code="no_audio")
            return {"quality": "audio"}
        if output_format not in VIDEO_OUTPUTS or not meta.get("has_video"):
            raise AppError("Formato indisponível para este link.", code="capability_unavailable")
        quality = str(options.get("quality", "best"))
        offered = {str(h) for h in meta.get("heights", [])}
        if quality != "best" and quality not in offered:  # never offer/accept a quality that doesn't exist
            raise AppError("Qualidade indisponível para este vídeo.", code="invalid_options")
        return {"quality": quality}

    def metadata(self, options, upload_meta):
        return {"duration_seconds": (upload_meta or {}).get("duration_seconds")}

    def execute(self, input_format, output_format, options, work_dir: Path, input_path, input_meta) -> ToolResult:
        raise ToolSystemError("remote_only")  # dispatched to worker-download instead
