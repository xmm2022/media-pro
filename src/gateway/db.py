from collections.abc import Generator
from fastapi import Request
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from gateway.models import Base


def make_engine(database_url: str) -> Engine:
    return create_engine(database_url, future=True)


def init_schema(engine: Engine) -> None:
    Base.metadata.create_all(engine)


def make_session_factory(engine: Engine):
    return sessionmaker(bind=engine, class_=Session, expire_on_commit=False)


def ensure_schema_initialized(request: Request) -> None:
    if getattr(request.app.state, "schema_initialized", False):
        return

    lock = getattr(request.app.state, "schema_init_lock", None)
    if lock is None:
        init_schema(request.app.state.engine)
        request.app.state.schema_initialized = True
        return

    with lock:
        if getattr(request.app.state, "schema_initialized", False):
            return
        init_schema(request.app.state.engine)
        request.app.state.schema_initialized = True


def get_session(request: Request) -> Generator[Session, None, None]:
    ensure_schema_initialized(request)
    session = request.app.state.session_factory()
    try:
        yield session
    finally:
        session.close()
