from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

from api.middleware import (
    PersistentRateLimitMiddleware,
    RequestLoggingMiddleware,
    RequestSizeLimitMiddleware,
    SecurityHeadersMiddleware,
)
from api.routes import router
from api.admin_routes import router as admin_router
from api.analytics_routes import router as analytics_router
from app.logging_config import configure_logging
from config.settings import get_settings
from services.ai_service import AIService
from services.command_service import CommandService
from services.intent_service import IntentService
from services.quality_service import QualityService
from services.web_search_service import WebSearchService
from storage.memory_store import MemoryStore
from storage.rate_limit_store import RateLimitStore
from storage.analytics_store import AnalyticsStore

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / 'static'
STATIC_ASSETS_DIR = STATIC_DIR / 'assets'
STATIC_INDEX = STATIC_DIR / 'index.html'


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(title=settings.app_name, version='1.1.0')
    app.state.settings = settings
    app.state.quality_service = QualityService()
    app.state.intent_service = IntentService()
    app.state.memory_store = MemoryStore(settings.memory_path)
    app.state.rate_limit_store = RateLimitStore(settings.rate_limit_path)
    app.state.analytics_store = AnalyticsStore(settings.analytics_path)
    app.state.ai_service = AIService(settings, app.state.quality_service, app.state.intent_service)
    app.state.web_search_service = WebSearchService()
    app.state.command_service = CommandService(app.state.memory_store)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins if settings.app_env != 'prod' else [],
        allow_credentials=True,
        allow_methods=['GET', 'POST', 'OPTIONS'],
        allow_headers=['Content-Type', 'Authorization'],
    )
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts or ['*'])
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(
        PersistentRateLimitMiddleware,
        store=app.state.rate_limit_store,
        limit_per_minute=settings.rate_limit_per_minute,
        trusted_proxies=settings.trusted_proxies,
    )
    app.add_middleware(RequestSizeLimitMiddleware, max_bytes=settings.max_request_bytes)
    app.add_middleware(SecurityHeadersMiddleware)
    app.include_router(router)
    app.include_router(admin_router)
    app.include_router(analytics_router)

    if STATIC_ASSETS_DIR.exists() and STATIC_INDEX.exists():
        app.mount('/assets', StaticFiles(directory=STATIC_ASSETS_DIR), name='assets')

        @app.get('/')
        def index():
            return FileResponse(STATIC_INDEX)

        @app.get('/{full_path:path}', include_in_schema=False)
        def spa_fallback(full_path: str):
            blocked_prefixes = ('chat', 'command', 'health', 'docs', 'openapi.json', 'admin', 'analytics')
            if any(full_path.startswith(prefix) for prefix in blocked_prefixes):
                return FileResponse(STATIC_INDEX)
            return FileResponse(STATIC_INDEX)

    return app


app = create_app()
