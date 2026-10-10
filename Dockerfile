# TraceLearn backend image (Railway / any Linux container host).
#
# Runtime tools:
#   g++          compiles student C++ submissions
#   bubblewrap   isolates untrusted student code (needs user-namespace support;
#                the app logs at startup whether it actually works here)
#   util-linux   provides prlimit, used to cap CPU/memory/output per run
#   curl         for manual health checks over `railway ssh`
FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends g++ bubblewrap util-linux curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# SERVE_FRONTEND=false, so frontend/ is intentionally not in the image.
COPY backend/ backend/
COPY config/ config/
COPY data/ data/
COPY scripts/ scripts/

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 8000

# Seed is idempotent (backend/app/db/seed.py skips when rows already exist), so
# this is safe on every boot. Schema is created by init_db() inside the app.
# All secrets/config come from the platform's environment variables.
CMD python scripts/seed_database.py && \
    exec uvicorn backend.app.main:app --host 0.0.0.0 --port "${PORT:-8000}" \
        --proxy-headers --forwarded-allow-ips "${FORWARDED_ALLOW_IPS:-127.0.0.1}"
