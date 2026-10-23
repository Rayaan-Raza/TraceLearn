"""Application settings (pydantic-settings).

Every security-relevant knob lives here so it can be set from the environment
or a .env file. See .env.example for documented defaults.
"""
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

DEV_SECRET_PLACEHOLDER = "dev-secret-change-in-production"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- environment -------------------------------------------------------
    # "development" relaxes a few checks (docs on, insecure cookies allowed,
    # sandbox optional). "production" enforces all of them at startup.
    app_env: Literal["development", "production", "test"] = "development"

    # --- core --------------------------------------------------------------
    database_url: str = "sqlite:///./tracelearn.db"
    evidence_weights_path: Path = Path("./config/evidence_weights.yaml")

    # --- auth --------------------------------------------------------------
    # Read from TRACELEARN_SECRET for backwards compatibility with earlier
    # versions of this repo, or SECRET_KEY.
    secret_key: str = DEV_SECRET_PLACEHOLDER
    tracelearn_secret: str | None = None
    jwt_expire_minutes: int = 8 * 60
    jwt_issuer: str = "tracelearn"
    jwt_audience: str = "tracelearn-api"
    # Teachers can only self-register when this invite code is set and given.
    # Leave empty to disable teacher self-registration entirely (use
    # scripts/create_teacher.py instead).
    teacher_signup_code: str = ""

    # --- cookies (browser sessions) ---------------------------------------
    cookie_secure: bool | None = None  # None -> True in production
    cookie_samesite: Literal["lax", "strict", "none"] = "lax"
    cookie_domain: str | None = None

    # --- http --------------------------------------------------------------
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]
    enable_docs: bool | None = None  # None -> on in development only
    max_request_bytes: int = 256 * 1024
    # When true, the backend also serves the built frontend (frontend/dist)
    # from the same origin. This is the simplest secure deployment.
    serve_frontend: bool = False
    frontend_dist: Path = Path("./frontend/dist")

    # --- rate limits (per process, in-memory) -----------------------------
    rate_limit_enabled: bool = True
    login_attempts_per_minute: int = 10
    register_attempts_per_hour: int = 20
    join_attempts_per_minute: int = 10
    executions_per_minute: int = 12

    # --- demo / research endpoints ----------------------------------------
    # /api/demo/* mutate synthetic research data. Off unless explicitly on.
    enable_demo_endpoints: bool = False

    # --- code execution ----------------------------------------------------
    execution_mode: str = "sandboxed"
    execution_timeout_seconds: int = 5
    compile_timeout_seconds: int = 30
    # "auto": use bubblewrap if installed, otherwise fall back to resource
    # limits only (and log a warning). "bwrap": require bubblewrap.
    # "none": resource limits only (development on Windows/macOS).
    sandbox_mode: Literal["auto", "bwrap", "none"] = "auto"
    # When true, refuse to execute code without an OS-level sandbox.
    # Defaults to True in production.
    require_sandbox: bool | None = None
    max_source_bytes: int = 64 * 1024
    max_output_bytes: int = 64 * 1024
    max_memory_mb: int = 256
    max_concurrent_executions: int = 4

    # ---------------------------------------------------------------------
    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def jwt_secret(self) -> str:
        if self.secret_key and self.secret_key != DEV_SECRET_PLACEHOLDER:
            return self.secret_key
        return self.tracelearn_secret or self.secret_key

    @property
    def effective_cookie_secure(self) -> bool:
        return self.is_production if self.cookie_secure is None else self.cookie_secure

    @property
    def docs_enabled(self) -> bool:
        return (not self.is_production) if self.enable_docs is None else self.enable_docs

    @property
    def sandbox_required(self) -> bool:
        return self.is_production if self.require_sandbox is None else self.require_sandbox

    def validate_for_startup(self) -> list[str]:
        """Return a list of fatal misconfigurations (empty means OK)."""
        problems: list[str] = []
        if self.is_production:
            secret = self.jwt_secret
            if not secret or secret == DEV_SECRET_PLACEHOLDER or len(secret) < 32:
                problems.append("SECRET_KEY must be set to a random value of at least 32 characters in production.")
            if "*" in self.cors_origins:
                problems.append("CORS_ORIGINS must not contain '*' (credentials are used).")
            if self.cookie_samesite == "none" and not self.effective_cookie_secure:
                problems.append("COOKIE_SAMESITE=none requires COOKIE_SECURE=true.")
            if self.enable_demo_endpoints:
                problems.append("ENABLE_DEMO_ENDPOINTS must be false in production.")
            if self.teacher_signup_code and len(self.teacher_signup_code) < 12:
                problems.append("TEACHER_SIGNUP_CODE must be at least 12 characters if set.")
        return problems


settings = Settings()
