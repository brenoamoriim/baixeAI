from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db
from app.models import ToolCapability, ToolDefinition
from app.tools.registry import get_handler, registered_tool_ids

router = APIRouter(prefix="/tools", tags=["tools"])


@router.get("")
def list_tools(db: Session = Depends(get_db)) -> dict:
    """Only `available` capabilities with a registered handler are exposed."""
    production = get_settings().is_production
    registered = registered_tool_ids()
    tools = db.execute(
        select(ToolDefinition).where(ToolDefinition.enabled.is_(True)).order_by(
            ToolDefinition.sort_order
        )
    ).scalars().all()
    result = []
    for tool in tools:
        if tool.dev_only and production:
            continue
        caps = []
        if tool.id in registered:
            caps = db.execute(
                select(ToolCapability).where(
                    ToolCapability.tool_id == tool.id, ToolCapability.status == "available"
                )
            ).scalars().all()
        result.append(
            {
                "id": tool.id,
                "name": tool.display_name,
                "base_cost": tool.credit_cost,
                "status": "available" if caps else "coming_soon",
                "capabilities": [
                    {"category": c.category, "input": c.input_format, "output": c.output_format,
                     "note": c.notes}
                    for c in caps
                ],
                **({"info": get_handler(tool.id).public_info(db)} if caps else {}),
            }
        )
    return {"tools": result}
