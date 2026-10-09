"""Engine, SessionLocal, Base và kiểu cột dùng chung cho ORM model của mọi module."""

from collections.abc import Generator
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import JSON, BigInteger, Integer, Text, create_engine, event
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.shared.config import settings

JSONType = JSON().with_variant(JSONB(), "postgresql")
BigIntPK = BigInteger().with_variant(Integer(), "sqlite")
# TSVECTOR trên PostgreSQL; SQLite (test) lưu text đã chuẩn hóa
SearchVectorType = TSVECTOR().with_variant(Text(), "sqlite")


def utcnow() -> datetime:
    return datetime.now(UTC)


def aware(dt: datetime | None) -> datetime | None:
    """SQLite trả datetime không có tzinfo; mọi giá trị được lưu theo UTC."""
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


def str_enum(enum_cls: type[StrEnum], name: str) -> SAEnum:
    """Enum lưu VARCHAR + CHECK (dễ migrate hơn ENUM gốc của PostgreSQL)."""
    return SAEnum(
        enum_cls,
        name=name,
        native_enum=False,
        create_constraint=True,
        length=30,
        values_callable=lambda e: [m.value for m in e],
        validate_strings=True,
    )


def make_engine(url: str) -> Engine:
    if url.startswith("sqlite"):
        eng = create_engine(url, connect_args={"check_same_thread": False})

        @event.listens_for(eng, "connect")
        def _sqlite_connect(dbapi_conn: Any, _: Any) -> None:
            dbapi_conn.execute("PRAGMA foreign_keys=ON")
            dbapi_conn.execute("PRAGMA journal_mode=WAL")  # đọc không chặn ghi
            dbapi_conn.isolation_level = None  # để SAVEPOINT hoạt động với pysqlite

        @event.listens_for(eng, "begin")
        def _sqlite_begin(conn: Any) -> None:
            conn.exec_driver_sql("BEGIN")

        return eng
    return create_engine(url, pool_pre_ping=True)


engine = make_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    with SessionLocal() as db:
        yield db


def is_postgres(db: Session) -> bool:
    return db.get_bind().dialect.name == "postgresql"
