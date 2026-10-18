"""Background remover and object remover (PRD §6.3, §6.4)."""

import re
from pathlib import Path

from PIL import Image, ImageFilter, ImageOps

from app.core.errors import AppError
from app.tools.ai import providers
from app.tools.base import ToolHandler, ToolResult, ToolSystemError, ToolUserError
from app.tools.converter.handler import output_filename

Image.MAX_IMAGE_PIXELS = 40_000_000
INPUTS = ("jpg", "png", "webp")
OUTPUTS = ("png", "webp", "jpg")
SAVE = {"png": ("PNG", {"optimize": True}), "webp": ("WEBP", {"quality": 90}), "jpg": ("JPEG", {"quality": 92})}
HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")
MASK_EXPAND = ("0", "8", "16", "32")
TERMS_VERSION = "2026-10-18"


def _open_rgb(path: Path) -> Image.Image:
    try:
        with Image.open(path) as image:
            image = ImageOps.exif_transpose(image)  # respect phone rotation, then drop metadata
            image.load()
            return image.convert("RGBA")
    except Image.DecompressionBombError:
        raise ToolUserError("image_too_large", "A imagem tem resolução grande demais.") from None
    except Exception:  # noqa: BLE001
        raise ToolUserError("unreadable_image", "Não foi possível ler esta imagem.") from None


def _save(image: Image.Image, fmt: str, work_dir: Path) -> Path:
    out = work_dir / f"output.{fmt}"
    pil_format, params = SAVE[fmt]
    if fmt == "jpg":
        image = image.convert("RGB")
    image.save(out, pil_format, **params)  # no exif/xmp passed: metadata stripped
    return out


def _model_call(fn, *args):
    try:
        return fn(*args)
    except FileNotFoundError as exc:
        raise ToolSystemError("model_missing") from exc
    except MemoryError as exc:
        raise ToolSystemError("out_of_memory") from exc


class BackgroundRemoverHandler(ToolHandler):
    tool_id = "background_remover"
    requires_upload = True

    def queue_for(self, category: str) -> str | None:
        return "ai"

    def public_info(self, db) -> dict:
        return {"options": {"background": ["transparent", "#RRGGBB"]}, "accepts": list(INPUTS)}

    def validate_options(self, input_format, output_format, options, upload_meta):
        if input_format not in INPUTS or output_format not in OUTPUTS:
            raise AppError("Combinação indisponível.", code="capability_unavailable")
        background = options.get("background", "transparent")
        if background != "transparent" and not HEX_COLOR.match(str(background)):
            raise AppError("Cor de fundo inválida.", code="invalid_options")
        if output_format == "jpg" and background == "transparent":
            background = "#ffffff"  # JPEG has no transparency
        unknown = set(options) - {"upload_id", "background"}
        if unknown:
            raise AppError(f"Opção inválida: {sorted(unknown)[0]}.", code="invalid_options")
        return {"background": background}

    def execute(self, input_format, output_format, options, work_dir, input_path, input_meta) -> ToolResult:
        image = _open_rgb(input_path)
        alpha = _model_call(providers.background_provider().mask, image)
        cutout = image.copy()
        cutout.putalpha(alpha)
        if options["background"] != "transparent":
            canvas = Image.new("RGBA", image.size, options["background"])
            canvas.alpha_composite(cutout)
            cutout = canvas
        out = _save(cutout, output_format, work_dir)
        name = output_filename(input_meta.get("original_name", ""), output_format).replace(f".{output_format}", "")
        return ToolResult(output_path=out, filename=f"{name}-sem-fundo.{output_format}")


class ObjectRemoverHandler(ToolHandler):
    tool_id = "object_remover"
    requires_upload = True
    extra_uploads = ("mask_upload_id",)
    required_terms = ("image_edit_rights", TERMS_VERSION)

    def queue_for(self, category: str) -> str | None:
        return "ai"

    def public_info(self, db) -> dict:
        return {"options": {"mask_expand": list(MASK_EXPAND)}, "accepts": list(INPUTS),
                "terms_version": TERMS_VERSION}

    def validate_options(self, input_format, output_format, options, upload_meta):
        if input_format not in INPUTS or output_format not in OUTPUTS:
            raise AppError("Combinação indisponível.", code="capability_unavailable")
        expand = str(options.get("mask_expand", "8"))
        if expand not in MASK_EXPAND:
            raise AppError("Opção inválida: mask_expand.", code="invalid_options")
        unknown = set(options) - {"upload_id", "mask_upload_id", "accept_rights", "mask_expand"}
        if unknown:
            raise AppError(f"Opção inválida: {sorted(unknown)[0]}.", code="invalid_options")
        mask_meta = (upload_meta or {}).get("extra", {}).get("mask_upload_id")
        if not mask_meta:
            raise AppError("Desenhe a área a remover.", code="mask_required")
        if mask_meta.get("format") != "png":
            raise AppError("Máscara inválida.", code="invalid_mask")
        if (mask_meta.get("width"), mask_meta.get("height")) != (upload_meta.get("width"), upload_meta.get("height")):
            raise AppError("A máscara não corresponde ao tamanho da imagem.", code="invalid_mask")
        return {"mask_expand": expand}

    def execute(self, input_format, output_format, options, work_dir, input_path, input_meta) -> ToolResult:
        image = _open_rgb(input_path)
        mask_path = input_meta.get("extra_paths", {}).get("mask_upload_id")
        try:
            with Image.open(mask_path) as raw:
                mask = raw.convert("L")
        except Exception:  # noqa: BLE001
            raise ToolUserError("invalid_mask", "Máscara inválida.") from None
        if mask.size != image.size:
            raise ToolUserError("invalid_mask", "A máscara não corresponde ao tamanho da imagem.")
        mask = mask.point(lambda v: 255 if v >= 128 else 0)
        if mask.getbbox() is None:
            raise ToolUserError("empty_mask", "Nenhuma área foi marcada para remoção.")
        expand = int(options["mask_expand"])
        if expand:
            # Grow the mask by ~`expand` px (Gaussian blur + low threshold: linear time, unlike MaxFilter).
            mask = mask.filter(ImageFilter.GaussianBlur(expand / 2)).point(lambda v: 255 if v > 8 else 0)
        result = _model_call(providers.inpainting_provider().inpaint, image.convert("RGB"), mask)
        if output_format != "jpg" and image.mode == "RGBA":
            result = result.convert("RGBA")
            result.putalpha(image.getchannel("A"))
        out = _save(result, output_format, work_dir)
        name = output_filename(input_meta.get("original_name", ""), output_format).replace(f".{output_format}", "")
        return ToolResult(output_path=out, filename=f"{name}-editada.{output_format}")
