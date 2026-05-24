from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from threading import Lock

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse

from gateway.api.admin import router as admin_router
from gateway.api.admin_auth import (
    ADMIN_SESSION_COOKIE,
    admin_session_is_valid,
    router as admin_auth_router,
)
from gateway.api.admin_ui import router as admin_ui_router
from gateway.api.health import router as health_router
from gateway.api.playback import router as playback_router
from gateway.config import settings
from gateway.db import init_schema, make_engine, make_session_factory
from gateway.security import AdminSessionCipher, CookieCipher, PlaybackTokenCipher


def create_app(
    database_url: str | None = None,
    cookie_secret: str | None = None,
    admin_password: str | None = None,
) -> FastAPI:
    resolved_database_url = database_url or settings.database_url
    resolved_cookie_secret = cookie_secret or settings.cookie_secret
    resolved_admin_password = settings.admin_password if admin_password is None else admin_password

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
    app.state.cookie_cipher = CookieCipher(resolved_cookie_secret)
    app.state.playback_token_cipher = PlaybackTokenCipher(resolved_cookie_secret)
    app.state.admin_session_cipher = AdminSessionCipher(resolved_cookie_secret)
    app.state.admin_password = resolved_admin_password
    app.state.admin_session_ttl_seconds = settings.admin_session_ttl_seconds

    @app.middleware("http")
    async def require_admin_session(request: Request, call_next):
        if _admin_auth_is_required(request):
            token = request.cookies.get(ADMIN_SESSION_COOKIE)
            if not token or not admin_session_is_valid(request, token):
                if request.url.path == "/admin":
                    return RedirectResponse("/admin/login", status_code=303)
                return JSONResponse(
                    {"detail": "admin authentication required"},
                    status_code=401,
                )
        return await call_next(request)

    app.include_router(health_router)
    app.include_router(admin_auth_router)
    app.include_router(admin_ui_router)
    app.include_router(admin_router)
    app.include_router(playback_router)
    return app


def _admin_auth_is_required(request: Request) -> bool:
    if not getattr(request.app.state, "admin_password", ""):
        return False
    path = request.url.path
    if path in {"/admin/login", "/api/admin/login", "/api/admin/logout", "/api/admin/session"}:
        return False
    return path == "/admin" or path.startswith("/api/admin/")


app = create_app()
