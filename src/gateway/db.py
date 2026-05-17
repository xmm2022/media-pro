from collections.abc import Generator

from fastapi import Request
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker


def make_engine(database_url: str):
    return create_engine(database_url, future=True)


def make_session_factory(database_url: str):
    engine = make_engine(database_url)
    return sessionmaker(bind=engine, class_=Session, expire_on_commit=False)


def get_session(request: Request) -> Generator[Session, None, None]:
    session = request.app.state.session_factory()
    try:
        yield session
    finally:
        session.close()
