"""Tool handler interface. New tools plug in here without touching auth/credits/payments."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class ToolUserError(Exception):
    """The input turned out to be invalid during processing (no refund, PRD §2)."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class ToolSystemError(Exception):
    """Our failure (engine crash, storage, ...). The credit is returned."""

    def __init__(self, code: str, message: str = "Falha interna no processamento.") -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass
class ToolResult:
    output_path: Path
    filename: str


class ToolHandler(ABC):
    tool_id: str
    dev_only: bool = False

    @abstractmethod
    def validate_options(self, input_format: str, output_format: str, options: dict) -> dict:
        """Validate before any charge. Raise AppError (422) on invalid input."""

    def metadata(self, options: dict) -> dict[str, Any]:
        """Facts used for pricing (e.g. duration). Must come from the server, not the client."""
        return {}

    @abstractmethod
    def execute(self, options: dict, work_dir: Path) -> ToolResult:
        """Run the operation inside `work_dir`. Raise ToolUserError/ToolSystemError on failure."""
