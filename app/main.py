from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.family_map import router as family_map_router
from app.api.routes.health import router as health_router
from app.api.routes.system import router as system_router
from app.api.routes.transaction import router as transaction_router
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
        allow_origins=settings.parsed_cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    @application.get("/demo")
    async def get_demo_dashboard():
        from fastapi.responses import HTMLResponse
        import os
        me_html_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".me", "api_test_dashboard.html"))
        if os.path.exists(me_html_path):
            with open(me_html_path, "r", encoding="utf-8") as f:
                return HTMLResponse(content=f.read())
        return HTMLResponse(content="<h1>Debugging dashboard HTML not found</h1>", status_code=404)

    application.include_router(health_router)
    application.include_router(health_router, prefix=settings.api_prefix)
    application.include_router(system_router, prefix=settings.api_prefix)
    application.include_router(family_map_router, prefix=settings.api_prefix)
    application.include_router(transaction_router)
    application.include_router(transaction_router, prefix=settings.api_prefix)
    return application


app = create_app()
