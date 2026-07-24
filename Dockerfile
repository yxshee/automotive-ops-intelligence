FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

COPY --from=ghcr.io/astral-sh/uv:0.9.7 /uv /uvx /bin/

WORKDIR /app

# Dependencies first, so a source edit does not invalidate the dependency layer.
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --locked --no-install-project --no-dev

COPY src ./src
RUN uv sync --locked --no-dev

# Run as a non-root user.
RUN useradd --create-home --uid 10001 app && chown -R app:app /app
USER app

ENV PATH="/app/.venv/bin:$PATH"

ENTRYPOINT ["python", "-m", "automotive_ops_intelligence"]
CMD ["--offline"]
