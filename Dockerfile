FROM python:3.11-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy

WORKDIR /app

COPY pyproject.toml requirements.txt ./
RUN uv sync --no-install-project --no-dev

COPY scripts/ ./scripts/
COPY finance/ ./finance/
COPY skills/ ./skills/

RUN mkdir -p /data

EXPOSE 8787

CMD ["uv", "run", "--no-sync", "uvicorn", "scripts.server:app", "--host", "0.0.0.0", "--port", "8787"]
