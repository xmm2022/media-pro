"""Database primitives kept available for later tasks.

Task 4 admin APIs remain intentionally in-memory; persistence wiring is deferred.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from gateway.models import Base

DATABASE_URL = "sqlite:///./gateway.db"

engine = create_engine(DATABASE_URL, future=True)
SessionLocal = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
