import logging
import traceback

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.routers import health, papers, saved, search

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Veros API", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Catch-all so unhandled exceptions still return through CORS middleware —
    # otherwise the browser shows a misleading CORS error in place of the real
    # 500. Logs the traceback so we still see the cause.
    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.error(
            "Unhandled error on %s %s\n%s",
            request.method,
            request.url.path,
            "".join(traceback.format_exception(exc)),
        )
        return JSONResponse(
            status_code=500,
            content={"detail": f"{type(exc).__name__}: {exc}"},
        )

    app.include_router(health.router, prefix="/api/v1")
    app.include_router(papers.router, prefix="/api/v1")
    app.include_router(search.router, prefix="/api/v1")
    app.include_router(saved.router, prefix="/api/v1")
    return app


app = create_app()
