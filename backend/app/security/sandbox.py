"""Run external engines (FFmpeg, LibreOffice, libvips, pdftotext) safely.

- argv list only, never a shell; arguments come from server-side templates
- minimal environment (no secrets inherited), stdin closed, private working directory
- wall-clock timeout + kernel limits (CPU seconds, address space, max file size, open files)
- whole process group killed on timeout (LibreOffice spawns children)

Container-level limits (memory, PIDs, no network, read-only root) are the outer layer.
"""

import os
import resource
import signal
import subprocess
from dataclasses import dataclass
from pathlib import Path

_SAFE_PATH = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
_MAX_CAPTURE = 64 * 1024


class SandboxTimeout(Exception):
    pass


class SandboxFailed(Exception):
    def __init__(self, returncode: int, stderr: str) -> None:
        super().__init__(f"exit {returncode}")
        self.returncode = returncode
        self.stderr = stderr


@dataclass(frozen=True)
class Limits:
    timeout_seconds: int = 60
    cpu_seconds: int = 120
    memory_bytes: int = 2 * 1024**3
    max_file_bytes: int = 1024**3
    max_open_files: int = 256


def _apply_limits(limits: Limits):
    def preexec() -> None:  # runs in the child, before exec
        os.setsid()  # own process group, so the whole tree can be killed
        resource.setrlimit(resource.RLIMIT_CPU, (limits.cpu_seconds, limits.cpu_seconds))
        resource.setrlimit(resource.RLIMIT_AS, (limits.memory_bytes, limits.memory_bytes))
        resource.setrlimit(resource.RLIMIT_FSIZE, (limits.max_file_bytes, limits.max_file_bytes))
        resource.setrlimit(resource.RLIMIT_NOFILE, (limits.max_open_files, limits.max_open_files))
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))

    return preexec


def run(argv: list[str], *, cwd: Path, limits: Limits, extra_env: dict[str, str] | None = None) -> str:
    """Run argv; return stdout (truncated). Raise SandboxTimeout / SandboxFailed."""
    if not argv or any(not isinstance(a, str) or "\x00" in a for a in argv):
        raise ValueError("invalid argv")
    env = {"PATH": _SAFE_PATH, "HOME": str(cwd), "TMPDIR": str(cwd), "LANG": "C.UTF-8"}
    env.update(extra_env or {})
    process = subprocess.Popen(  # noqa: S603 - argv list, no shell, server-built arguments
        argv,
        cwd=cwd,
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        preexec_fn=_apply_limits(limits),  # noqa: PLW1509 - single-threaded worker process
        close_fds=True,
    )
    try:
        stdout, stderr = process.communicate(timeout=limits.timeout_seconds)
    except subprocess.TimeoutExpired:
        _kill_group(process)
        raise SandboxTimeout(argv[0]) from None
    if process.returncode != 0:
        raise SandboxFailed(process.returncode, stderr[-_MAX_CAPTURE:].decode("utf-8", "replace"))
    return stdout[:_MAX_CAPTURE].decode("utf-8", "replace")


def _kill_group(process: subprocess.Popen) -> None:
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    process.communicate()
