"""worker-download side: fetch the media, verify what was produced, store it. No database."""

import logging
import shutil
import tempfile
from collections.abc import Callable
from pathlib import Path

from celery.exceptions import SoftTimeLimitExceeded

from app.security.file_sniffing import SniffError, sniff
from app.storage.base import get_storage, new_key
from app.tools.converter.handler import output_filename
from app.tools.downloader.extractor import ExtractionError, VideoExtractor, default_extractor

log = logging.getLogger(__name__)
_override: VideoExtractor | None = None  # tests inject a local-only extractor


def extractor_for(limits: dict) -> VideoExtractor:
    if _override is not None:
        return _override
    extractor = default_extractor()
    extractor.max_bytes = int(limits["max_bytes"])
    extractor.max_seconds = int(limits["max_seconds"])
    return extractor


def fetch(job_id: str, url: str, output: str, quality: str, limits: dict, name_hint: str,
          progress: Callable[[int], None]) -> dict:
    work = Path(tempfile.mkdtemp(prefix="dl-"))
    try:
        path = extractor_for(limits).download(url, output, quality, work, progress)
        if path.stat().st_size > int(limits["max_bytes"]):
            return {"ok": False, "error_class": "system", "error_code": "too_large"}
        try:
            real = sniff(path, output).format
        except SniffError:
            real = None
        if real != output:  # never hand out something other than what was promised
            log.warning("download format mismatch", extra={"expected": output, "got": real})
            return {"ok": False, "error_class": "system", "error_code": "unexpected_format"}
        key = new_key(f"jobs/{job_id.replace('-', '')}", output)
        get_storage().save_file(key, path)
        progress(100)
        return {"ok": True, "key": key, "filename": output_filename(name_hint, output)}
    except ExtractionError as exc:
        return {"ok": False, "error_class": exc.error_class, "error_code": exc.code}
    except (TimeoutError, SoftTimeLimitExceeded):
        return {"ok": False, "error_class": "timeout", "error_code": "time_limit"}
    except Exception:  # noqa: BLE001
        log.exception("download crashed")
        return {"ok": False, "error_class": "system", "error_code": "unexpected"}
    finally:
        shutil.rmtree(work, ignore_errors=True)
