import io
import zipfile
from pathlib import Path

import pytest

from app.security.file_sniffing import SniffError, sniff
from app.services.uploads import safe_display_name
from app.tools.converter.handler import output_filename
from app.tools.converter.images import sanitize_svg
from app.tools.base import ToolUserError

HEIC = Path(__file__).resolve().parents[2] / "app/tools/converter/fixtures/sample.heic"


def _write(tmp_path: Path, name: str, data: bytes) -> Path:
    path = tmp_path / name
    path.write_bytes(data)
    return path


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        (b"%PDF-1.7\n...", "pdf"),
        (b"\x89PNG\r\n\x1a\n" + b"\0" * 20, "png"),
        (b"\xff\xd8\xff\xe0" + b"\0" * 20, "jpg"),
        (b"GIF89a" + b"\0" * 20, "gif"),
        (b"RIFF\x00\x00\x00\x00WEBPVP8 ", "webp"),
        (b"RIFF\x00\x00\x00\x00WAVEfmt ", "wav"),
        (b"RIFF\x00\x00\x00\x00AVI LIST", "avi"),
        (b"fLaC" + b"\0" * 20, "flac"),
        (b"OggS" + b"\0" * 24 + b"OpusHead", "opus"),
        (b"OggS" + b"\0" * 24 + b"\x01vorbis", "ogg"),
        (b"ID3\x04" + b"\0" * 20, "mp3"),
        (b"\x1a\x45\xdf\xa3" + b"\x42\x82\x84webm" + b"\0" * 10, "webm"),
        (b"\x1a\x45\xdf\xa3" + b"\x42\x82\x88matroska" + b"\0" * 10, "mkv"),
        (b"\x00\x00\x00\x18ftypqt  \x00\x00\x00\x00qt  ", "mov"),
        (b"\x00\x00\x00\x18ftypisom\x00\x00\x02\x00isomiso2", "mp4"),
        (b"\x00\x00\x00\x18ftypM4A \x00\x00\x00\x00M4A mp42", "m4a"),
        (b"\x00\x00\x00\x1cftypavif\x00\x00\x00\x00avifmif1miaf", "avif"),
        (b"II*\x00" + b"\0" * 20, "tiff"),
        (b"{\\rtf1\\ansi hello}", "rtf"),
    ],
)
def test_binary_signatures(tmp_path, data, expected):
    assert sniff(_write(tmp_path, "f.bin", data), "bin").format == expected


def test_real_heic_fixture_is_detected(tmp_path):
    assert sniff(HEIC, "heic").format == "heic"


def test_extension_is_not_trusted(tmp_path):
    # a PNG named .pdf is a PNG; a script named .jpg is rejected as unsupported binary/text mix
    assert sniff(_write(tmp_path, "x.pdf", b"\x89PNG\r\n\x1a\n" + b"\0" * 20), "pdf").format == "png"
    assert sniff(_write(tmp_path, "evil.jpg", b"#!/bin/sh\nrm -rf /\n"), "jpg").format == "txt"
    with pytest.raises(SniffError):
        sniff(_write(tmp_path, "x.exe", b"MZ\x90\x00\x03\x00\x00\x00\x04\x00\xff\xff"), "exe")


def test_text_family_uses_declared_extension(tmp_path):
    assert sniff(_write(tmp_path, "a.csv", b"a,b\n1,2\n"), "csv").format == "csv"
    assert sniff(_write(tmp_path, "a.txt", "olá\n".encode()), "txt").format == "txt"
    assert sniff(_write(tmp_path, "a.html", b"<!doctype html><html></html>"), "html").format == "html"
    assert sniff(_write(tmp_path, "a.svg", b"<?xml version='1.0'?><svg xmlns='http://www.w3.org/2000/svg'/>"),
                 "svg").format == "svg"
    with pytest.raises(SniffError):
        sniff(_write(tmp_path, "fake.svg", b"just text"), "svg")


def _zip(entries: dict[str, bytes], compress=zipfile.ZIP_DEFLATED) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compress) as archive:
        for name, data in entries.items():
            archive.writestr(name, data)
    return buf.getvalue()


def test_ooxml_and_odf_detected_from_structure(tmp_path):
    docx = _zip({"[Content_Types].xml": b"<x/>", "word/document.xml": b"<w/>"})
    xlsx = _zip({"[Content_Types].xml": b"<x/>", "xl/workbook.xml": b"<w/>"})
    odt = _zip({"mimetype": b"application/vnd.oasis.opendocument.text", "content.xml": b"<x/>"}, zipfile.ZIP_STORED)
    assert sniff(_write(tmp_path, "a.docx", docx), "docx").format == "docx"
    assert sniff(_write(tmp_path, "a.xlsx", xlsx), "xlsx").format == "xlsx"
    assert sniff(_write(tmp_path, "a.odt", odt), "odt").format == "odt"


def test_zip_bomb_rejected(tmp_path):
    bomb = _zip({"[Content_Types].xml": b"<x/>", "word/document.xml": b"\0" * (50 * 1024 * 1024)})
    with pytest.raises(SniffError) as exc:
        sniff(_write(tmp_path, "bomb.docx", bomb), "docx")
    assert exc.value.code == "decompression_bomb"


def test_random_zip_is_not_a_document(tmp_path):
    with pytest.raises(SniffError):
        sniff(_write(tmp_path, "a.docx", _zip({"payload.exe": b"MZ"})), "docx")


def test_empty_and_corrupted_files(tmp_path):
    with pytest.raises(SniffError) as exc:
        sniff(_write(tmp_path, "e.pdf", b""), "pdf")
    assert exc.value.code == "empty_file"
    with pytest.raises(SniffError):
        sniff(_write(tmp_path, "c.docx", b"PK\x03\x04garbage-not-a-zip"), "docx")


def test_svg_sanitizer_removes_scripts_and_external_refs(tmp_path):
    hostile = (
        b'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" onload="alert(1)">'
        b'<script>alert(2)</script><foreignObject><iframe src="http://x"/></foreignObject>'
        b'<image xlink:href="file:///etc/passwd"/><image href="http://169.254.169.254/"/>'
        b'<style>@import url(http://evil/x.css);</style>'
        b'<rect fill="url(http://evil/p)" width="1" height="1"/><use href="#ok"/></svg>'
    )
    clean = sanitize_svg(_write(tmp_path, "h.svg", hostile), tmp_path).read_text()
    for bad in ("script", "foreignObject", "iframe", "onload", "/etc/passwd", "169.254", "evil", "@import"):
        assert bad not in clean, bad
    assert 'href="#ok"' in clean


def test_svg_with_entities_or_dtd_is_rejected(tmp_path):
    xxe = (b'<?xml version="1.0"?><!DOCTYPE svg [<!ENTITY x SYSTEM "file:///etc/passwd">]>'
           b'<svg xmlns="http://www.w3.org/2000/svg"><text>&x;</text></svg>')
    with pytest.raises(ToolUserError):
        sanitize_svg(_write(tmp_path, "x.svg", xxe), tmp_path)


@pytest.mark.parametrize("name", ["../../etc/passwd", "..\\..\\win.ini", "/abs/x.pdf", "a\x00b.pdf", ""])
def test_original_names_never_become_paths(name):
    display = safe_display_name(name)
    assert "/" not in display and "\\" not in display and "\x00" not in display and display
    assert "/" not in output_filename(display, "pdf") and output_filename(display, "pdf").endswith(".pdf")
