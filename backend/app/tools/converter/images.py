"""Image conversions. libvips CLI for most formats; Pillow only for BMP/ICO. Metadata (EXIF/GPS)
is stripped. SVG is sanitized, then rasterized by rsvg-convert inside the sandbox.

libvips is always run with VIPS_BLOCK_UNTRUSTED=1: this disables its "untrusted" loaders, notably
ImageMagick (magickload), PDF, SVG, FITS and the native .v format, shrinking the attack surface to
the loaders we actually need (jpeg, png, webp, gif, tiff, heif/avif).
"""

import xml.etree.ElementTree as StdET
from pathlib import Path

from defusedxml import ElementTree as SafeET
from PIL import Image

from app.security.sandbox import Limits, SandboxFailed, SandboxTimeout, run
from app.tools.base import ToolSystemError, ToolUserError

Image.MAX_IMAGE_PIXELS = 40_000_000  # Pillow raises above 2x this; the probe enforces 40 MP first
LIMITS = Limits(timeout_seconds=60, cpu_seconds=90, memory_bytes=2 * 1024**3, max_file_bytes=500 * 1024**2)
PILLOW_FORMATS = {"bmp": "BMP", "ico": "ICO"}
QUALITY = {"alta": 90, "media": 80, "baixa": 65}
ICO_SIZES = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
SVG_NS = "{http://www.w3.org/2000/svg}"
XLINK_HREF = "{http://www.w3.org/1999/xlink}href"
SVG_BLOCKED_TAGS = {"script", "foreignObject", "iframe", "object", "embed", "audio", "video", "handler"}
VIPS_ENV = {"VIPS_CONCURRENCY": "1", "VIPS_BLOCK_UNTRUSTED": "1"}
StdET.register_namespace("", "http://www.w3.org/2000/svg")
StdET.register_namespace("xlink", "http://www.w3.org/1999/xlink")


def _vips(argv: list[str], work_dir: Path) -> str:
    try:
        return run(["vips", *argv], cwd=work_dir, limits=LIMITS, extra_env=VIPS_ENV)
    except SandboxTimeout:
        raise TimeoutError from None
    except SandboxFailed as exc:
        raise ToolUserError("unreadable_image", "Não foi possível ler esta imagem (corrompida ou inválida).") from exc


def dimensions(path: Path, fmt: str, work_dir: Path) -> tuple[int, int]:
    """Read width/height from the header only (no full decode). Used before charging."""
    if fmt in PILLOW_FORMATS:
        try:
            with Image.open(path) as image:
                return image.size
        except Exception:  # noqa: BLE001 - any parse failure means a bad file
            raise ToolUserError("unreadable_image", "Não foi possível ler esta imagem.") from None
    source = rasterize_svg(path, work_dir) if fmt == "svg" else path
    return int(_header(source, "width", work_dir)), int(_header(source, "height", work_dir))


def _header(path: Path, field: str, work_dir: Path) -> str:
    try:
        value = run(["vipsheader", "-f", field, str(path)], cwd=work_dir, limits=LIMITS, extra_env=VIPS_ENV).strip()
        int(value)
        return value
    except (SandboxFailed, SandboxTimeout, ValueError):
        raise ToolUserError("unreadable_image", "Não foi possível ler esta imagem.") from None


def rasterize_svg(path: Path, work_dir: Path) -> Path:
    """Sanitize, then render to PNG at its natural size. A huge declared size fails inside the
    sandbox memory limit (user error), and the probe applies the pixel limit to the result."""
    out = work_dir / "raster-svg.png"
    if out.exists():
        return out
    clean = sanitize_svg(path, work_dir)
    try:
        run(["rsvg-convert", "--format", "png", "--output", str(out), str(clean)], cwd=work_dir, limits=LIMITS)
    except SandboxTimeout:
        raise TimeoutError from None
    except SandboxFailed:
        raise ToolUserError("unreadable_image", "Não foi possível desenhar este SVG.") from None
    return out


def sanitize_svg(path: Path, work_dir: Path) -> Path:
    """Drop scripts, foreign content, event handlers and any non-local reference."""
    try:
        tree = SafeET.parse(path, forbid_dtd=True, forbid_entities=True, forbid_external=True)
    except Exception:  # noqa: BLE001 - malformed or hostile XML
        raise ToolUserError("unsafe_svg", "SVG inválido ou com conteúdo não permitido.") from None
    root = tree.getroot()
    if root.tag not in (f"{SVG_NS}svg", "svg"):
        raise ToolUserError("unsafe_svg", "SVG inválido.")
    for parent in list(root.iter()):
        for child in list(parent):
            local = child.tag.split("}")[-1] if isinstance(child.tag, str) else ""
            if local in SVG_BLOCKED_TAGS:
                parent.remove(child)
    for element in root.iter():
        for attr in list(element.attrib):
            value = element.attrib[attr].strip().lower()
            if attr.split("}")[-1].lower().startswith("on"):
                del element.attrib[attr]
            elif attr in ("href", XLINK_HREF) and not (value.startswith("#") or value.startswith("data:image/")):
                del element.attrib[attr]
            elif "url(" in value and "url(#" not in value.replace(" ", ""):
                del element.attrib[attr]
    for style in root.iter(f"{SVG_NS}style"):
        style.text = ""  # CSS can reference external resources (@import, url())
    clean = work_dir / "sanitized.svg"
    tree.write(clean, encoding="utf-8", xml_declaration=True)
    return clean


def _pillow_to_png(path: Path, work_dir: Path) -> Path:
    out = work_dir / "intermediate.png"
    try:
        with Image.open(path) as image:
            image.load()
            if image.mode not in ("RGB", "RGBA"):
                image = image.convert("RGBA")
            image.save(out, "PNG")
    except Image.DecompressionBombError:
        raise ToolUserError("image_too_large", "A imagem tem resolução grande demais.") from None
    except Exception:  # noqa: BLE001
        raise ToolUserError("unreadable_image", "Não foi possível ler esta imagem.") from None
    return out


def _png_to_pillow(png: Path, fmt: str, work_dir: Path) -> Path:
    out = work_dir / f"output.{fmt}"
    try:
        with Image.open(png) as image:
            if fmt == "bmp":
                image.convert("RGB" if image.mode != "RGBA" else "RGBA").save(out, "BMP")
            else:
                side = max(image.size)
                sizes = [s for s in ICO_SIZES if s[0] <= side] or [(16, 16)]
                image.convert("RGBA").save(out, "ICO", sizes=sizes)
    except Exception as exc:  # noqa: BLE001
        raise ToolSystemError("pillow_save_failed") from exc
    return out


def _save_suffix(fmt: str, quality: int) -> str:
    keep = "keep=none"  # strip EXIF/XMP/ICC metadata (privacy)
    if fmt == "avif":
        # effort=2: ~4x faster than the default (4) on CPU with near-identical size (measured, 12 MP)
        return f"[Q={quality},effort=2,{keep}]"
    if fmt in ("jpg", "webp"):
        return f"[Q={quality},{keep}]"
    if fmt == "tiff":
        return f"[compression=deflate,{keep}]"
    return f"[{keep}]"


def convert(input_path: Path, input_format: str, output_format: str, options: dict, work_dir: Path) -> Path:
    quality = QUALITY[options.get("quality", "media")]
    source = input_path
    if input_format in PILLOW_FORMATS:
        source = _pillow_to_png(input_path, work_dir)
    elif input_format == "svg":
        source = rasterize_svg(input_path, work_dir)

    if output_format in PILLOW_FORMATS:
        png = source
        if source.name != "intermediate.png":  # not already decoded by Pillow
            png = work_dir / "for-pillow.png"
            _vips(["copy", str(source), f"{png}[keep=none]"], work_dir)
        return _png_to_pillow(png, output_format, work_dir)

    output = work_dir / f"output.{output_format}"
    target = f"{output}{_save_suffix(output_format, quality)}"
    bands = int(_header(source, "bands", work_dir))
    if output_format == "jpg" and bands in (2, 4):
        # JPEG has no transparency: flatten on white so transparent areas don't turn black.
        background = "255" if bands == 2 else "255 255 255"
        _vips(["flatten", str(source), target, "--background", background], work_dir)
    else:
        _vips(["copy", str(source), target], work_dir)
    if not output.exists() or output.stat().st_size == 0:
        raise ToolSystemError("vips_no_output")
    return output
