"""Test-only tool that validates the job + credits pipeline. Never registered in production."""

import time
from pathlib import Path

from app.core.errors import AppError
from app.tools.base import ToolHandler, ToolResult, ToolSystemError, ToolUserError

MAX_TEXT = 2000
SIMULATIONS = {"none", "user_error", "system_error", "slow"}


class EchoHandler(ToolHandler):
    tool_id = "echo"
    dev_only = True

    def validate_options(self, input_format: str, output_format: str, options: dict) -> dict:
        text = options.get("text")
        if not isinstance(text, str) or not text.strip():
            raise AppError("Informe um texto.", code="invalid_options")
        if len(text) > MAX_TEXT:
            raise AppError("Texto longo demais.", code="invalid_options")
        simulate = options.get("simulate", "none")
        if simulate not in SIMULATIONS:
            raise AppError("Simulação inválida.", code="invalid_options")
        return {"text": text, "simulate": simulate}

    def execute(self, options: dict, work_dir: Path) -> ToolResult:
        simulate = options["simulate"]
        if simulate == "user_error":
            raise ToolUserError("invalid_content", "Conteúdo inválido (simulado).")
        if simulate == "system_error":
            raise ToolSystemError("engine_crash")
        if simulate == "slow":
            time.sleep(5)
        output = work_dir / "echo.txt"
        output.write_text(options["text"], encoding="utf-8")
        return ToolResult(output_path=output, filename="eco.txt")
