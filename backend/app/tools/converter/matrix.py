"""Candidate conversions for the launch set (PRD §6.2).

A candidate becomes `available` ONLY if it is listed in `verified.json`, which is written by
`python -m app.tools.converter.verify` after a real conversion succeeds inside the worker image.
Everything else is seeded as `planned`.
"""

import json
from dataclasses import dataclass
from pathlib import Path

DOC_TO_PDF_INPUTS = ("docx", "doc", "odt", "rtf", "txt", "html")
IMAGE_INPUTS = ("jpg", "png", "webp", "avif", "gif", "bmp", "tiff", "ico", "heic", "svg")
IMAGE_OUTPUTS = ("jpg", "png", "webp", "avif", "gif", "bmp", "tiff", "ico")
AUDIO_FORMATS = ("mp3", "wav", "ogg", "m4a", "flac", "opus")
VIDEO_FORMATS = ("mp4", "webm", "mkv", "mov", "avi")

QUEUE_BY_CATEGORY = {"document": "light", "image": "light", "audio": "media", "video": "media"}

# Limitations shown to the user next to the combination.
NOTES = {
    ("pdf", "docx"): "A conversão de PDF para DOCX perde parte do layout (colunas, fontes, posições).",
    ("pdf", "txt"): "PDF escaneado (imagem) não tem texto: o resultado sai vazio. OCR não está disponível.",
    ("xlsx", "csv"): "Apenas a primeira planilha é convertida.",
    ("xls", "csv"): "Apenas a primeira planilha é convertida.",
    ("html", "pdf"): "Imagens e estilos externos (links da internet) não são carregados.",
}
GIF_NOTE = "GIF animado: apenas o primeiro quadro é convertido."
VIDEO_GIF_NOTE = "Usa no máximo os primeiros 15 segundos, até 480 px de largura e 10 quadros/s."


@dataclass(frozen=True)
class Candidate:
    input_format: str
    output_format: str
    category: str
    engine: str

    @property
    def key(self) -> str:
        return f"{self.input_format}->{self.output_format}"

    @property
    def queue(self) -> str:
        return QUEUE_BY_CATEGORY[self.category]

    def note(self) -> str | None:
        if (self.input_format, self.output_format) in NOTES:
            return NOTES[(self.input_format, self.output_format)]
        if self.category == "video" and self.output_format == "gif":
            return VIDEO_GIF_NOTE
        if self.input_format == "gif" and self.output_format != "gif":
            return GIF_NOTE
        return None


def candidates() -> list[Candidate]:
    items: list[Candidate] = []
    for src in DOC_TO_PDF_INPUTS:
        items.append(Candidate(src, "pdf", "document", "libreoffice"))
    items.append(Candidate("pdf", "docx", "document", "libreoffice"))
    items.append(Candidate("pdf", "txt", "document", "pdftotext"))
    items.append(Candidate("doc", "docx", "document", "libreoffice"))
    for src in ("xlsx", "xls"):
        items.append(Candidate(src, "csv", "document", "libreoffice"))
    items.append(Candidate("csv", "xlsx", "document", "libreoffice"))

    for src in IMAGE_INPUTS:
        for dst in IMAGE_OUTPUTS:
            if src != dst:
                engine = "pillow" if "bmp" in (src, dst) or "ico" in (src, dst) else "libvips"
                items.append(Candidate(src, dst, "image", engine))

    for src in AUDIO_FORMATS:
        for dst in AUDIO_FORMATS:
            if src != dst:
                items.append(Candidate(src, dst, "audio", "ffmpeg"))

    for src in VIDEO_FORMATS:
        for dst in VIDEO_FORMATS:
            if src != dst:
                items.append(Candidate(src, dst, "video", "ffmpeg"))
        for dst in ("mp3", "m4a", "wav", "ogg", "opus", "flac"):  # extract audio
            items.append(Candidate(src, dst, "video", "ffmpeg"))
        items.append(Candidate(src, "gif", "video", "ffmpeg"))
    return items


VERIFIED_FILE = Path(__file__).with_name("verified.json")


def verified_keys() -> set[str]:
    if not VERIFIED_FILE.exists():
        return set()
    data = json.loads(VERIFIED_FILE.read_text(encoding="utf-8"))
    return {item["key"] for item in data.get("passed", [])}


def find(input_format: str, output_format: str) -> Candidate | None:
    for c in candidates():
        if c.input_format == input_format and c.output_format == output_format:
            return c
    return None
