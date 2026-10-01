from __future__ import annotations

import logging
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.config import Settings, get_settings
from app.db import create_database_engine, database_is_up
from app.db import create_sessionmaker
from app.routers import auth
from app.routers import audit, orgs
from app.routers import members
from app.routers import usage
from app.routers import budget
from app.routers import reports
from app.routers import diagnostics
from app.routers import kb
from app.routers import kb_logs
from app.routers import docgraph
from app.routers import jobs
from app.routers import market
from app.routers import market_approval
from app.services.report_store import ReportStore
from app.models.base import Base
import app.models  # noqa: F401

logger = logging.getLogger("worknexus.control_plane")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    logger.info("control plane started", extra={"version": app.state.version})
    yield
    app.state.engine.dispose()


def create_app(database_url: str | None = None, settings: Settings | None = None) -> FastAPI:
    app_settings = settings or get_settings()
    engine = create_database_engine(database_url or app_settings.database_url)
    if engine.url.drivername.startswith("sqlite"):
        Base.metadata.create_all(engine)

    app = FastAPI(title=app_settings.app_name, version=app_settings.version, lifespan=lifespan)
    app.state.settings = app_settings
    app.state.engine = engine
    app.state.version = app_settings.version
    app.state.SessionLocal = create_sessionmaker(engine)
    app.state.report_store = ReportStore()
    app.include_router(auth.router)
    app.include_router(orgs.router)
    app.include_router(members.router)
    app.include_router(usage.router)
    app.include_router(budget.router)
    app.include_router(reports.router)
    app.include_router(diagnostics.router)
    app.include_router(kb.router)
    app.include_router(kb_logs.router)
    app.include_router(docgraph.router)
    app.include_router(jobs.router)
    app.include_router(market.router)
    app.include_router(market_approval.router)
    app.include_router(audit.router)

    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        started = time.perf_counter()
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        logger.info(
            "request completed",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "duration_ms": duration_ms,
            },
        )
        return response

    @app.exception_handler(Exception)
    async def unhandled_error(_: Request, __: Exception) -> JSONResponse:
        return JSONResponse(status_code=500, content={"error": {"code": "internal_error", "message": "服务内部错误"}})

    @app.get("/api/v1/health")
    async def health() -> dict[str, str]:
        database = "up" if database_is_up(engine) else "down"
        return {
            "status": "ok" if database == "up" else "degraded",
            "database": database,
            "version": app_settings.version,
        }

    return app
