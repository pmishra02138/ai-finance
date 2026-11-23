FROM python:3.11-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy

WORKDIR /app

COPY pyproject.toml requirements.txt ./
RUN uv sync --no-install-project --no-dev

COPY scripts/ ./scripts/
COPY specs/ ./specs/
COPY frontend/public/ ./frontend/public/

RUN useradd --create-home --uid 1000 aifinance && \
    mkdir -p /app/data /data && \
    chown -R aifinance:aifinance /app /data

USER aifinance

ENV STATIC_DIR=/app/frontend/public \
    AI_FINANCE_DB_PATH=/app/data/ai_finance.db

EXPOSE 8787

HEALTHCHECK --interval=10s --timeout=3s --start-period=5s \
    CMD python3 -c "import os, urllib.request; urllib.request.urlopen(f'http://localhost:{os.environ.get(\"PORT\", \"8787\")}/api/health')"

CMD ["sh", "-c", "uv run --no-sync python -m uvicorn scripts.server:app --host 0.0.0.0 --port ${PORT:-8787}"]
