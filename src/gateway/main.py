from fastapi import FastAPI

from gateway.api.admin import router as admin_router
from gateway.api.health import router as health_router
from gateway.api.playback import router as playback_router
from gateway.config import settings
from gateway.db import make_session_factory
from gateway.security import CookieCipher


def create_app(database_url: str | None = None, cookie_secret: str | None = None) -> FastAPI:
    app = FastAPI(title=settings.app_name)
    app.state.session_factory = make_session_factory(database_url or settings.database_url)
    app.state.cookie_cipher = CookieCipher(cookie_secret or settings.cookie_secret)
    app.include_router(health_router)
    app.include_router(admin_router)
    app.include_router(playback_router)
    return app


app = create_app()
