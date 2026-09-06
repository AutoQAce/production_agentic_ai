# ==========================
# Layer 0 — Containerization
# Multi-stage build: uv installs deps into a venv, final image is slim.
# ==========================
# Pinned by digest, not just by tag: `python:3.12-slim` is a moving target that is rebuilt
# whenever its own base or packages change, so the same Dockerfile can produce different images
# on different days. A digest makes the build reproducible and makes a base-image change a
# reviewed commit rather than a silent event. Refresh it deliberately (and re-run the scan).
FROM python:3.12-slim@sha256:78387bc3881b8273120a12ebe6c1ab22b018ccc2c9adf565ae1ac9b536e184ea AS builder

# uv for fast, lockfile-based installs
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv

# Install deps first (cached layer) using only the lockfiles
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

# ----- final runtime image -----
FROM python:3.12-slim@sha256:78387bc3881b8273120a12ebe6c1ab22b018ccc2c9adf565ae1ac9b536e184ea

WORKDIR /app
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

COPY --from=builder /opt/venv /opt/venv
COPY . .

EXPOSE 8000

# Refuse to start without an explicit APP_ENV. Python cannot make this check -- by the time it
# runs, os.getenv's fallback has already erased the difference between unset and 'development'.
# See the script for the full reasoning.
RUN chmod +x /app/docker-entrypoint.sh

# Drop root. A container process that keeps root can write anywhere in the filesystem, and if the
# agent is ever tricked into executing code (Bible Step 9, ASI05) that is the difference between a
# bad response and a persistent foothold.
#
# Note what is deliberately NOT chowned: /app and /opt/venv stay root-owned and world-readable, so
# the app can read its own code and dependencies but cannot rewrite them. Chowning them to `app`
# would hand that ability back and undo most of the benefit. PYTHONDONTWRITEBYTECODE=1 above is
# what makes read-only source workable -- no .pyc files are written next to the modules.
RUN groupadd --system app && useradd --system --gid app --no-create-home --home-dir /app app
USER app

ENTRYPOINT ["/app/docker-entrypoint.sh"]

# uvloop is Linux-only and present here (the image is Linux), so uvicorn will use it automatically.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
