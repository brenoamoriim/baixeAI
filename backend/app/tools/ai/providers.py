"""Local CPU image-AI providers behind abstract interfaces (swap engines without touching
credits/accounts). Models are baked into the worker-ai image (no download at runtime) and loaded
once per worker process.

Licenses (verified 18/10/2026, see docs/architecture/07 §4):
- onnxruntime: MIT
- IS-Net general-use weights: Apache-2.0 (xuebinqin/DIS); file from the rembg (MIT) release,
  md5 matches rembg's published checksum. Pre/post-processing mirrors rembg's DisSession.
- LaMa (big-lama) ONNX port, Carve/LaMa-ONNX: Apache-2.0 (code advimman/lama: Apache-2.0).
  Residual risk: the training dataset (Places2) terms were not verified.
"""

import os
import threading
from abc import ABC, abstractmethod
from functools import lru_cache
from pathlib import Path

from PIL import Image

MODEL_DIR = Path(os.environ.get("AI_MODEL_DIR", "/opt/models"))
ISNET_FILE = "isnet-general-use.onnx"
LAMA_FILE = "lama_fp32.onnx"
LAMA_SIZE = 512
ISNET_SIZE = 1024
_lock = threading.Lock()


class BackgroundRemovalProvider(ABC):
    @abstractmethod
    def mask(self, image: Image.Image) -> Image.Image:
        """Return an 'L' alpha mask (255 = keep) with the same size as `image`."""


class InpaintingProvider(ABC):
    @abstractmethod
    def inpaint(self, image: Image.Image, mask: Image.Image) -> Image.Image:
        """Fill the white area of `mask` ('L', same size). Returns RGB, same size."""


def _session(filename: str):
    import onnxruntime as ort

    path = MODEL_DIR / filename
    if not path.is_file():
        raise FileNotFoundError(f"model not found: {path}")
    options = ort.SessionOptions()
    options.intra_op_num_threads = int(os.environ.get("AI_THREADS", "2"))
    options.inter_op_num_threads = 1
    return ort.InferenceSession(str(path), sess_options=options, providers=["CPUExecutionProvider"])


class IsNetBackground(BackgroundRemovalProvider):
    def __init__(self) -> None:
        self.session = _session(ISNET_FILE)
        self.input_name = self.session.get_inputs()[0].name

    def mask(self, image: Image.Image) -> Image.Image:
        import numpy as np  # worker-ai only (not installed in the API image)

        rgb = image.convert("RGB").resize((ISNET_SIZE, ISNET_SIZE), Image.Resampling.LANCZOS)
        array = np.asarray(rgb, dtype=np.float32)
        array = array / max(float(array.max()), 1e-6)
        array = (array - 0.5) / 1.0
        tensor = np.expand_dims(array.transpose(2, 0, 1), 0).astype(np.float32)
        pred = self.session.run(None, {self.input_name: tensor})[0][:, 0, :, :]
        lo, hi = float(pred.min()), float(pred.max())
        pred = (pred - lo) / max(hi - lo, 1e-6)
        mask = Image.fromarray((np.squeeze(pred) * 255).astype(np.uint8), mode="L")
        return mask.resize(image.size, Image.Resampling.LANCZOS)


class LamaInpainting(InpaintingProvider):
    def __init__(self) -> None:
        self.session = _session(LAMA_FILE)

    def _run(self, crop: Image.Image, crop_mask: Image.Image) -> Image.Image:
        import numpy as np  # worker-ai only (not installed in the API image)

        img = np.asarray(crop.convert("RGB").resize((LAMA_SIZE, LAMA_SIZE), Image.Resampling.BICUBIC),
                         dtype=np.float32) / 255.0
        msk = np.asarray(crop_mask.resize((LAMA_SIZE, LAMA_SIZE), Image.Resampling.NEAREST), dtype=np.float32) / 255.0
        msk = (msk > 0.5).astype(np.float32)
        out = self.session.run(None, {"image": np.expand_dims(img.transpose(2, 0, 1), 0),
                                      "mask": msk[None, None, :, :]})[0][0]
        out = out.transpose(1, 2, 0)
        if out.max() <= 1.5:  # some exports return 0..1
            out = out * 255.0
        result = Image.fromarray(np.clip(out, 0, 255).astype(np.uint8), mode="RGB")
        return result.resize(crop.size, Image.Resampling.BICUBIC)

    def inpaint(self, image: Image.Image, mask: Image.Image) -> Image.Image:
        """Inpaint only a crop around the mask (keeps detail on large photos), then paste back
        strictly inside the mask, so pixels outside it are untouched."""
        rgb = image.convert("RGB")
        box = mask.getbbox()
        if box is None:
            return rgb
        left, top, right, bottom = box
        side = max(right - left, bottom - top)
        pad = max(32, side // 2)
        side = min(max(side + 2 * pad, LAMA_SIZE // 2), max(rgb.size))
        cx, cy = (left + right) // 2, (top + bottom) // 2
        x0 = min(max(cx - side // 2, 0), max(rgb.width - side, 0))
        y0 = min(max(cy - side // 2, 0), max(rgb.height - side, 0))
        crop_box = (x0, y0, min(x0 + side, rgb.width), min(y0 + side, rgb.height))
        filled = self._run(rgb.crop(crop_box), mask.crop(crop_box))
        result = rgb.copy()
        result.paste(filled, crop_box[:2], mask.crop(crop_box))
        return result


@lru_cache(maxsize=1)
def background_provider() -> BackgroundRemovalProvider:
    with _lock:
        return IsNetBackground()


@lru_cache(maxsize=1)
def inpainting_provider() -> InpaintingProvider:
    with _lock:
        return LamaInpainting()
