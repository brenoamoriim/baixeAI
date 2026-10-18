"""Document conversions: LibreOffice (headless, per-job profile, macros disabled) and pdftotext."""

from pathlib import Path

from app.security.sandbox import Limits, SandboxFailed, SandboxTimeout, run
from app.tools.base import ToolSystemError, ToolUserError

LIMITS = Limits(timeout_seconds=120, cpu_seconds=180, memory_bytes=3 * 1024**3, max_file_bytes=300 * 1024**2)

# Per-job user profile: macros never run, untrusted referer links blocked. The worker has no
# network access either, so external links/images in documents cannot be fetched.
_PROFILE = """<?xml version="1.0" encoding="UTF-8"?>
<oor:items xmlns:oor="http://openoffice.org/2001/registry" xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
<item oor:path="/org.openoffice.Office.Common/Security/Scripting"><prop oor:name="MacroSecurityLevel" oor:op="fuse"><value>3</value></prop></item>
<item oor:path="/org.openoffice.Office.Common/Security/Scripting"><prop oor:name="DisableMacrosExecution" oor:op="fuse"><value>true</value></prop></item>
<item oor:path="/org.openoffice.Office.Common/Security/Scripting"><prop oor:name="BlockUntrustedRefererLinks" oor:op="fuse"><value>true</value></prop></item>
<item oor:path="/org.openoffice.Office.Common/Misc"><prop oor:name="UseOpenCL" oor:op="fuse"><value>false</value></prop></item>
</oor:items>
"""

# (input, output) -> (input filter or None, output filter spec)
_LO = {
    ("docx", "pdf"): (None, "pdf:writer_pdf_Export"),
    ("doc", "pdf"): (None, "pdf:writer_pdf_Export"),
    ("odt", "pdf"): (None, "pdf:writer_pdf_Export"),
    ("rtf", "pdf"): (None, "pdf:writer_pdf_Export"),
    ("txt", "pdf"): ("Text (encoded):UTF8,LF,,,", "pdf:writer_pdf_Export"),
    ("html", "pdf"): ("HTML (StarWriter)", "pdf:writer_pdf_Export"),
    ("pdf", "docx"): ("writer_pdf_import", "docx:MS Word 2007 XML"),
    ("doc", "docx"): (None, "docx:MS Word 2007 XML"),
    ("xlsx", "csv"): (None, "csv:Text - txt - csv (StarCalc):44,34,76,1"),
    ("xls", "csv"): (None, "csv:Text - txt - csv (StarCalc):44,34,76,1"),
    ("csv", "xlsx"): ("CSV:44,34,76,1", "xlsx:Calc MS Excel 2007 XML"),
}


def _profile(work_dir: Path) -> str:
    user_dir = work_dir / "lo-profile" / "user"
    user_dir.mkdir(parents=True, exist_ok=True)
    (user_dir / "registrymodifications.xcu").write_text(_PROFILE, encoding="utf-8")
    return (work_dir / "lo-profile").as_uri()


def convert(input_path: Path, input_format: str, output_format: str, work_dir: Path) -> Path:
    if (input_format, output_format) == ("pdf", "txt"):
        return _pdftotext(input_path, work_dir)
    infilter, outfilter = _LO[(input_format, output_format)]
    out_dir = work_dir / "out"
    out_dir.mkdir()
    argv = [
        "soffice",
        f"-env:UserInstallation={_profile(work_dir)}",
        "--headless", "--norestore", "--nologo", "--nodefault", "--nolockcheck", "--nofirststartwizard",
    ]
    if infilter:
        argv.append(f"--infilter={infilter}")
    argv += ["--convert-to", outfilter, "--outdir", str(out_dir), str(input_path)]
    try:
        run(argv, cwd=work_dir, limits=LIMITS)
    except SandboxTimeout:
        raise TimeoutError from None
    except SandboxFailed as exc:
        raise ToolSystemError("libreoffice_failed") from exc
    produced = list(out_dir.glob(f"*.{output_format}"))
    if len(produced) != 1 or produced[0].stat().st_size == 0:
        # LibreOffice exits 0 but writes nothing when it cannot read the document.
        raise ToolUserError("unreadable_document", "Não foi possível ler este documento (corrompido ou protegido).")
    return produced[0]


def _pdftotext(input_path: Path, work_dir: Path) -> Path:
    output = work_dir / "output.txt"
    try:
        run(["pdftotext", "-enc", "UTF-8", "-eol", "unix", str(input_path), str(output)],
            cwd=work_dir, limits=LIMITS)
    except SandboxTimeout:
        raise TimeoutError from None
    except SandboxFailed as exc:
        # poppler exit codes 1-3: unreadable/encrypted/permission -> the input's fault
        if exc.returncode in (1, 2, 3):
            raise ToolUserError("unreadable_pdf", "Não foi possível ler este PDF (corrompido ou protegido).") from exc
        raise ToolSystemError("pdftotext_failed") from exc
    return output


def page_count(input_path: Path, work_dir: Path) -> int:
    """Used by the probe step (before charging)."""
    try:
        info = run(["pdfinfo", str(input_path)], cwd=work_dir, limits=Limits(timeout_seconds=20))
    except (SandboxFailed, SandboxTimeout):
        raise ToolUserError("unreadable_pdf", "Não foi possível ler este PDF (corrompido ou protegido).") from None
    for line in info.splitlines():
        if line.startswith("Pages:"):
            return int(line.split(":", 1)[1].strip())
    raise ToolUserError("unreadable_pdf", "Não foi possível ler este PDF.")
