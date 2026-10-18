"""Run inside worker-download:  docker compose run --rm worker-download env TESTS_NO_DB=1 pytest tests/engines/test_downloader.py

Real yt-dlp against a local HTTP fixture server (no internet needed), plus network isolation checks
of the container itself. Skipped elsewhere with the reason shown.
"""

import os
import shutil
import socket
import subprocess
import threading
import urllib.error
import urllib.request
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from app.tools.downloader import worker
from app.tools.downloader.extractor import ExtractionError, YtDlpExtractor, classify

try:
    import yt_dlp  # noqa: F401

    HAS_YTDLP = shutil.which("ffmpeg") is not None
except ImportError:
    HAS_YTDLP = False
download_only = pytest.mark.skipif(not HAS_YTDLP, reason="run inside worker-download (yt-dlp/ffmpeg missing here)")
in_container = pytest.mark.skipif(not os.environ.get("EGRESS_PROXY_URL"), reason="network checks run inside worker-download")


@pytest.fixture(scope="module")
def fixture_server(tmp_path_factory):
    root = tmp_path_factory.mktemp("site")
    subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=duration=3:size=320x240:rate=25",
                    "-f", "lavfi", "-i", "sine=duration=3", "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-y", str(root / "clip.mp4")], check=True)
    (root / "page.html").write_text("<html><body><p>sem video</p></body></html>")
    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(SimpleHTTPRequestHandler, directory=str(root)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


def _local(max_bytes=50 * 1024 * 1024, max_seconds=600) -> YtDlpExtractor:
    return YtDlpExtractor(proxy=None, max_bytes=max_bytes, max_seconds=max_seconds)  # local fixture only


@download_only
def test_inspect_reports_real_options(fixture_server):
    info = _local().inspect(f"{fixture_server}/clip.mp4")
    assert info.has_video and info.has_audio
    assert info.duration_seconds and 2.5 < info.duration_seconds < 3.5


@download_only
@pytest.mark.parametrize("output", ["mp4", "m4a", "mp3"])
def test_download_produces_the_promised_format(fixture_server, tmp_path, output):
    progress = []
    path = _local().download(f"{fixture_server}/clip.mp4", output, "best" if output == "mp4" else "audio",
                             tmp_path, progress.append)
    from app.security.file_sniffing import sniff

    assert sniff(path, output).format == output


@download_only
def test_missing_video_is_classified(fixture_server):
    with pytest.raises(ExtractionError) as exc:
        _local().inspect(f"{fixture_server}/nao-existe.mp4")
    assert exc.value.code in ("unavailable", "unsupported_site")


@download_only
def test_page_without_video_is_unsupported(fixture_server):
    with pytest.raises(ExtractionError) as exc:
        _local().inspect(f"{fixture_server}/page.html")
    assert exc.value.code == "unsupported_site" and exc.value.error_class == "user_input"


@download_only
def test_duration_limit_enforced_before_download(fixture_server):
    with pytest.raises(ExtractionError) as exc:
        _local(max_seconds=1).inspect(f"{fixture_server}/clip.mp4")
    assert exc.value.code == "too_long"


@download_only
def test_size_limit_enforced(fixture_server, tmp_path):
    with pytest.raises(ExtractionError):
        info = _local(max_bytes=1000).inspect(f"{fixture_server}/clip.mp4")
        _local(max_bytes=1000).download(f"{fixture_server}/clip.mp4", "mp4", "best", tmp_path, lambda v: None)
        assert info


def test_fetch_refuses_output_that_is_not_the_promised_format(monkeypatch, tmp_path):
    class Liar:
        def download(self, url, output, quality, work_dir, progress):
            fake = work_dir / f"download.{output}"
            fake.write_text("<html>not a video</html>")
            return fake

    monkeypatch.setattr(worker, "_override", Liar())
    result = worker.fetch("job-1", "https://x", "mp4", "best", {"max_bytes": 10**6, "max_seconds": 60}, "a.x",
                          progress=lambda v: None)
    assert result == {"ok": False, "error_class": "system", "error_code": "unexpected_format"}


@pytest.mark.parametrize("message,code,error_class", [
    ("ERROR: Unsupported URL: https://x", "unsupported_site", "user_input"),
    ("ERROR: [youtube] abc: Private video. Sign in", "private_content", "user_input"),
    ("ERROR: Sign in to confirm you're not a bot", "login_required", "user_input"),
    ("ERROR: This video is DRM protected", "drm_protected", "user_input"),
    ("ERROR: Video unavailable", "unavailable", "user_input"),
    ("ERROR: HTTP Error 429: Too Many Requests", "blocked_by_platform", "system"),
    ("Tunnel connection failed: 403 Blocked By Egress Policy", "blocked_destination", "user_input"),
    ("ERROR: something new and weird", "extractor_failed", "system"),
])
def test_error_classification(message, code, error_class):
    err = classify(message)
    assert (err.code, err.error_class) == (code, error_class)


# ---------------------------------------------------------------- container network isolation


def _tcp(host: str, port: int) -> bool:
    try:
        socket.create_connection((host, port), timeout=4).close()
        return True
    except OSError:
        return False


@in_container
def test_worker_download_cannot_reach_database_or_internet_directly():
    assert not _tcp("db", 5432), "worker-download must not reach Postgres"
    assert not _tcp("1.1.1.1", 443), "worker-download must not have a direct internet route"
    assert not _tcp("169.254.169.254", 80), "cloud metadata must be unreachable"
    assert _tcp("redis", 6379), "the broker is required"


@in_container
@pytest.mark.parametrize("url", ["http://169.254.169.254/latest/meta-data/", "http://db:5432/", "http://redis:6379/",
                                 "http://127.0.0.1/", "http://[::1]/"])
def test_egress_proxy_refuses_internal_targets(url):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({"http": os.environ["EGRESS_PROXY_URL"]}))
    with pytest.raises(urllib.error.HTTPError) as exc:
        opener.open(url, timeout=15)
    assert exc.value.code == 403


@in_container
def test_no_secrets_in_worker_download_environment():
    # conftest injects test variables into os.environ; the process' ORIGINAL environment is what matters
    original = Path("/proc/self/environ").read_bytes().split(b"\0")
    names = {item.split(b"=", 1)[0].decode() for item in original if item}
    assert "DATABASE_URL" not in names and "SECRET_KEY" not in names and "TEST_DATABASE_URL" not in names
