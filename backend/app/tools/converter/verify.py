"""Verify candidate conversions with REAL files inside the worker images.

    docker compose run --rm worker-light python -m app.tools.converter.verify --categories document,image
    docker compose run --rm worker-media python -m app.tools.converter.verify --categories audio,video

Each run merges its results into verified.json (one section per category). A combination is
`available` only if listed under "passed". Fixtures are generated here with the engines themselves
(LibreOffice writes the DOCX/DOC/ODT/RTF inputs, FFmpeg the media) except HEIC: the image has no
HEVC encoder, so a small committed sample (fixtures/sample.heic) is used.
"""

import argparse
import json
import shutil
import tempfile
import time
import zipfile
from datetime import UTC, datetime
from pathlib import Path

from app.security.file_sniffing import sniff
from app.security.sandbox import Limits, run
from app.tools.base import ToolSystemError, ToolUserError
from app.tools.converter import images, matrix, media
from app.tools.converter.handler import ConverterHandler

MARKER = "BAIXEAI-MARCADOR-7319"
FIXTURE_DIR = Path(__file__).with_name("fixtures")
LIMITS = Limits(timeout_seconds=120, cpu_seconds=180, memory_bytes=3 * 1024**3)


# --------------------------------------------------------------------------- fixtures


def _soffice(args: list[str], work: Path) -> None:
    profile = (work / "fixture-profile").as_uri()
    run(["soffice", f"-env:UserInstallation={profile}", "--headless", "--norestore", *args], cwd=work, limits=LIMITS)


def make_document_fixtures(out: Path) -> dict[str, Path]:
    files: dict[str, Path] = {}
    (out / "src.txt").write_text(f"{MARKER}\nação e acentuação: café, pão.\n", encoding="utf-8")
    files["txt"] = out / "src.txt"
    (out / "src.html").write_text(
        f"<!doctype html><html><head><meta charset='utf-8'><title>t</title></head><body><h1>{MARKER}</h1>"
        "<p>conteúdo</p><img src='http://169.254.169.254/x.png'></body></html>", encoding="utf-8")
    files["html"] = out / "src.html"
    (out / "src.csv").write_text(f"coluna,valor\n{MARKER},42\nação,7\n", encoding="utf-8")
    files["csv"] = out / "src.csv"
    gen = out / "gen"
    gen.mkdir()
    for fmt, spec in (("docx", "docx:MS Word 2007 XML"), ("odt", "odt"), ("rtf", "rtf"),
                      ("doc", "doc:MS Word 97"), ("pdf", "pdf:writer_pdf_Export")):
        _soffice(["--infilter=Text (encoded):UTF8,LF,,,", "--convert-to", spec, "--outdir", str(gen),
                  str(files["txt"])], out)
        files[fmt] = gen / f"src.{fmt}"
    for fmt, spec in (("xlsx", "xlsx:Calc MS Excel 2007 XML"), ("xls", "xls:MS Excel 97")):
        _soffice(["--infilter=CSV:44,34,76,1", "--convert-to", spec, "--outdir", str(gen), str(files["csv"])], out)
        files[fmt] = gen / f"src.{fmt}"
    return files


def make_image_fixtures(out: Path) -> dict[str, Path]:
    from PIL import Image

    base = out / "base.png"
    run(["vips", "xyz", str(out / "xyz.v"), "64", "48"], cwd=out, limits=LIMITS)
    run(["vips", "cast", str(out / "xyz.v"), str(base), "uchar"], cwd=out, limits=LIMITS)
    files = {"png": base}
    for fmt in ("jpg", "webp", "avif", "gif", "tiff"):
        target = out / f"src.{fmt}"
        run(["vips", "copy", str(base), str(target)], cwd=out, limits=LIMITS)
        files[fmt] = target
    with Image.open(base) as image:
        image.convert("RGB").save(out / "src.bmp", "BMP")
        image.convert("RGBA").save(out / "src.ico", "ICO", sizes=[(48, 48)])
    files["bmp"], files["ico"] = out / "src.bmp", out / "src.ico"
    (out / "src.svg").write_text(
        '<?xml version="1.0"?><svg xmlns="http://www.w3.org/2000/svg" width="64" height="48">'
        '<rect width="64" height="48" fill="#3366cc"/><script>alert(1)</script>'
        '<image href="http://169.254.169.254/x.png" width="10" height="10"/></svg>', encoding="utf-8")
    files["svg"] = out / "src.svg"
    shutil.copyfile(FIXTURE_DIR / "sample.heic", out / "src.heic")
    files["heic"] = out / "src.heic"
    return files


def make_audio_fixtures(out: Path) -> dict[str, Path]:
    files = {}
    for fmt in matrix.AUDIO_FORMATS:
        target = out / f"src.{fmt}"
        codec = media.AUDIO_CODEC[fmt]
        args = ["-ar", "48000"] if fmt == "opus" else []
        run(["ffmpeg", "-nostdin", "-loglevel", "error", "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
             "-ac", "2", "-c:a", codec, *args, "-f", media.MUXER[fmt], "-y", str(target)], cwd=out, limits=LIMITS)
        files[fmt] = target
    return files


def make_video_fixtures(out: Path) -> dict[str, Path]:
    codecs = {"mp4": ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac"],
              "mov": ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac"],
              "mkv": ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac"],
              "webm": ["-c:v", "libvpx-vp9", "-deadline", "realtime", "-c:a", "libopus"],
              "avi": ["-c:v", "mpeg4", "-c:a", "libmp3lame"]}
    files = {}
    for fmt, args in codecs.items():
        target = out / f"src.{fmt}"
        run(["ffmpeg", "-nostdin", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=duration=2:size=320x240:rate=25",
             "-f", "lavfi", "-i", "sine=frequency=440:duration=2", "-shortest", *args,
             "-f", media.MUXER[fmt], "-y", str(target)], cwd=out, limits=LIMITS)
        files[fmt] = target
    return files


MAKERS = {"document": make_document_fixtures, "image": make_image_fixtures,
          "audio": make_audio_fixtures, "video": make_video_fixtures}


# --------------------------------------------------------------------------- checks


def _text_of(path: Path, fmt: str, work: Path) -> str:
    if fmt == "pdf":
        return run(["pdftotext", "-enc", "UTF-8", str(path), "-"], cwd=work, limits=LIMITS)
    if fmt in ("txt", "csv"):
        return path.read_text(encoding="utf-8", errors="replace")
    if fmt in ("docx", "xlsx"):
        with zipfile.ZipFile(path) as archive:
            return " ".join(archive.read(n).decode("utf-8", "replace") for n in archive.namelist()
                            if n.endswith(".xml"))
    raise AssertionError(f"no text extractor for {fmt}")


def check_output(candidate: matrix.Candidate, source_meta: dict, output: Path, work: Path) -> None:
    detected = sniff(output, candidate.output_format).format
    expected = candidate.output_format
    assert detected == expected, f"output sniffed as {detected}, expected {expected}"
    if candidate.category == "document":
        text = _text_of(output, expected, work)
        assert MARKER in text, "marker text missing in output"
    elif candidate.category == "image":
        width, height = images.dimensions(output, expected, work)
        if expected == "ico":
            assert max(width, height) <= 256 and width > 0
        else:
            assert (width, height) == (source_meta["width"], source_meta["height"]), f"size {width}x{height}"
    else:
        info = media.probe(output, expected, work)
        if expected == "gif":
            assert info["has_video"] and info["width"] <= 480
            return
        assert abs(info["duration_seconds"] - source_meta["duration_seconds"]) < 0.35, "duration changed"
        if expected in media.AUDIO_CODEC:
            assert info["has_audio"] and not info["has_video"]
        else:
            assert info["has_video"] and info["has_audio"]


def source_meta(category: str, path: Path, fmt: str, work: Path) -> dict:
    if category == "image":
        width, height = images.dimensions(path, fmt, work)
        return {"width": width, "height": height}
    if category in ("audio", "video"):
        return media.probe(path, fmt, work)
    return {}


def make_fixtures(categories: list[str], root: Path) -> dict[str, dict[str, Path]]:
    fixtures: dict[str, dict[str, Path]] = {}
    for category in categories:
        folder = root / f"fx-{category}"
        folder.mkdir()
        fixtures[category] = MAKERS[category](folder)
    return fixtures


def run_candidate(candidate: matrix.Candidate, fixtures: dict[str, dict[str, Path]], root: Path) -> None:
    """Convert the fixture through the production handler and check the output. Raises on failure."""
    handler = ConverterHandler()
    source_category = "video" if candidate.input_format in matrix.VIDEO_FORMATS else candidate.category
    source = fixtures.get(source_category, {}).get(candidate.input_format)
    assert source is not None, "no fixture"
    work = root / f"job-{candidate.input_format}-{candidate.output_format}"
    work.mkdir()
    local = work / f"input.{candidate.input_format}"
    shutil.copyfile(source, local)
    meta = source_meta(candidate.category, local, candidate.input_format, work)
    options = handler.validate_options(candidate.input_format, candidate.output_format, {}, meta)
    result = handler.execute(candidate.input_format, candidate.output_format, options, work, local,
                             {**meta, "original_name": f"teste.{candidate.input_format}"})
    check_output(candidate, meta, result.output_path, work)


def verify(categories: list[str]) -> dict:
    results = {"passed": [], "failed": []}
    with tempfile.TemporaryDirectory(prefix="verify-") as tmp:
        root = Path(tmp)
        fixtures = make_fixtures(categories, root)
        for candidate in matrix.candidates():
            if candidate.category not in categories:
                continue
            entry = {"key": candidate.key, "category": candidate.category, "engine": candidate.engine}
            started = time.monotonic()
            try:
                run_candidate(candidate, fixtures, root)
                entry["seconds"] = round(time.monotonic() - started, 2)
                results["passed"].append(entry)
            except (AssertionError, ToolUserError, ToolSystemError, TimeoutError, Exception) as exc:  # noqa: BLE001
                entry["error"] = f"{type(exc).__name__}: {getattr(exc, 'message', None) or exc}"[:300]
                results["failed"].append(entry)
    return results


def merge_into_file(categories: list[str], results: dict) -> dict:
    data = json.loads(matrix.VERIFIED_FILE.read_text(encoding="utf-8")) if matrix.VERIFIED_FILE.exists() else {}
    keep = [e for e in data.get("passed", []) if e["category"] not in categories]
    keep_failed = [e for e in data.get("failed", []) if e["category"] not in categories]
    runs = {k: v for k, v in data.get("runs", {}).items() if k not in categories}
    stamp = datetime.now(UTC).isoformat(timespec="seconds")
    for category in categories:
        runs[category] = stamp
    merged = {
        "note": "Generated by app.tools.converter.verify inside the worker images. Do not edit by hand.",
        "runs": runs,
        "passed": sorted(keep + results["passed"], key=lambda e: e["key"]),
        "failed": sorted(keep_failed + results["failed"], key=lambda e: e["key"]),
    }
    matrix.VERIFIED_FILE.write_text(json.dumps(merged, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return merged


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--categories", required=True)
    parser.add_argument("--no-write", action="store_true")
    args = parser.parse_args()
    categories = [c.strip() for c in args.categories.split(",") if c.strip()]
    results = verify(categories)
    if not args.no_write:
        merge_into_file(categories, results)
    print(f"passed={len(results['passed'])} failed={len(results['failed'])}")
    for entry in results["failed"]:
        print(f"FAILED {entry['key']}: {entry['error']}")


if __name__ == "__main__":
    main()
