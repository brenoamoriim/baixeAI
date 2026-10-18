"""Latency and memory of the AI providers on CPU (fresh process per case).

    docker compose run --rm --no-deps worker-ai python -m app.tools.ai.benchmark
"""

import json
import os
import platform
import subprocess
import sys

CASES = [
    ("background", 1280, 800, None), ("background", 2448, 1632, None), ("background", 4000, 3000, None),
    ("inpaint", 1280, 800, 120), ("inpaint", 4000, 3000, 120), ("inpaint", 4000, 3000, 900),
]

_CHILD = """
import json, resource, sys, time
from PIL import Image, ImageDraw
from app.tools.ai import providers
kind, w, h, box = json.loads(sys.argv[1])
image = Image.effect_noise((w, h), 40).convert("RGB")
t0 = time.monotonic()
provider = providers.background_provider() if kind == "background" else providers.inpainting_provider()
load = time.monotonic() - t0
runs = []
for _ in range(2):
    t1 = time.monotonic()
    if kind == "background":
        provider.mask(image)
    else:
        mask = Image.new("L", (w, h), 0)
        half = box // 2
        ImageDraw.Draw(mask).rectangle((w // 2 - half, h // 2 - half, w // 2 + half, h // 2 + half), fill=255)
        provider.inpaint(image, mask)
    runs.append(time.monotonic() - t1)
peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
print(json.dumps({"load_s": round(load, 2), "first_s": round(runs[0], 2), "warm_s": round(runs[1], 2),
                  "peak_rss_mb": round(peak)}))
"""


def main() -> None:
    results = []
    for kind, w, h, box in CASES:
        proc = subprocess.run([sys.executable, "-c", _CHILD, json.dumps([kind, w, h, box])],  # noqa: S603
                              capture_output=True, text=True, timeout=1800, check=False)
        entry = {"case": kind, "size": f"{w}x{h}", "megapixels": round(w * h / 1e6, 1)}
        if box:
            entry["mask_side_px"] = box
        entry.update(json.loads(proc.stdout) if proc.returncode == 0 else {"error": proc.stderr[-300:]})
        results.append(entry)
        print(json.dumps(entry), flush=True)
    cpu = next((line.split(":", 1)[1].strip() for line in open("/proc/cpuinfo") if line.startswith("model name")), "?")
    print(json.dumps({"machine": {"cpu": cpu, "nproc": os.cpu_count(), "arch": platform.machine(),
                                  "threads": os.environ.get("AI_THREADS")}, "results": results}, indent=2))


if __name__ == "__main__":
    main()
