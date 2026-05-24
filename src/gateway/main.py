from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from threading import Lock

from fastapi import FastAPI

from gateway.api.admin import router as admin_router
from gateway.api.admin_ui import router as admin_ui_router
from gateway.api.health import router as health_router
from gateway.api.playback import router as playback_router
from gateway.config import settings
from gateway.db import init_schema, make_engine, make_session_factory
from gateway.security import CookieCipher, PlaybackTokenCipher


def create_app(database_url: str | None = None, cookie_secret: str | None = None) -> FastAPI:
    resolved_database_url = database_url or settings.database_url

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        init_schema(app.state.engine)
        app.state.schema_initialized = True
        yield
        app.state.engine.dispose()

    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    app.state.engine = make_engine(resolved_database_url)
    app.state.session_factory = make_session_factory(app.state.engine)
    app.state.schema_initialized = False
    app.state.schema_init_lock = Lock()
    app.state.cookie_cipher = CookieCipher(cookie_secret or settings.cookie_secret)
    app.state.playback_token_cipher = PlaybackTokenCipher(cookie_secret or settings.cookie_secret)
    app.include_router(health_router)
    app.include_router(admin_ui_router)
    app.include_router(admin_router)
    app.include_router(playback_router)
    return app


app = create_app()
