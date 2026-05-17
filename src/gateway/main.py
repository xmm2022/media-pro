from fastapi import FastAPI

from gateway.api.admin import router as admin_router
from gateway.api.health import router as health_router


def create_app() -> FastAPI:
    app = FastAPI(title="GD Source-First Playback Gateway")
    app.state.admin_users = []
    app.state.admin_drives = []
    app.include_router(health_router)
    app.include_router(admin_router)
    return app


app = create_app()
