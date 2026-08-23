"""Application settings (pydantic-settings)."""
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "sqlite:///./tracelearn.db"
    execution_mode: str = "subprocess"  # trusted synthetic/demo only; not a secure sandbox
    execution_timeout_seconds: int = 5
    evidence_weights_path: Path = Path("./config/evidence_weights.yaml")
    cors_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:5173", "http://127.0.0.1:5173"]


settings = Settings()
