FROM python:3.12

ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    UV_PYTHON_DOWNLOADS=0 \
    PATH="/app/.venv/bin:${PATH}"

# uv CLI (pinned). The build backend (uv_build) is resolved from PyPI per the
# pyproject build-system requirement during build isolation.
COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /bin/uv

WORKDIR /app

# Workspace manifests + lockfile + members first, so the dependency layer is
# cached and only re-resolved when the lock or a package manifest changes.
COPY pyproject.toml uv.lock README.md ./
COPY packages ./packages

# Install third-party deps + workspace members, but not the root project yet.
RUN uv sync --frozen --no-dev --no-install-project

# Application source, then install the root project (geneweaver-api).
COPY src ./src
RUN uv sync --frozen --no-dev

CMD ["uvicorn", "geneweaver.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
