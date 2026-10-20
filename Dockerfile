# syntax=docker/dockerfile:1.7
# Multi-stage hardened image for 3HK Assistant.
# Base images pinned by digest (resolved 2026-10-13).

############################
# Frontend build (Node 26)
############################
FROM node:26-bookworm@sha256:a856ae5e25d498bbe5ec85fde88f00f5ed99908fda803ba39d7735ab8574f58c AS frontend-build
WORKDIR /src/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
COPY LICENSE THIRD_PARTY_NOTICES.md /src/
RUN NODE_OPTIONS=--max-old-space-size=512 npm run build

############################
# Python runtime
############################
FROM python:3.15-slim-bookworm@sha256:2a41267d9de9d358f77a1de356e0f16ecba8d39827855be0ce9ef4792edce402 AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    HOST=0.0.0.0 \
    PORT=8888

# Non-root user
RUN groupadd --system --gid 10001 app \
 && useradd --system --uid 10001 --gid app --home-dir /app --shell /usr/sbin/nologin app \
 && mkdir -p /app/backend/plans_cache /app/frontend \
 && chown -R app:app /app

WORKDIR /app/backend

# System deps minimal (ca-certificates for HTTPS upstream)
RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates \
 && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt /app/backend/requirements.txt
COPY backend/requirements.lock /app/backend/requirements.lock
RUN pip install --no-cache-dir --require-hashes -r /app/backend/requirements.lock
# Package installers are not part of the runtime. pip vendors older libraries
# independently of our lock; remove it and ensurepip's bundled installer wheel.
RUN python -m pip uninstall --yes pip \
 && python -c "import pathlib, shutil, sysconfig; shutil.rmtree(pathlib.Path(sysconfig.get_path('stdlib')) / 'ensurepip')"
COPY LICENSE THIRD_PARTY_NOTICES.md /app/

# Application source (no local secrets or host-only extensions)
COPY backend/app /app/backend/app
COPY backend/run.py /app/backend/run.py
COPY backend/start.sh /app/backend/start.sh
COPY backend/pyproject.toml /app/backend/pyproject.toml
COPY backend/pyrightconfig.json /app/backend/pyrightconfig.json
RUN chmod 755 /app/backend/start.sh \
 && mkdir -p /app/backend/plans_cache \
 && chown -R app:app /app

# Built frontend into location expected by runtime (repo layout: ../frontend/dist)
COPY --from=frontend-build /src/frontend/dist /app/frontend/dist
RUN chown -R app:app /app/frontend

USER app
EXPOSE 8888
HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8888/_health', timeout=3)"

# Bind all interfaces inside container; host publish is loopback-only via Compose.
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8888", "--no-access-log"]
