# syntax=docker/dockerfile:1.7
# Multi-stage hardened image for 3HK Assistant.
# Base images pinned by digest (resolved 2026-07-16).

############################
# Frontend build (Node 24)
############################
FROM node:26-bookworm@sha256:9f94d34c787165dca03b74e5bf9c3bf90e8de79b19aa3d87fe1fa1694bf75c89 AS frontend-build
WORKDIR /src/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

############################
# Python runtime
############################
FROM python:3.14-slim-bookworm@sha256:9ab8d9c8514b44f90cf0029dd42fdd7e9e211e639c8b995304cc04568dee900f AS runtime

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
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

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
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8888"]
