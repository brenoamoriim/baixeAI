import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api.middleware import SecurityMiddleware
from app.api.v1 import admin, auth, downloads, jobs, me, payments, site, tools, uploads
from app.core.config import get_settings
from app.core.db import SessionLocal
from app.core.errors import AppError
from app.core.logging import configure_logging
from app.security.rate_limit import get_redis

configure_logging()
log = logging.getLogger("app")
settings = get_settings()

app = FastAPI(
    title="BaixeAI API",
    docs_url=None if settings.is_production else "/api/docs",
    redoc_url=None,
    openapi_url=None if settings.is_production else "/api/openapi.json",
)

app.add_middleware(SecurityMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.app_base_url],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-CSRF-Token", "Idempotency-Key"],
)


def _error(status: int, code: str, message: str, request: Request) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"error": {"code": code, "message": message,
                           "request_id": getattr(request.state, "request_id", None)}},
    )


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return _error(exc.status_code, exc.code, exc.message, request)


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    response = _error(422, "validation_error", "Dados inválidos.", request)
    if not settings.is_production:
        response = JSONResponse(
            status_code=422,
            content={"error": {"code": "validation_error", "message": "Dados inválidos.",
                               "details": [{k: v for k, v in e.items() if k in ("loc", "msg", "type")}
                                           for e in exc.errors()]}},
        )
    return response


@app.exception_handler(Exception)
async def unhandled_handler(request: Request, exc: Exception) -> JSONResponse:
    log.exception("unhandled error", extra={"request_id": getattr(request.state, "request_id", None)})
    return _error(500, "internal_error", "Erro interno. Tente novamente em instantes.", request)


@app.get("/healthz", include_in_schema=False)
def healthz() -> dict:
    return {"status": "ok"}


@app.get("/readyz", include_in_schema=False)
def readyz() -> JSONResponse:
    checks = {}
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception:
        checks["database"] = "fail"
    try:
        get_redis().ping()
        checks["redis"] = "ok"
    except Exception:
        checks["redis"] = "fail"
    ok = all(v == "ok" for v in checks.values())
    return JSONResponse(status_code=200 if ok else 503, content={"status": checks})


for router in (auth.router, me.router, tools.router, uploads.router, downloads.router, jobs.router, admin.router,
               downloads.admin_router, payments.router, site.router):
    app.include_router(router, prefix="/api/v1")
app.include_router(payments.webhook_router)
