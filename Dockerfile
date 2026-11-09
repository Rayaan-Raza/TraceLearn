# TraceLearn backend image (Railway / any Linux container host).
#
# Runtime tools:
#   g++          compiles student C++ submissions
#   bubblewrap   isolates untrusted student code (needs user-namespace support;
#                the app logs at startup whether it actually works here)
#   util-linux   provides prlimit, used to cap CPU/memory/output per run
#   curl         for manual health checks over `railway ssh`
#
# Same OS and compiler as the training data (g++ 13.3 on Ubuntu 24.04). The execution model reads
# compiler warnings and runtime behaviour, and Debian's g++ 14 changed the features of 50 of 59 programs:
# Ubuntu turns on _FORTIFY_SOURCE and stack protection by default. Keep this in step with the machine
# that builds run records.
FROM ubuntu:24.04

RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 python3-pip python-is-python3 g++ bubblewrap util-linux curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --break-system-packages -r requirements.txt

# SERVE_FRONTEND=false, so frontend/ is intentionally not in the image.
COPY backend/ backend/
COPY tracelearn_features/ tracelearn_features/
COPY config/ config/
COPY data/ data/
COPY scripts/ scripts/
COPY sandbox_runner/ sandbox_runner/

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 8000

# Seed is idempotent (backend/app/db/seed.py skips when rows already exist), so
# this is safe on every boot. Schema is created by init_db() inside the app.
# All secrets/config come from the platform's environment variables.
CMD python scripts/seed_database.py && \
    exec uvicorn backend.app.main:app --host 0.0.0.0 --port "${PORT:-8000}" \
        --proxy-headers --forwarded-allow-ips "${FORWARDED_ALLOW_IPS:-127.0.0.1}"
