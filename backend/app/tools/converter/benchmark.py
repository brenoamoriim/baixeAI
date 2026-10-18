"""Measure wall time and peak engine memory with realistic inputs (not the tiny test fixtures).

    docker compose run --rm --no-deps worker-light python -m app.tools.converter.benchmark --group light
    docker compose run --rm --no-deps worker-media python -m app.tools.converter.benchmark --group media

Each case runs in a fresh Python process; peak memory is RUSAGE_CHILDREN.ru_maxrss of that process
(i.e. the largest engine subprocess it spawned).
"""

import argparse
import json
import os
import platform
import subprocess
import sys
import tempfile
from pathlib import Path

from app.security.sandbox import Limits, run

LIMITS = Limits(timeout_seconds=900, cpu_seconds=1800, memory_bytes=4 * 1024**3, max_file_bytes=2 * 1024**3)

CASES = {
    "light": [
        ("document", "docx", "pdf", {}), ("document", "pdf", "docx", {}), ("document", "xlsx", "csv", {}),
        ("image", "jpg", "webp", {}), ("image", "jpg", "avif", {}), ("image", "jpg", "png", {}),
        ("image", "heic", "jpg", {}), ("image", "png", "ico", {}),
    ],
    "media": [
        ("audio", "wav", "mp3", {}), ("audio", "mp3", "opus", {}),
        ("video", "mp4", "mp4", {"resolution": "480"}), ("video", "mp4", "webm", {}),
        ("video", "mp4", "mp3", {}), ("video", "mp4", "gif", {}), ("video", "mov", "mp4", {}),
    ],
}


def _make_inputs(group: str, root: Path) -> dict[str, Path]:
    files: dict[str, Path] = {}
    if group == "light":
        lines = "\n".join(f"Parágrafo {i}: " + "texto de exemplo para ocupar a página. " * 12 for i in range(400))
        (root / "big.txt").write_text(lines, encoding="utf-8")
        profile = (root / "p").as_uri()
        for fmt, spec in (("docx", "docx:MS Word 2007 XML"), ("pdf", "pdf:writer_pdf_Export")):
            run(["soffice", f"-env:UserInstallation={profile}", "--headless", "--infilter=Text (encoded):UTF8,LF,,,",
                 "--convert-to", spec, "--outdir", str(root), str(root / "big.txt")], cwd=root, limits=LIMITS)
            files[fmt] = root / f"big.{fmt}"
        csv = "\n".join(f"{i},{i * 3},valor {i}" for i in range(50000))
        (root / "big.csv").write_text(csv, encoding="utf-8")
        run(["soffice", f"-env:UserInstallation={profile}", "--headless", "--infilter=CSV:44,34,76,1",
             "--convert-to", "xlsx:Calc MS Excel 2007 XML", "--outdir", str(root), str(root / "big.csv")],
            cwd=root, limits=LIMITS)
        files["xlsx"] = root / "big.xlsx"
        # 12 MP photo-like image (noise + gradient defeats trivial compression)
        run(["vips", "gaussnoise", str(root / "n.v"), "4000", "3000"], cwd=root, limits=LIMITS)
        run(["vips", "colourspace", str(root / "n.v"), str(root / "c.v"), "srgb"], cwd=root, limits=LIMITS)
        run(["vips", "bandjoin", f"{root / 'c.v'} {root / 'c.v'} {root / 'c.v'}", str(root / "rgb.v")],
            cwd=root, limits=LIMITS)
        run(["vips", "cast", str(root / "rgb.v"), str(root / "big.jpg[Q=90]"), "uchar"], cwd=root, limits=LIMITS)
        files["jpg"] = root / "big.jpg"
        run(["vips", "copy", str(root / "big.jpg"), str(root / "big.png")], cwd=root, limits=LIMITS)
        files["png"] = root / "big.png"
        files["heic"] = Path(__file__).with_name("fixtures") / "sample.heic"
    else:
        run(["ffmpeg", "-nostdin", "-loglevel", "error", "-f", "lavfi", "-i", "sine=frequency=440:duration=300",
             "-ac", "2", "-ar", "44100", "-c:a", "pcm_s16le", "-y", str(root / "big.wav")], cwd=root, limits=LIMITS)
        files["wav"] = root / "big.wav"
        run(["ffmpeg", "-nostdin", "-loglevel", "error", "-i", str(root / "big.wav"), "-c:a", "libmp3lame",
             "-b:a", "192k", "-y", str(root / "big.mp3")], cwd=root, limits=LIMITS)
        files["mp3"] = root / "big.mp3"
        for fmt, mux in (("mp4", "mp4"), ("mov", "mov")):
            run(["ffmpeg", "-nostdin", "-loglevel", "error",
                 "-f", "lavfi", "-i", "testsrc2=duration=60:size=1280x720:rate=30",
                 "-f", "lavfi", "-i", "sine=frequency=440:duration=60", "-shortest",
                 "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p", "-c:a", "aac",
                 "-f", mux, "-y", str(root / f"big.{fmt}")], cwd=root, limits=LIMITS)
            files[fmt] = root / f"big.{fmt}"
    return files


_CHILD = """
import json, resource, sys, time
from pathlib import Path
from app.tools.converter import images, media
from app.tools.converter.handler import ConverterHandler
category, src, dst, options, path, work = json.loads(sys.argv[1])
work = Path(work); path = Path(path)
meta = media.probe(path, src, work) if category in ("audio", "video") else {}
started = time.monotonic()
result = ConverterHandler().execute(src, dst, options, work, path, {**meta, "original_name": "x." + src})
elapsed = time.monotonic() - started
peak_kb = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
print(json.dumps({"seconds": round(elapsed, 2), "peak_mb": round(peak_kb / 1024, 1),
                  "output_mb": round(result.output_path.stat().st_size / 1024**2, 2)}))
"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--group", choices=sorted(CASES), required=True)
    args = parser.parse_args()
    results = []
    with tempfile.TemporaryDirectory(prefix="bench-") as tmp:
        root = Path(tmp)
        files = _make_inputs(args.group, root)
        for category, src, dst, options in CASES[args.group]:
            work = root / f"w-{src}-{dst}"
            work.mkdir()
            payload = json.dumps([category, src, dst, options, str(files[src]), str(work)])
            proc = subprocess.run([sys.executable, "-c", _CHILD, payload], capture_output=True, text=True,  # noqa: S603
                                  timeout=1200, check=False)
            entry = {"case": f"{src}->{dst}", "options": options,
                     "input_mb": round(files[src].stat().st_size / 1024**2, 2)}
            entry.update(json.loads(proc.stdout) if proc.returncode == 0 else {"error": proc.stderr[-300:]})
            results.append(entry)
    machine = {"cpu": _cpu_model(), "nproc": os.cpu_count(), "arch": platform.machine()}
    print(json.dumps({"machine": machine, "results": results}, ensure_ascii=False, indent=2))


def _cpu_model() -> str:
    try:
        for line in Path("/proc/cpuinfo").read_text().splitlines():
            if line.startswith("model name"):
                return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return platform.processor() or "unknown"


if __name__ == "__main__":
    main()
