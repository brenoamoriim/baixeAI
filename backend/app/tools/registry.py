"""Maps tool ids to handlers. A capability is exposed only if it is `available` in the database
AND a handler is registered here (docs/architecture/07 §1)."""

from app.core.config import get_settings
from app.tools.ai.handlers import BackgroundRemoverHandler, ObjectRemoverHandler
from app.tools.base import ToolHandler
from app.tools.converter.handler import ConverterHandler
from app.tools.echo.handler import EchoHandler


def _build() -> dict[str, ToolHandler]:
    handlers: list[ToolHandler] = [
        EchoHandler(), ConverterHandler(), BackgroundRemoverHandler(), ObjectRemoverHandler(),
    ]
    production = get_settings().is_production
    return {h.tool_id: h for h in handlers if not (h.dev_only and production)}


_HANDLERS = _build()


def get_handler(tool_id: str) -> ToolHandler | None:
    return _HANDLERS.get(tool_id)


def registered_tool_ids() -> set[str]:
    return set(_HANDLERS)
