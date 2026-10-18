"""Audio/video conversions with FFmpeg. Arguments are built only from server-side templates and
closed option lists. The input demuxer is forced from the sniffed format and only the `file`
protocol is allowed, so playlists/concat tricks cannot pull other files or URLs."""

import json
from pathlib import Path

from app.security.sandbox import Limits, SandboxFailed, SandboxTimeout, run
from app.tools.base import ToolSystemError, ToolUserError

LIMITS = Limits(timeout_seconds=900, cpu_seconds=1800, memory_bytes=3 * 1024**3, max_file_bytes=1024**3)
PROBE_LIMITS = Limits(timeout_seconds=30, cpu_seconds=30, memory_bytes=1024**3)

DEMUXER = {"mp4": "mov", "mov": "mov", "m4a": "mov", "webm": "matroska", "mkv": "matroska",
           "avi": "avi", "mp3": "mp3", "wav": "wav", "ogg": "ogg", "opus": "ogg", "flac": "flac",
           "gif": "gif"}  # gif: only used to check our own video->gif output
MUXER = {"mp4": "mp4", "webm": "webm", "mkv": "matroska", "mov": "mov", "avi": "avi", "mp3": "mp3",
         "wav": "wav", "ogg": "ogg", "m4a": "ipod", "flac": "flac", "opus": "opus", "gif": "gif"}
AUDIO_CODEC = {"mp3": "libmp3lame", "wav": "pcm_s16le", "ogg": "libvorbis", "m4a": "aac",
               "flac": "flac", "opus": "libopus"}
LOSSLESS = {"wav", "flac"}

AUDIO_BITRATES = ("64k", "96k", "128k", "192k", "256k", "320k")
SAMPLE_RATES = ("original", "22050", "44100", "48000")
CHANNELS = ("original", "1", "2")
RESOLUTIONS = ("original", "360", "480", "720", "1080")
QUALITIES = ("alta", "media", "baixa")
FPS = ("original", "24", "30")

_X264_CRF = {"alta": "20", "media": "23", "baixa": "28"}
_VP9_CRF = {"alta": "30", "media": "34", "baixa": "40"}
_MPEG4_Q = {"alta": "3", "media": "5", "baixa": "8"}

_BASE = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-threads", "2",
         "-protocol_whitelist", "file"]


def probe(path: Path, sniffed_format: str, work_dir: Path) -> dict:
    """Facts about the media, read before charging. Raises ToolUserError for unusable files."""
    argv = ["ffprobe", "-v", "error", "-protocol_whitelist", "file", "-f", DEMUXER[sniffed_format],
            "-print_format", "json", "-show_format", "-show_streams", str(path)]
    try:
        data = json.loads(run(argv, cwd=work_dir, limits=PROBE_LIMITS))
    except (SandboxFailed, SandboxTimeout, json.JSONDecodeError):
        raise ToolUserError("unreadable_media", "Não foi possível ler este arquivo de áudio/vídeo.") from None
    streams = data.get("streams", [])
    video = next((s for s in streams if s.get("codec_type") == "video"
                  and not s.get("disposition", {}).get("attached_pic")), None)
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
    try:
        duration = float(data.get("format", {}).get("duration") or 0)
    except ValueError:
        duration = 0.0
    if video is None and audio is None:
        raise ToolUserError("no_media_streams", "O arquivo não contém áudio nem vídeo.")
    if duration <= 0:
        raise ToolUserError("unknown_duration", "Não foi possível determinar a duração do arquivo.")
    fmt = sniffed_format
    if fmt == "mp4" and video is None:
        fmt = "m4a"  # MP4 container with audio only
    if fmt in ("ogg", "opus") and audio is not None:
        fmt = "opus" if audio.get("codec_name") == "opus" else "ogg"
    return {
        "format": fmt,
        "duration_seconds": round(duration, 3),
        "has_video": video is not None,
        "has_audio": audio is not None,
        "width": int(video.get("width", 0)) if video else 0,
        "height": int(video.get("height", 0)) if video else 0,
        "audio_channels": int(audio.get("channels", 0)) if audio else 0,
    }


def _audio_args(output_format: str, options: dict, meta: dict) -> list[str]:
    args = ["-c:a", AUDIO_CODEC[output_format]]
    if output_format not in LOSSLESS:
        args += ["-b:a", options.get("bitrate", "192k")]
    if output_format == "opus":
        args += ["-ar", "48000"]  # libopus does not accept 44.1 kHz
    elif options.get("sample_rate", "original") != "original":
        args += ["-ar", options["sample_rate"]]
    channels = options.get("channels", "original")
    if channels != "original":
        args += ["-ac", channels]
    elif meta.get("audio_channels", 0) > 2:
        args += ["-ac", "2"]
    return args


def _video_filters(options: dict, meta: dict) -> str:
    filters = []
    target = options.get("resolution", "original")
    if target != "original" and int(target) < meta.get("height", 0):
        filters.append(f"scale=-2:{int(target)}")
    else:
        filters.append("scale=trunc(iw/2)*2:trunc(ih/2)*2")
    fps = options.get("fps", "original")
    if fps != "original":
        filters.append(f"fps={int(fps)}")
    return ",".join(filters)


def _video_codec_args(output_format: str, quality: str) -> list[str]:
    if output_format == "webm":
        return ["-c:v", "libvpx-vp9", "-crf", _VP9_CRF[quality], "-b:v", "0", "-deadline", "realtime",
                "-cpu-used", "8", "-row-mt", "1", "-c:a", "libopus", "-b:a", "128k", "-ar", "48000"]
    if output_format == "avi":
        return ["-c:v", "mpeg4", "-q:v", _MPEG4_Q[quality], "-c:a", "libmp3lame", "-b:a", "192k"]
    return ["-c:v", "libx264", "-preset", "veryfast", "-crf", _X264_CRF[quality], "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "160k"]


def convert(input_path: Path, input_format: str, output_format: str, options: dict, meta: dict,
            work_dir: Path) -> Path:
    output = work_dir / f"output.{output_format}"
    argv = [*_BASE, "-f", DEMUXER[input_format], "-i", str(input_path)]

    if output_format in AUDIO_CODEC:  # audio -> audio, or extract audio from video
        if not meta.get("has_audio"):
            raise ToolUserError("no_audio", "O arquivo não tem faixa de áudio.")
        argv += ["-map", "0:a:0", "-vn", *_audio_args(output_format, options, meta)]
    elif output_format == "gif":
        argv += ["-t", "15", "-an", "-vf",
                 "fps=10,scale='min(480,iw)':-2:flags=lanczos,split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse",
                 "-loop", "0"]
    else:
        if not meta.get("has_video"):
            raise ToolUserError("no_video", "O arquivo não tem faixa de vídeo.")
        argv += ["-map", "0:v:0", "-map", "0:a:0?", "-vf", _video_filters(options, meta),
                 *_video_codec_args(output_format, options.get("quality", "media"))]
        if output_format in ("mp4", "mov"):
            argv += ["-movflags", "+faststart"]
    argv += ["-map_metadata", "-1", "-f", MUXER[output_format], "-y", str(output)]

    try:
        run(argv, cwd=work_dir, limits=LIMITS)
    except SandboxTimeout:
        raise TimeoutError from None
    except SandboxFailed as exc:
        if "Invalid data found" in exc.stderr or "could not find codec" in exc.stderr.lower():
            raise ToolUserError("unreadable_media", "O arquivo de mídia está corrompido ou é inválido.") from exc
        raise ToolSystemError("ffmpeg_failed") from exc
    if not output.exists() or output.stat().st_size == 0:
        raise ToolSystemError("ffmpeg_no_output")
    return output
