"""VideoExtractor interface + yt-dlp implementation (PRD §6.1).

Runs ONLY in worker-download, whose sole route to the internet is the egress proxy. yt-dlp is
used through its Python API (no shell), with no cookies, no login, no config files, no
playlists and no live streams. Options shown to the user come from the real format list.
"""

import json
import os
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

AUDIO_OUTPUTS = ("m4a", "mp3")
VIDEO_OUTPUTS = ("mp4",)
# yt-dlp error text -> (error_code, error_class, message). Order matters (first match wins).
_ERRORS = [
    (
        ("blocked by egress policy",),
        "blocked_destination",
        "user_input",
        "O link (ou um redirecionamento dele) aponta para um endereço não permitido.",
    ),
    (
        ("unable to obtain file audio codec", "does not contain any stream", "no audio"),
        "no_audio",
        "system",
        "Este vídeo não tem faixa de áudio.",
    ),
    (("unsupported url",), "unsupported_site", "user_input", "Não encontramos um vídeo neste link."),
    (("drm",), "drm_protected", "user_input", "Este conteúdo é protegido (DRM) e não pode ser baixado."),
    (
        ("private video", "this video is private", "members-only", "join this channel"),
        "private_content",
        "user_input",
        "Este vídeo é privado ou exclusivo para membros.",
    ),
    (
        ("sign in", "login required", "log in", "confirm your age", "age-restricted", "cookies"),
        "login_required",
        "user_input",
        "Este vídeo exige login na plataforma; só baixamos conteúdo público.",
    ),
    (
        (
            "video unavailable",
            "has been removed",
            "not available",
            "no longer available",
            "http error 404",
            "does not exist",
        ),
        "unavailable",
        "user_input",
        "Este vídeo não está disponível.",
    ),
    (
        ("is live", "live event", "premieres in"),
        "live_stream",
        "user_input",
        "Transmissões ao vivo não são suportadas.",
    ),
    (("larger than max-filesize", "max_filesize"), "too_large", "system", "O vídeo é maior que o limite permitido."),
    (
        ("http error 403", "http error 429", "too many requests", "not a bot", "blocked"),
        "blocked_by_platform",
        "system",
        "A plataforma bloqueou o acesso a partir do nosso servidor. Tente mais tarde.",
    ),
]


class ExtractionError(Exception):
    def __init__(self, code: str, error_class: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.error_class = error_class
        self.message = message


def classify(text: str) -> ExtractionError:
    lowered = text.lower()
    for needles, code, error_class, message in _ERRORS:
        if any(n in lowered for n in needles):
            return ExtractionError(code, error_class, message)
    return ExtractionError("extractor_failed", "system", "O extrator falhou ao processar este link. Tente mais tarde.")


@dataclass
class VideoInfo:
    title: str
    duration_seconds: float | None
    extractor: str
    heights: list[int]
    has_audio: bool
    has_video: bool
    filesize_approx: int | None


class VideoExtractor(ABC):
    @abstractmethod
    def inspect(self, url: str) -> VideoInfo: ...

    @abstractmethod
    def download(
        self, url: str, output: str, quality: str, work_dir: Path, progress: Callable[[int], None]
    ) -> Path: ...


class YtDlpExtractor(VideoExtractor):
    def __init__(self, *, proxy: str | None, max_bytes: int, max_seconds: int) -> None:
        self.proxy = proxy
        self.max_bytes = max_bytes
        self.max_seconds = max_seconds

    def _base_options(self) -> dict:
        options = {
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
            "noplaylist": True,
            "playlist_items": "1",
            "socket_timeout": 20,
            "retries": 2,
            "fragment_retries": 2,
            "extractor_retries": 1,
            "cachedir": False,
            "usenetrc": False,
            "cookiefile": None,
            "ignoreconfig": True,
            "check_formats": False,
            "max_filesize": self.max_bytes,
            "concurrent_fragment_downloads": 2,
            "restrictfilenames": True,
            "windowsfilenames": True,
        }
        if self.proxy:
            options["proxy"] = self.proxy
        return options

    def _extract(self, url: str, options: dict, download: bool):
        import yt_dlp

        try:
            with yt_dlp.YoutubeDL(options) as ydl:
                return ydl.extract_info(url, download=download)
        except yt_dlp.utils.DownloadError as exc:
            raise classify(str(exc)) from None
        except yt_dlp.utils.YoutubeDLError as exc:
            raise classify(str(exc)) from None

    def inspect(self, url: str) -> VideoInfo:
        info = self._extract(url, {**self._base_options(), "skip_download": True}, download=False)
        if info is None:
            raise ExtractionError("unavailable", "user_input", "Este vídeo não está disponível.")
        if info.get("_type") in ("playlist", "multi_video"):
            raise ExtractionError(
                "playlist", "user_input", "Envie o link de um único vídeo (playlists não são suportadas)."
            )
        if info.get("is_live") or info.get("live_status") in ("is_live", "is_upcoming"):
            raise ExtractionError("live_stream", "user_input", "Transmissões ao vivo não são suportadas.")
        formats = info.get("formats") or [info]
        usable = [f for f in formats if not f.get("has_drm")]
        if not usable:
            raise ExtractionError(
                "drm_protected", "user_input", "Este conteúdo é protegido (DRM) e não pode ser baixado."
            )
        heights = sorted(
            {int(f["height"]) for f in usable if f.get("vcodec") not in (None, "none") and f.get("height")}
        )
        has_video = bool(heights) or any(f.get("vcodec") not in (None, "none") for f in usable)
        has_audio = any(f.get("acodec") not in (None, "none") for f in usable)
        duration = info.get("duration")
        direct_url = info.get("url") or (usable[0].get("url") if len(usable) == 1 else None)
        if (duration is None or not (has_video or has_audio)) and direct_url:
            # Direct file links: the generic extractor reports no metadata, so measure it for real
            # (through the same egress proxy) instead of guessing price or options.
            probed = self._ffprobe(direct_url)
            duration = duration or probed.get("duration")
            heights = heights or probed["heights"]
            has_video = has_video or bool(probed["heights"]) or probed["has_video"]
            has_audio = has_audio or probed["has_audio"]
        if not duration:
            raise ExtractionError(
                "unknown_duration",
                "user_input",
                "Não foi possível determinar a duração deste vídeo, por isso ele não pode ser baixado.",
            )
        if duration and duration > self.max_seconds:
            raise ExtractionError(
                "too_long", "user_input", f"O vídeo é longo demais (máximo {self.max_seconds // 60} minutos)."
            )
        size = info.get("filesize") or info.get("filesize_approx")
        if size and size > self.max_bytes:
            raise ExtractionError("too_large", "user_input", "O vídeo é maior que o limite permitido.")
        return VideoInfo(
            title=str(info.get("title") or "video")[:200],
            duration_seconds=float(duration) if duration else None,
            extractor=str(info.get("extractor_key") or info.get("extractor") or "generic")[:60],
            heights=[h for h in heights if h <= 2160],
            has_audio=has_audio,
            has_video=has_video,
            filesize_approx=int(size) if size else None,
        )

    def _ffprobe(self, media_url: str) -> dict:
        from app.security.sandbox import Limits, SandboxFailed, SandboxTimeout, run

        argv = ["ffprobe", "-v", "error", "-protocol_whitelist", "https,http,tls,tcp,httpproxy"]
        if self.proxy:
            argv += ["-http_proxy", self.proxy]
        argv += ["-show_entries", "format=duration:stream=codec_type,height", "-of", "json", media_url]
        try:
            data = json.loads(run(argv, cwd=Path("/tmp"), limits=Limits(timeout_seconds=45)))  # noqa: S108
        except (SandboxFailed, SandboxTimeout, json.JSONDecodeError):
            return {"duration": None, "heights": [], "has_video": False, "has_audio": False}
        streams = data.get("streams", [])
        try:
            duration = float(data.get("format", {}).get("duration") or 0) or None
        except ValueError:
            duration = None
        return {
            "duration": duration,
            "heights": sorted(
                {int(st["height"]) for st in streams if st.get("codec_type") == "video" and st.get("height")}
            ),
            "has_video": any(st.get("codec_type") == "video" for st in streams),
            "has_audio": any(st.get("codec_type") == "audio" for st in streams),
        }

    def download(self, url: str, output: str, quality: str, work_dir: Path, progress: Callable[[int], None]) -> Path:
        def hook(status: dict) -> None:
            if status.get("status") == "downloading":
                total = status.get("total_bytes") or status.get("total_bytes_estimate")
                if total:
                    progress(min(95, int(status.get("downloaded_bytes", 0) * 100 / total)))

        options = {
            **self._base_options(),
            "outtmpl": {"default": str(work_dir / "download.%(ext)s")},
            "paths": {"home": str(work_dir), "temp": str(work_dir)},
            "progress_hooks": [hook],
            "match_filter": lambda info, *, incomplete=False: (
                "too long" if (info.get("duration") or 0) > self.max_seconds else None
            ),
        }
        if output in AUDIO_OUTPUTS:
            options["format"] = "bestaudio/best"
            options["postprocessors"] = [
                {"key": "FFmpegExtractAudio", "preferredcodec": output, "preferredquality": "192"}
            ]
        else:
            cap = "" if quality == "best" else f"[height<={int(quality)}]"
            options["format"] = f"bv*{cap}+ba/b{cap}/bv*+ba/b"
            options["merge_output_format"] = "mp4"
            options["postprocessors"] = [{"key": "FFmpegVideoRemuxer", "preferedformat": "mp4"}]
        self._extract(url, options, download=True)
        produced = [p for p in work_dir.iterdir() if p.name.startswith("download.") and p.suffix == f".{output}"]
        if not produced:
            raise ExtractionError("no_output", "system", "O download não produziu o arquivo esperado.")
        return produced[0]


def default_extractor() -> YtDlpExtractor:
    return YtDlpExtractor(
        proxy=os.environ.get("EGRESS_PROXY_URL") or None,
        max_bytes=int(os.environ.get("DOWNLOAD_MAX_BYTES", str(300 * 1024 * 1024))),
        max_seconds=int(os.environ.get("DOWNLOAD_MAX_SECONDS", str(20 * 60))),
    )
