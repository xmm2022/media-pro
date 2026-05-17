from fastapi import FastAPI

from gateway.api.health import router as health_router


def create_app() -> FastAPI:
    app = FastAPI(title="GD Source-First Playback Gateway")
    app.include_router(health_router)
    return app


app = create_app()
