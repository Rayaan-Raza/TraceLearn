from pathlib import Path
ROOT = Path(r"c:/Users/rayaan/Desktop/POC")

def w(rel, text):
    p = ROOT / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8", newline="\n")

w("backend/app/config.py", """
\"\"\"Application settings (pydantic-settings).\"\"\"
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=\".env\",
        env_file_encoding=\"utf-8\",
        extra=\"ignore\",
    )

    database_url: str = \"sqlite:///./tracelearn.db\"
    execution_mode: str = \"subprocess\"
    execution_timeout_seconds: int = 5
    evidence_weights_path: Path = Path(\"./config/evidence_weights.yaml\")
    cors_origins: list[str] = [\"http://localhost:3000\", \"http://127.0.0.1:3000\"]


settings = Settings()
""".strip() + "\n")

w("backend/app/db/database.py", """
\"\"\"SQLAlchemy engine and session factory.\"\"\"
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from backend.app.config import settings


class Base(DeclarativeBase):
    pass


connect_args = {}
if settings.database_url.startswith(\"sqlite\"):
    connect_args = {\"check_same_thread\": False}

engine = create_engine(settings.database_url, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from backend.app.db import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
""".strip() + "\n")

print("config+database ok")
