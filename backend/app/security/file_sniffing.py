"""Detect the real file format from its content (magic bytes / container structure).

The file extension and the browser's MIME type are never trusted. This module only reads
headers and container directories (no decoding), so it is safe to run in the API process.
Deep inspection (decode, duration, dimensions) happens later in an isolated worker.
"""

import zipfile
from dataclasses import dataclass
from pathlib import Path

import olefile

# ZIP-based documents: limits against decompression bombs while listing entries.
MAX_ZIP_ENTRIES = 2000
MAX_ZIP_UNCOMPRESSED = 300 * 1024 * 1024
MAX_ZIP_RATIO = 200

CATEGORY = {
    **dict.fromkeys(("pdf", "docx", "doc", "odt", "rtf", "txt", "html", "xlsx", "xls", "csv"), "document"),
    **dict.fromkeys(("jpg", "png", "webp", "avif", "gif", "bmp", "tiff", "ico", "heic", "svg"), "image"),
    **dict.fromkeys(("mp3", "wav", "ogg", "m4a", "flac", "opus"), "audio"),
    **dict.fromkeys(("mp4", "webm", "mkv", "mov", "avi"), "video"),
}

# Formats whose content is plain text: the declared extension decides between them.
TEXT_FAMILY = ("txt", "csv", "html", "svg")


@dataclass(frozen=True)
class Sniffed:
    format: str
    category: str


class SniffError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _ftyp_brand(head: bytes) -> tuple[str, bytes] | None:
    if len(head) >= 12 and head[4:8] == b"ftyp":
        size = int.from_bytes(head[0:4], "big")
        brands = head[8 : min(size, len(head))] if size >= 16 else head[8:12]
        return head[8:12].decode("latin-1"), brands
    return None


def _sniff_zip(path: Path) -> str:
    try:
        with zipfile.ZipFile(path) as archive:
            infos = archive.infolist()
            if len(infos) > MAX_ZIP_ENTRIES:
                raise SniffError("archive_too_complex", "O arquivo tem estrutura interna grande demais.")
            total = sum(i.file_size for i in infos)
            compressed = sum(i.compress_size for i in infos) or 1
            if total > MAX_ZIP_UNCOMPRESSED or total / compressed > MAX_ZIP_RATIO:
                raise SniffError("decompression_bomb", "O arquivo parece uma bomba de descompressão.")
            names = {i.filename for i in infos}
            if "mimetype" in names:
                mimetype = archive.read("mimetype")[:100].strip()
                if mimetype == b"application/vnd.oasis.opendocument.text":
                    return "odt"
            if "[Content_Types].xml" in names:
                if any(n.startswith("word/") for n in names):
                    return "docx"
                if any(n.startswith("xl/") for n in names):
                    return "xlsx"
    except zipfile.BadZipFile:
        raise SniffError("corrupted", "O arquivo está corrompido.") from None
    raise SniffError("unsupported_format", "Formato de arquivo não suportado.")


def _sniff_ole(path: Path) -> str:
    try:
        with olefile.OleFileIO(str(path)) as ole:
            if ole.exists("WordDocument"):
                return "doc"
            if ole.exists("Workbook") or ole.exists("Book"):
                return "xls"
    except OSError:
        raise SniffError("corrupted", "O arquivo está corrompido.") from None
    raise SniffError("unsupported_format", "Formato de arquivo não suportado.")


def _is_text(head: bytes) -> bool:
    if b"\x00" in head:
        return False
    sample = head[:-4] if len(head) >= 4096 else head  # tolerate a cut multibyte char
    try:
        sample.decode("utf-8")
        return True
    except UnicodeDecodeError:
        try:
            sample.decode("cp1252")
            return True
        except UnicodeDecodeError:
            return False


def _sniff_text(head: bytes, declared: str) -> str:
    text = head.lstrip(b"\xef\xbb\xbf").lstrip().lower()
    if text.startswith(b"{\\rtf"):
        return "rtf"
    looks_svg = b"<svg" in text[:4096] and (text.startswith(b"<?xml") or text.startswith(b"<svg")
                                            or text.startswith(b"<!--") or text.startswith(b"<!doctype svg"))
    looks_html = text.startswith(b"<!doctype html") or text.startswith(b"<html") or b"<html" in text[:1024]
    if declared == "svg":
        if looks_svg:
            return "svg"
        raise SniffError("format_mismatch", "O conteúdo não é uma imagem SVG.")
    if looks_svg and declared != "txt":
        return "svg"
    if declared == "html" or looks_html:
        return "html"
    if declared in ("csv", "txt"):
        return declared
    return "txt"


def sniff(path: Path, declared_extension: str) -> Sniffed:
    """Return the real format. `declared_extension` only breaks ties inside a family."""
    declared = declared_extension.lower().lstrip(".")
    declared = {"jpeg": "jpg", "tif": "tiff", "htm": "html", "heif": "heic", "aac": "m4a"}.get(declared, declared)
    with path.open("rb") as handle:
        head = handle.read(8192)
    if not head:
        raise SniffError("empty_file", "O arquivo está vazio.")

    fmt = _sniff_binary(head, path)
    if fmt is None:
        if not _is_text(head):
            raise SniffError("unsupported_format", "Formato de arquivo não suportado.")
        fmt = _sniff_text(head, declared)
    return Sniffed(format=fmt, category=CATEGORY[fmt])


def _sniff_binary(head: bytes, path: Path) -> str | None:  # noqa: PLR0911, PLR0912
    if head.startswith(b"%PDF-"):
        return "pdf"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if head.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if head.startswith((b"GIF87a", b"GIF89a")):
        return "gif"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "webp"
    if head[:4] == b"RIFF" and head[8:12] == b"WAVE":
        return "wav"
    if head[:4] == b"RIFF" and head[8:12] == b"AVI ":
        return "avi"
    bmp_header_sizes = (12, 40, 52, 56, 108, 124)
    if head.startswith(b"BM") and len(head) > 14 and int.from_bytes(head[14:18], "little") in bmp_header_sizes:
        return "bmp"
    if head.startswith((b"II*\x00", b"MM\x00*")):
        return "tiff"
    if head.startswith(b"\x00\x00\x01\x00") and len(head) > 6 and head[4] > 0:
        return "ico"
    if head.startswith(b"fLaC"):
        return "flac"
    if head.startswith(b"OggS"):
        return "opus" if b"OpusHead" in head[:512] else "ogg"
    if head.startswith(b"ID3") or (head[0] == 0xFF and head[1] & 0xE0 == 0xE0 and head[1] & 0x06 != 0):
        # MPEG audio frame sync (layer bits != 00); ADTS AAC uses layer 00 and is not accepted
        return "mp3"
    if head.startswith(b"\x1a\x45\xdf\xa3"):
        return "webm" if b"webm" in head[:64] else "mkv"
    brand = _ftyp_brand(head)
    if brand:
        major, brands = brand
        if major in ("avif", "avis"):
            return "avif"
        if major in ("heic", "heix", "heim", "heis", "mif1", "msf1"):
            return "avif" if b"avif" in brands else "heic"
        if major == "qt  ":
            return "mov"
        if major in ("M4A ", "M4B "):
            return "m4a"
        return "mp4"
    if head.startswith(b"PK\x03\x04"):
        return _sniff_zip(path)
    if head.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"):
        return _sniff_ole(path)
    return None
