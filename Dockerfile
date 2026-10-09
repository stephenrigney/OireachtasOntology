# Reproducible production ETL/operations image. Runtime secrets are mounted or
# injected by Compose; no credentials or source captures are copied here.
FROM ghcr.io/astral-sh/uv:0.12.19 AS uv
FROM restic/restic:0.19.1 AS restic
FROM python:3.12.12-slim-bookworm

COPY --from=uv /uv /uvx /usr/local/bin/
COPY --from=restic /usr/bin/restic /usr/local/bin/restic

ENV UV_PROJECT_ENVIRONMENT=/app/.venv \
    UV_LINK_MODE=copy \
    UV_CACHE_DIR=/tmp/uv-cache \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH=/app/.venv/bin:$PATH

WORKDIR /app
COPY . /app

ARG OIR_GIT_COMMIT=unknown
RUN printf '%s\n' "$OIR_GIT_COMMIT" > /app/BUILD_INFO \
    && uv sync --locked --no-dev \
    && rm -rf /tmp/uv-cache

USER 10001:10001
ENTRYPOINT ["oir-etl"]
