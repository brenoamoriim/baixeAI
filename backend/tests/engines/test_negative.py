import io
import struct
import time
import zipfile
import zlib
from pathlib import Path

import pytest

from app.core.errors import AppError
from app.security.sandbox import Limits, SandboxTimeout, run
from app.tools.base import ToolUserError
from app.tools.converter import documents, images, media
from app.tools.converter.handler import ConverterHandler
from tests.engines.conftest import light
from tests.engines.conftest import media as media_mark


def _png_header_only(width: int, height: int) -> bytes:
    """A PNG whose IHDR claims huge dimensions (decompression-bomb shape) with a tiny body."""
    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(b"\0" * 64)) + chunk(b"IEND", b"")


# ---------------------------------------------------------------- sandbox (no engines needed)


def test_sandbox_kills_on_timeout(tmp_path):
    started = time.monotonic()
    with pytest.raises(SandboxTimeout):
        run(["sh", "-c", "sleep 30 & sleep 30"], cwd=tmp_path, limits=Limits(timeout_seconds=1))
    assert time.monotonic() - started < 5


def test_sandbox_does_not_leak_secrets_to_engines(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://secret@db/x")
    out = run(["env"], cwd=tmp_path, limits=Limits(timeout_seconds=5))
    assert "secret" not in out and "DATABASE_URL" not in out


def test_sandbox_never_uses_a_shell(tmp_path):
    out = run(["echo", "$(id); rm -rf /"], cwd=tmp_path, limits=Limits(timeout_seconds=5))
    assert out.strip() == "$(id); rm -rf /"


def test_sandbox_enforces_file_size_limit(tmp_path):
    with pytest.raises(Exception):  # noqa: B017 - SIGXFSZ/exit != 0 surfaces as SandboxFailed
        run(["sh", "-c", "head -c 5000000 /dev/zero > big"], cwd=tmp_path,
            limits=Limits(timeout_seconds=5, max_file_bytes=1_000_000))
    assert (tmp_path / "big").stat().st_size <= 1_000_000


# ---------------------------------------------------------------- option injection (no engines)


@pytest.mark.parametrize("options", [
    {"quality": "-i /etc/passwd"},
    {"bitrate": "192k -f lavfi"},
    {"resolution": "720,scale=99999"},
    {"filter_complex": "x"},
    {"fps": "1000"},
])
def test_options_outside_closed_lists_are_rejected(options):
    handler = ConverterHandler()
    meta = {"has_audio": True, "has_video": True}
    for src, dst in (("png", "jpg"), ("mp3", "wav"), ("mp4", "webm")):
        with pytest.raises(AppError):
            handler.validate_options(src, dst, options | {"upload_id": "x"}, meta)


def test_audio_extraction_requires_audio_track():
    with pytest.raises(AppError) as exc:
        ConverterHandler().validate_options("mp4", "mp3", {}, {"has_video": True, "has_audio": False})
    assert exc.value.code == "no_audio"


# ---------------------------------------------------------------- light engines


@light
def test_pixel_bomb_is_detected_from_header_without_decoding(tmp_path):
    bomb = tmp_path / "bomb.png"
    bomb.write_bytes(_png_header_only(60000, 60000))
    started = time.monotonic()
    width, height = images.dimensions(bomb, "png", tmp_path)
    assert (width, height) == (60000, 60000)  # the probe then rejects it (> 40 MP) before charging
    assert time.monotonic() - started < 5


@light
def test_svg_with_absurd_size_fails_inside_memory_limit(tmp_path):
    svg = tmp_path / "huge.svg"
    svg.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="200000" height="200000">'
                   '<rect width="10" height="10"/></svg>')
    with pytest.raises((ToolUserError, TimeoutError)):
        images.dimensions(svg, "svg", tmp_path)


@light
def test_imagemagick_and_untrusted_loaders_are_blocked(tmp_path):
    # PPM is only loadable through an "untrusted" libvips loader: it must be refused.
    ppm = tmp_path / "x.ppm"
    ppm.write_bytes(b"P6\n2 2\n255\n" + b"\xff" * 12)
    with pytest.raises(ToolUserError):
        images.dimensions(ppm, "png", tmp_path)


@light
def test_corrupted_docx_is_a_user_error(tmp_path):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as archive:
        archive.writestr("[Content_Types].xml", "<broken")
        archive.writestr("word/document.xml", "<<<not xml")
    path = tmp_path / "input.docx"
    path.write_bytes(buf.getvalue())
    with pytest.raises(ToolUserError):
        documents.convert(path, "docx", "pdf", tmp_path)


MACRO_CONTENT = (
    '<?xml version="1.0" encoding="UTF-8"?><office:document-content '
    'xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
    'xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" '
    'xmlns:script="urn:oasis:names:tc:opendocument:xmlns:script:1.0" '
    'xmlns:xlink="http://www.w3.org/1999/xlink" office:version="1.2"><office:scripts><office:event-listeners>'
    '<script:event-listener script:language="ooo:script" script:event-name="office:load" '
    'xlink:href="vnd.sun.star.script:Standard.Module1.Main?language=Basic&amp;location=document"/>'
    '</office:event-listeners></office:scripts><office:body><office:text><text:p>macro test</text:p>'
    '</office:text></office:body></office:document-content>'
)
LIB_CONTAINER = (
    '<?xml version="1.0" encoding="UTF-8"?><!DOCTYPE library:libraries PUBLIC "-//OpenOffice.org//DTD OfficeDocument 1.0//EN" "libraries.dtd">'
    '<library:libraries xmlns:library="http://openoffice.org/2000/library" xmlns:xlink="http://www.w3.org/1999/xlink">'
    '<library:library library:name="Standard" library:link="false"/></library:libraries>'
)
LIB_INDEX = (
    '<?xml version="1.0" encoding="UTF-8"?><!DOCTYPE library:library PUBLIC "-//OpenOffice.org//DTD OfficeDocument 1.0//EN" "library.dtd">'
    '<library:library xmlns:library="http://openoffice.org/2000/library" library:name="Standard" '
    'library:readonly="false" library:passwordprotected="false"><library:element library:name="Module1"/></library:library>'
)


def _macro_odt(marker: Path) -> bytes:
    module = (
        '<?xml version="1.0" encoding="UTF-8"?><!DOCTYPE script:module PUBLIC "-//OpenOffice.org//DTD OfficeDocument 1.0//EN" "module.dtd">'
        '<script:module xmlns:script="http://openoffice.org/2000/script" script:name="Module1" script:language="StarBasic">'
        f'Sub Main\n  Shell("sh", 0, "-c ""touch {marker}""")\nEnd Sub\n</script:module>'
    )
    manifest = (
        '<?xml version="1.0"?><manifest:manifest xmlns:manifest="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0" '
        'manifest:version="1.2"><manifest:file-entry manifest:full-path="/" '
        'manifest:media-type="application/vnd.oasis.opendocument.text"/>'
        '<manifest:file-entry manifest:full-path="content.xml" manifest:media-type="text/xml"/>'
        '<manifest:file-entry manifest:full-path="Basic/" manifest:media-type=""/>'
        '<manifest:file-entry manifest:full-path="Basic/script-lc.xml" manifest:media-type="text/xml"/>'
        '<manifest:file-entry manifest:full-path="Basic/Standard/" manifest:media-type=""/>'
        '<manifest:file-entry manifest:full-path="Basic/Standard/script-lb.xml" manifest:media-type="text/xml"/>'
        '<manifest:file-entry manifest:full-path="Basic/Standard/Module1.xml" manifest:media-type="text/xml"/>'
        '</manifest:manifest>'
    )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as archive:
        archive.writestr(zipfile.ZipInfo("mimetype"), "application/vnd.oasis.opendocument.text")
        archive.writestr("content.xml", MACRO_CONTENT)
        archive.writestr("Basic/script-lc.xml", LIB_CONTAINER)
        archive.writestr("Basic/Standard/script-lb.xml", LIB_INDEX)
        archive.writestr("Basic/Standard/Module1.xml", module)
        archive.writestr("META-INF/manifest.xml", manifest)
    return buf.getvalue()


@light
def test_document_macros_do_not_run(tmp_path):
    """ODT with a Basic macro bound to the document-open event that would create a file.

    Honest limitation: a control run with macro security DISABLED did not execute the macro either
    (headless --convert-to apparently does not fire office:load). So this is a regression guard for
    "converting a macro document runs nothing", not proof that the profile settings are effective.
    """
    marker = tmp_path / "macro-ran"
    path = tmp_path / "input.odt"
    path.write_bytes(_macro_odt(marker))
    out = documents.convert(path, "odt", "pdf", tmp_path)
    assert out.exists()  # the document itself is processed...
    assert not marker.exists(), "macro executed!"  # ...but its macro never runs


@light
def test_html_external_resources_are_not_fetched(tmp_path):
    """Worker has no network; the conversion must still complete without the remote image."""
    path = tmp_path / "input.html"
    path.write_text("<html><body><p>ok</p><img src='http://169.254.169.254/latest/meta-data/'></body></html>")
    started = time.monotonic()
    assert documents.convert(path, "html", "pdf", tmp_path).exists()
    assert time.monotonic() - started < 60


# ---------------------------------------------------------------- media engines


@media_mark
def test_garbage_after_mp4_signature_is_rejected(tmp_path):
    path = tmp_path / "fake.mp4"
    path.write_bytes(b"\x00\x00\x00\x18ftypisom\x00\x00\x02\x00isomiso2" + b"\x13\x37" * 5000)
    with pytest.raises(ToolUserError):
        media.probe(path, "mp4", tmp_path)


@media_mark
def test_playlist_disguised_as_media_cannot_read_local_files(tmp_path):
    """An HLS/concat playlist pointing at /etc/passwd: the forced demuxer refuses it."""
    path = tmp_path / "evil.mp3"
    path.write_text("#EXTM3U\n#EXTINF:1,\nfile:///etc/passwd\n")
    with pytest.raises(ToolUserError):
        media.probe(path, "mp3", tmp_path)
    with pytest.raises(ToolUserError):
        media.probe(Path(path), "mp4", tmp_path)
