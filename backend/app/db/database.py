"""SQLAlchemy engine and session factory."""
from collections.abc import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from backend.app.config import settings


class Base(DeclarativeBase):
    pass


connect_args = {}
if settings.database_url.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(settings.database_url, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Columns added after the first release. create_all() does not alter existing
# tables, so add them in place for databases created by older versions.
_ADDITIVE_COLUMNS: dict[str, dict[str, str]] = {
    "users": {
        "display_name": "VARCHAR(128) NOT NULL DEFAULT ''",
        "token_version": "INTEGER NOT NULL DEFAULT 0",
    },
    "problems": {
        "language": "VARCHAR(16) NOT NULL DEFAULT 'python'",
        "topic": "VARCHAR(64) NOT NULL DEFAULT ''",
        "difficulty": "VARCHAR(16) NOT NULL DEFAULT 'Easy'",
        "created_by_user_id": "INTEGER REFERENCES users(id)",
    },
}


def _migrate_additive_columns() -> None:
    insp = inspect(engine)
    existing_tables = set(insp.get_table_names())
    with engine.begin() as conn:
        for table, cols in _ADDITIVE_COLUMNS.items():
            if table not in existing_tables:
                continue
            present = {c["name"] for c in insp.get_columns(table)}
            for name, ddl in cols.items():
                if name not in present:
                    # Table/column names come from the constant above, never from input.
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))


def init_db() -> None:
    from backend.app.db import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _migrate_additive_columns()
