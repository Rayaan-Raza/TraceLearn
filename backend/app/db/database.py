"""SQLAlchemy engine and session factory."""
import logging
from collections.abc import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from backend.app.config import settings

log = logging.getLogger("tracelearn.db")


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
        "language_standard": "VARCHAR(8) NOT NULL DEFAULT 'cpp17'",
        "input_spec": "TEXT NOT NULL DEFAULT ''",
        "output_spec": "TEXT NOT NULL DEFAULT ''",
        "constraints": "TEXT NOT NULL DEFAULT ''",
    },
    "test_cases": {
        "time_limit_ms": "INTEGER",
        "memory_limit_mb": "INTEGER",
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


# Unique indexes added after the first release, for the same reason.
_ADDITIVE_UNIQUE_INDEXES: dict[str, tuple[str, str]] = {
    "uq_submission_attempt": ("submissions", "student_id, problem_id, attempt_number"),
}


def _migrate_unique_indexes() -> None:
    existing_tables = set(inspect(engine).get_table_names())
    for name, (table, cols) in _ADDITIVE_UNIQUE_INDEXES.items():
        if table not in existing_tables:
            continue
        try:
            with engine.begin() as conn:
                # Names come from the constant above, never from input.
                conn.execute(text(f"CREATE UNIQUE INDEX IF NOT EXISTS {name} ON {table} ({cols})"))
        except Exception as exc:  # older rows may already hold duplicates
            log.warning("Could not add unique index %s: %s", name, exc)


def init_db() -> None:
    from backend.app.db import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _migrate_additive_columns()
    _migrate_unique_indexes()
