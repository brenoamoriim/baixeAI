import shutil
from pathlib import Path

import pytest

from app.tools.converter import verify

LIGHT_BINARIES = ("soffice", "vips", "vipsheader", "pdftotext", "rsvg-convert")
MEDIA_BINARIES = ("ffmpeg", "ffprobe")

HAS_LIGHT = all(shutil.which(b) for b in LIGHT_BINARIES)
HAS_MEDIA = all(shutil.which(b) for b in MEDIA_BINARIES)

light = pytest.mark.skipif(not HAS_LIGHT, reason="run inside worker-light (LibreOffice/libvips missing here)")
media = pytest.mark.skipif(not HAS_MEDIA, reason="run inside worker-media (FFmpeg missing here)")


@pytest.fixture(scope="session")
def fixtures(tmp_path_factory) -> dict[str, dict[str, Path]]:
    categories = []
    if HAS_LIGHT:
        categories += ["document", "image"]
    if HAS_MEDIA:
        categories += ["audio", "video"]
    return verify.make_fixtures(categories, tmp_path_factory.mktemp("fixtures"))
