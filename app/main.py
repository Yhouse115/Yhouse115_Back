from fastapi import FastAPI

from app.api.routes.health import router as health_router
from app.core.config import settings
from app.utils.logging import configure_logging


def create_app() -> FastAPI:
    configure_logging(settings.log_level)

    application = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        docs_url="/docs",
        redoc_url="/redoc",
    )
    application.include_router(health_router)
    application.include_router(health_router, prefix=settings.api_prefix)
    return application


app = create_app()

