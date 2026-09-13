"""Conexão com o banco SQLite (SQLModel)."""
from __future__ import annotations

from sqlmodel import Session, SQLModel, create_engine

from app.config import SQLITE_URI

engine = create_engine(
    SQLITE_URI,
    connect_args={"check_same_thread": False},
    echo=False,
)


def init_db() -> None:
    from app import models  # noqa: F401  (registra tabelas)

    SQLModel.metadata.create_all(engine)


def get_session() -> Session:
    with Session(engine) as session:
        yield session