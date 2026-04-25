from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers import health, papers, saved, search


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

    app.include_router(health.router, prefix="/api/v1")
    app.include_router(papers.router, prefix="/api/v1")
    app.include_router(search.router, prefix="/api/v1")
    app.include_router(saved.router, prefix="/api/v1")
    return app


app = create_app()
