import re
from pathlib import Path

from app.core.errors import AppError
from app.tools.base import ToolHandler, ToolResult
from app.tools.converter import documents, images, matrix, media

OPTION_SETS: dict[str, dict[str, tuple[str, ...]]] = {
    "document": {},
    "image": {"quality": tuple(images.QUALITY)},
    "audio": {"bitrate": media.AUDIO_BITRATES, "sample_rate": media.SAMPLE_RATES, "channels": media.CHANNELS},
    "video": {"resolution": media.RESOLUTIONS, "quality": media.QUALITIES, "fps": media.FPS,
              "bitrate": media.AUDIO_BITRATES, "sample_rate": media.SAMPLE_RATES, "channels": media.CHANNELS},
}


def output_filename(original_name: str, output_format: str) -> str:
    stem = Path(original_name).stem
    stem = re.sub(r"[^\w.\- ]", "", stem, flags=re.UNICODE).strip(" .")[:80] or "arquivo"
    return f"{stem}.{output_format}"


class ConverterHandler(ToolHandler):
    tool_id = "converter"
    requires_upload = True

    def public_info(self, db) -> dict:
        from app.services.settings import get_setting

        return {"options": OPTION_SETS, "limits_bytes": get_setting(db, "limits_bytes"),
                "video_max_seconds": get_setting(db, "video_max_seconds")}

    def queue_for(self, category: str) -> str | None:
        return matrix.QUEUE_BY_CATEGORY.get(category)

    def validate_options(self, input_format: str, output_format: str, options: dict,
                         upload_meta: dict | None) -> dict:
        candidate = matrix.find(input_format, output_format)
        if candidate is None:
            raise AppError("Combinação de formatos indisponível.", code="capability_unavailable")
        allowed = OPTION_SETS[candidate.category]
        clean: dict[str, str] = {}
        for key, value in options.items():
            if key == "upload_id":
                continue
            if key not in allowed or value not in allowed[key]:
                raise AppError(f"Opção inválida: {key}.", code="invalid_options")
            clean[key] = value
        meta = upload_meta or {}
        audio_out = output_format in media.AUDIO_CODEC
        if candidate.category in ("audio", "video") and audio_out and not meta.get("has_audio"):
            raise AppError("Este arquivo não tem faixa de áudio.", code="no_audio")
        if candidate.category == "video" and not audio_out and not meta.get("has_video"):
            raise AppError("Este arquivo não tem faixa de vídeo.", code="no_video")
        return clean

    def metadata(self, options: dict, upload_meta: dict | None) -> dict:
        return {"duration_seconds": (upload_meta or {}).get("duration_seconds")}

    def execute(self, input_format: str, output_format: str, options: dict, work_dir: Path,
                input_path: Path | None, input_meta: dict) -> ToolResult:
        candidate = matrix.find(input_format, output_format)
        if candidate.category == "document":
            out = documents.convert(input_path, input_format, output_format, work_dir)
        elif candidate.category == "image":
            out = images.convert(input_path, input_format, output_format, options, work_dir)
        else:
            out = media.convert(input_path, input_format, output_format, options, input_meta, work_dir)
        return ToolResult(output_path=out, filename=output_filename(input_meta.get("original_name", ""), output_format))
