from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.demo import router as demo_router
from app.api.routes.environment import router as environment_router
from app.api.routes.family_map import router as family_map_router
from app.api.routes.health import router as health_router
from app.api.routes.system import router as system_router
from app.api.routes.transaction import router as transaction_router
from app.api.routes.walking_route import router as walking_route_router
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
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    application.include_router(demo_router)
    application.include_router(health_router)
    application.include_router(health_router, prefix=settings.api_prefix)
    application.include_router(system_router, prefix=settings.api_prefix)
    application.include_router(family_map_router, prefix=settings.api_prefix)
    application.include_router(transaction_router)
    application.include_router(transaction_router, prefix=settings.api_prefix)
    application.include_router(environment_router, prefix=settings.api_prefix)
    application.include_router(walking_route_router, prefix=settings.api_prefix)
    return application


app = create_app()
