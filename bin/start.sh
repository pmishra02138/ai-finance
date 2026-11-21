#!/usr/bin/env bash
# AI Personal Finance Advisor - Unified Single-Port Launcher (macOS & Linux)
# Serves both the web UI and FastAPI backend on one port (default: 8787).
#
# Usage:
#   ./bin/start.sh                 # Local uv server at http://127.0.0.1:8787
#   ./bin/start.sh --restart       # Stop any existing listener on port 8787 and restart
#   ./bin/start.sh --docker        # Single Docker container at http://localhost:8787
#   ./bin/start.sh --port 8000     # Custom port

set -e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODE="local"
HOST="127.0.0.1"
PORT="8787"
RESTART=0

while [ $# -gt 0 ]; do
  case "$1" in
    --docker)
      MODE="docker"
      shift
      ;;
    --local)
      MODE="local"
      shift
      ;;
    --restart|-r)
      RESTART=1
      shift
      ;;
    --host)
      HOST="$2"
      shift 2
      ;;
    --port)
      PORT="$2"
      shift 2
      ;;
    -h|--help)
      echo "Usage: ./bin/start.sh [--local | --docker] [--restart] [--host HOST] [--port PORT]"
      echo "  --local        Run unified FastAPI + frontend server with uv (default)"
      echo "  --docker       Build and start single-port Docker container (localhost:8787)"
      echo "  --restart, -r  Stop any existing listener on PORT before starting"
      echo "  --host HOST    Bind address (default: 127.0.0.1)"
      echo "  --port PORT    Port to listen on (default: 8787)"
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      exit 1
      ;;
  esac
done

cd "$REPO_ROOT"

if [ "$MODE" = "docker" ]; then
  if ! command -v docker >/dev/null 2>&1; then
    echo "Error: docker not found. Install Docker Desktop for macOS first." >&2
    exit 1
  fi
  mkdir -p "${REPO_ROOT}/data" "${REPO_ROOT}/output"
  docker compose up -d --build app
  echo "✓ App running at http://localhost:8787"
  echo "  Default login: user / password"
  exit 0
fi

if ! command -v uv >/dev/null 2>&1; then
  echo "Error: uv not found. Install uv (https://docs.astral.sh/uv/) or use ./bin/start.sh --docker" >&2
  exit 1
fi

if command -v lsof >/dev/null 2>&1; then
  pids=$(lsof -tiTCP:"$PORT" -sTCP:LISTEN 2>/dev/null || true)
elif command -v fuser >/dev/null 2>&1; then
  pids=$(fuser "${PORT}/tcp" 2>/dev/null || true)
else
  pids=""
fi

if [ -n "$pids" ]; then
  if [ "$RESTART" -eq 1 ]; then
    echo "Stopping existing process(es) on port ${PORT}: ${pids}"
    echo "$pids" | xargs kill 2>/dev/null || true
    sleep 1
  else
    echo "Error: port ${PORT} is already in use (PID: $(echo "$pids" | tr '\n' ' '))." >&2
    echo "Run './bin/start.sh --restart' to replace it, or './bin/start.sh --port 8000' to use another port." >&2
    exit 1
  fi
fi

if [ ! -d "${REPO_ROOT}/.venv" ]; then
  uv sync --no-install-project --no-dev
fi

echo "Starting AI Personal Finance Advisor at http://${HOST}:${PORT} (default login: user / password) ..."
exec uv run --no-sync uvicorn scripts.server:app --host "$HOST" --port "$PORT"
