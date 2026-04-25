from collections.abc import Iterator

from sqlalchemy.engine import Engine
from sqlmodel import Session, create_engine

from app.config import get_settings

_engine: Engine | None = None


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = create_engine(
            get_settings().database_url,
            pool_pre_ping=True,
            future=True,
        )
    return _engine


def get_db() -> Iterator[Session]:
    with Session(get_engine()) as session:
        yield session
