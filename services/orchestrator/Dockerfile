FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.10 /uv /uvx /bin/

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONPATH=/app/src

COPY pyproject.toml ./
RUN uv venv /app/.venv && \
    uv pip install --python /app/.venv/bin/python --no-cache -r pyproject.toml

COPY src ./src
RUN uv pip install --python /app/.venv/bin/python --no-cache --no-deps .

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8080
CMD ["sh", "-c", "exec uvicorn orchestrator.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
