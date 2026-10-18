"""Verify the AI tools with the real models inside worker-ai, and write verified.json.

    docker compose run --rm --no-deps worker-ai python -m app.tools.ai.verify

Synthetic images with known geometry make the checks objective:
- background remover: a red disc on a white background -> alpha high on the disc, low on corners;
  solid-colour mode -> corners take the chosen colour.
- object remover: a dark square on a textured background, masked -> pixels outside the mask are
  unchanged and the masked area no longer looks like the square.
"""

import json
import tempfile
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from PIL import Image, ImageDraw

from app.tools.ai.handlers import INPUTS, OUTPUTS, BackgroundRemoverHandler, ObjectRemoverHandler

VERIFIED_FILE = Path(__file__).with_name("verified.json")
PIL_SAVE = {"jpg": ("JPEG", {"quality": 95}), "png": ("PNG", {}), "webp": ("WEBP", {"quality": 95})}


@dataclass(frozen=True)
class Candidate:
    tool_id: str
    input_format: str
    output_format: str

    @property
    def key(self) -> str:
        return f"{self.tool_id}:{self.input_format}->{self.output_format}"


def candidates() -> list[Candidate]:
    return [Candidate(t, i, o) for t in ("background_remover", "object_remover") for i in INPUTS for o in OUTPUTS]


def verified_keys() -> set[str]:
    if not VERIFIED_FILE.exists():
        return set()
    return {e["key"] for e in json.loads(VERIFIED_FILE.read_text(encoding="utf-8")).get("passed", [])}


def disc_image(size=(640, 480)) -> Image.Image:
    image = Image.new("RGB", size, "white")
    w, h = size
    ImageDraw.Draw(image).ellipse((w * 0.3, h * 0.25, w * 0.7, h * 0.75), fill=(200, 30, 30))
    return image


def square_scene(size=(640, 480)) -> tuple[Image.Image, Image.Image]:
    w, h = size
    image = Image.new("RGB", size)
    pixels = image.load()
    for y in range(h):
        for x in range(w):
            pixels[x, y] = (120 + (x * 3 % 40), 160 + (y * 2 % 30), 90 + ((x + y) % 25))  # mild texture
    box = (int(w * 0.4), int(h * 0.4), int(w * 0.55), int(h * 0.6))
    ImageDraw.Draw(image).rectangle(box, fill=(10, 10, 10))
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).rectangle((box[0] - 4, box[1] - 4, box[2] + 4, box[3] + 4), fill=255)
    return image, mask


def _write(image: Image.Image, fmt: str, path: Path) -> Path:
    pil_format, params = PIL_SAVE[fmt]
    image.save(path, pil_format, **params)
    return path


def check_background(c: Candidate, work: Path) -> None:
    src = _write(disc_image(), c.input_format, work / f"in.{c.input_format}")
    handler = BackgroundRemoverHandler()
    for background in (("transparent",) if c.output_format != "jpg" else ()) + ("#00ff00",):
        sub = work / background.strip("#")
        sub.mkdir()
        options = handler.validate_options(c.input_format, c.output_format, {"background": background}, {})
        result = handler.execute(c.input_format, c.output_format, options, sub, src, {"original_name": "foto.jpg"})
        with Image.open(result.output_path) as out:
            assert out.size == (640, 480), f"size changed: {out.size}"
            if background == "transparent":
                alpha = out.convert("RGBA").getchannel("A")
                assert alpha.getpixel((320, 240)) > 200, f"disc not kept (alpha={alpha.getpixel((320, 240))})"
                assert alpha.getpixel((10, 10)) < 60, f"background not removed (alpha={alpha.getpixel((10, 10))})"
            else:
                corner = out.convert("RGB").getpixel((10, 10))
                assert corner[1] > 200 and corner[0] < 60 and corner[2] < 60, f"solid colour missing: {corner}"
        assert result.filename.endswith(f"-sem-fundo.{c.output_format}")


def check_object(c: Candidate, work: Path) -> None:
    image, mask = square_scene()
    src = _write(image, c.input_format, work / f"in.{c.input_format}")
    mask_path = work / "mask.png"
    mask.save(mask_path, "PNG")
    with Image.open(src) as decoded:
        reference = decoded.convert("RGB")
    handler = ObjectRemoverHandler()
    meta = {"width": 640, "height": 480, "extra": {"mask_upload_id": {"format": "png", "width": 640, "height": 480}}}
    options = handler.validate_options(c.input_format, c.output_format,
                                       {"mask_upload_id": "x", "accept_rights": True, "mask_expand": "0"}, meta)
    result = handler.execute(c.input_format, c.output_format, options, work, src,
                             {"original_name": "foto.png", "extra_paths": {"mask_upload_id": mask_path}})
    with Image.open(result.output_path) as raw:
        out = raw.convert("RGB")
    assert out.size == reference.size
    # PNG output is pixel-exact outside the mask; JPEG/WEBP are lossy re-encodings (small drift).
    tolerance = 0 if c.output_format == "png" else 40
    for point in ((5, 5), (630, 470), (100, 300), (500, 100)):
        diff = max(abs(a - b) for a, b in zip(out.getpixel(point), reference.getpixel(point), strict=True))
        assert diff <= tolerance, f"pixel outside mask changed at {point}: {diff}"
    inside = out.crop((290, 220, 320, 260))
    data = inside.tobytes()
    mean = sum(data) / len(data)
    assert mean > 60, f"object not removed (mean brightness inside mask = {mean:.0f})"
    assert result.filename.endswith(f"-editada.{c.output_format}")


def run_candidate(c: Candidate, work: Path) -> None:
    (check_background if c.tool_id == "background_remover" else check_object)(c, work)


def main() -> None:
    results = {"passed": [], "failed": []}
    with tempfile.TemporaryDirectory(prefix="ai-verify-") as tmp:
        for c in candidates():
            work = Path(tmp) / c.key.replace(":", "_").replace(">", "")
            work.mkdir()
            entry = {"key": c.key}
            started = time.monotonic()
            try:
                run_candidate(c, work)
                entry["seconds"] = round(time.monotonic() - started, 2)
                results["passed"].append(entry)
            except Exception as exc:  # noqa: BLE001
                entry["error"] = f"{type(exc).__name__}: {getattr(exc, 'message', None) or exc}"[:300]
                results["failed"].append(entry)
    results["note"] = "Generated by app.tools.ai.verify inside worker-ai. Do not edit by hand."
    results["run"] = datetime.now(UTC).isoformat(timespec="seconds")
    VERIFIED_FILE.write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"passed={len(results['passed'])} failed={len(results['failed'])}")
    for e in results["failed"]:
        print(f"FAILED {e['key']}: {e['error']}")


if __name__ == "__main__":
    main()
