# syntax=docker/dockerfile:1.7
#
# Multi-stage Dockerfile for the SRE Agent dashboard.
#
# Stage 1: deps — install Python deps (cached unless pyproject.toml changes)
# Stage 2: runtime — copy source, run gunicorn
#
# Build:  docker build -t sre-agent:latest .
# Run:    docker run -p 5080:5080 -e OPENAI_API_KEY=$OPENAI_API_KEY sre-agent:latest

ARG PYTHON_VERSION=3.12-slim

FROM python:${PYTHON_VERSION} AS deps
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src/ ./src/
RUN pip install --upgrade pip && pip install --no-cache-dir ".[dev]"

# ─────────────────────────────────────────────────────────────────────────
FROM python:${PYTHON_VERSION} AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=5080 \
    SRE_LOG_JSON=true \
    SRE_LOG_LEVEL=INFO

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --shell /bin/bash sre

WORKDIR /app
COPY --from=deps /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=deps /usr/local/bin /usr/local/bin
COPY --chown=sre:sre . .

# Install our own package (now that source is in /app)
RUN pip install --no-deps -e .

USER sre

EXPOSE 5080
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl --fail http://127.0.0.1:5080/api/health || exit 1

# 4 workers × 2 threads — enough for many concurrent incidents without
# overloading a small box. Graceful timeout matches typical incident pipeline.
CMD ["gunicorn", \
     "--bind", "0.0.0.0:5080", \
     "--workers", "4", \
     "--threads", "2", \
     "--worker-class", "gthread", \
     "--graceful-timeout", "60", \
     "--access-logfile", "-", \
     "--error-logfile", "-", \
     "dashboard.app:app"]
