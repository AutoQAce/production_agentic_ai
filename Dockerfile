# ==========================
# Layer 0 — Containerization
# Multi-stage build: uv installs deps into a venv, final image is slim.
# ==========================
FROM python:3.12-slim AS builder

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
FROM python:3.12-slim

WORKDIR /app
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

COPY --from=builder /opt/venv /opt/venv
COPY . .

EXPOSE 8000
# uvloop is Linux-only and present here (the image is Linux), so uvicorn will use it automatically.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
