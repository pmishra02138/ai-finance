#!/usr/bin/env bash
# AI Personal Finance Advisor - Unified Localhost Launcher
# Starts BOTH the FastAPI + SQLite backend (port 8787) and the Node.js frontend (port 3000).
#
# Usage:
#   ./start.sh                                   # Local uv + Node.js (http://127.0.0.1:3000)
#   ./start.sh --restart                         # Stop existing listeners on 3000/8787 and restart
#   ./start.sh --docker                          # Docker Compose (frontend :3000 + api :8787)
#   ./start.sh --port 3001 --api-port 8788       # Custom ports

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODE="local"
HOST="127.0.0.1"
FRONTEND_PORT="3000"
API_PORT="8787"
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
      FRONTEND_PORT="$2"
      shift 2
      ;;
    --api-port)
      API_PORT="$2"
      shift 2
      ;;
    -h|--help)
      echo "Usage: ./start.sh [--local | --docker] [--restart] [--host HOST] [--port FRONTEND_PORT] [--api-port API_PORT]"
      echo "  --local               Run FastAPI (uv) + Node.js frontend locally (default)"
      echo "  --docker              Build and start Docker Compose stack (frontend :3000 + api :8787)"
      echo "  --restart, -r         Stop any existing process using the target ports before starting"
      echo "  --host HOST           Bind address (default: 127.0.0.1)"
      echo "  --port PORT           Node.js frontend port (default: 3000)"
      echo "  --api-port API_PORT   FastAPI backend port (default: 8787)"
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      exit 1
      ;;
  esac
done

cd "$SCRIPT_DIR"

if [ "$MODE" = "docker" ]; then
  if ! command -v docker >/dev/null 2>&1; then
    echo "Error: docker not found. Install Docker Desktop for macOS first." >&2
    exit 1
  fi
  docker compose up -d --build
  echo "✓ Unified app running at http://localhost:3000 (API docs: http://localhost:8787/docs)"
  echo "  Default login: user / password"
  exit 0
fi

if ! command -v uv >/dev/null 2>&1; then
  echo "Error: uv not found. Install uv (https://docs.astral.sh/uv/) or use ./start.sh --docker" >&2
  exit 1
fi
if ! command -v node >/dev/null 2>&1; then
  echo "Error: node not found. Install Node.js 18+ or use ./start.sh --docker" >&2
  exit 1
fi

check_or_free_port() {
  local port="$1"
  local label="$2"
  local pids=""
  if command -v lsof >/dev/null 2>&1; then
    pids=$(lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null || true)
  fi
  if [ -n "$pids" ]; then
    if [ "$RESTART" -eq 1 ]; then
      echo "Stopping existing ${label} process(es) on port ${port}: ${pids}"
      echo "$pids" | xargs kill 2>/dev/null || true
      sleep 1
    else
      echo "Error: ${label} port ${port} is already in use (PID: $(echo "$pids" | tr '\n' ' '))." >&2
      echo "Run './start.sh --restart' to replace it, or './start.sh --port 3001 --api-port 8788' to use different ports." >&2
      exit 1
    fi
  fi
}

check_or_free_port "$API_PORT" "FastAPI backend"
check_or_free_port "$FRONTEND_PORT" "Node.js frontend"

if [ ! -d "${SCRIPT_DIR}/.venv" ]; then
  uv sync --no-install-project --no-dev
fi

API_PID=""
cleanup() {
  if [ -n "$API_PID" ] && kill -0 "$API_PID" 2>/dev/null; then
    kill "$API_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

echo "Starting FastAPI backend at http://${HOST}:${API_PORT} ..."
uv run --no-sync uvicorn scripts.server:app --host "$HOST" --port "$API_PORT" &
API_PID=$!

echo "Starting Node.js frontend at http://${HOST}:${FRONTEND_PORT} (default login: user / password) ..."
HOST="$HOST" PORT="$FRONTEND_PORT" BACKEND_URL="http://${HOST}:${API_PORT}" node "${SCRIPT_DIR}/frontend/server.js"
