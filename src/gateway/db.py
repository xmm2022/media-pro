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


def get_session(request: Request) -> Generator[Session, None, None]:
    session = request.app.state.session_factory()
    try:
        yield session
    finally:
        session.close()
