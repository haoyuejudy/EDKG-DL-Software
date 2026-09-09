FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    EDKG_DL_ASSET_DIR=/app/models

WORKDIR /app

RUN sed -i 's|deb.debian.org|mirrors.cernet.edu.cn|g; s|security.debian.org|mirrors.cernet.edu.cn|g' /etc/apt/sources.list.d/debian.sources \
    && apt-get update \
    && apt-get install -y --no-install-recommends openjdk-17-jre-headless \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock README.md ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --extra api --no-install-project

RUN .venv/bin/hf download HaoyueTan/edkg-dl-models \
    --local-dir "$EDKG_DL_ASSET_DIR"

COPY edkg_dl ./edkg_dl
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --extra api


ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

CMD ["edkg-dl-api", "--host", "0.0.0.0"]
