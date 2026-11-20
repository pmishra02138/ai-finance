#!/usr/bin/env bash
# AI Personal Finance Advisor - Stop Script (macOS & Linux)
# Stops Docker Compose services (if running) and frees local ports (default: 3000, 8787).
#
# Usage:
#   ./stop.sh
#   ./stop.sh --port 3001 --api-port 8788

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRONTEND_PORT="3000"
API_PORT="8787"

while [ $# -gt 0 ]; do
  case "$1" in
    --port)
      FRONTEND_PORT="$2"
      shift 2
      ;;
    --api-port)
      API_PORT="$2"
      shift 2
      ;;
    -h|--help)
      echo "Usage: ./stop.sh [--port FRONTEND_PORT] [--api-port API_PORT]"
      echo "  --port PORT           Node.js frontend port to free (default: 3000)"
      echo "  --api-port API_PORT   FastAPI backend port to free (default: 8787)"
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      exit 1
      ;;
  esac
done

cd "$SCRIPT_DIR"

if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
  if [ -f "${SCRIPT_DIR}/docker-compose.yml" ]; then
    docker compose down --remove-orphans >/dev/null 2>&1 || true
    echo "✓ Stopped Docker Compose services (if any)"
  fi
fi

free_port() {
  local port="$1"
  local label="$2"
  local pids=""
  if command -v lsof >/dev/null 2>&1; then
    pids=$(lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null || true)
  elif command -v fuser >/dev/null 2>&1; then
    pids=$(fuser "${port}/tcp" 2>/dev/null || true)
  fi

  if [ -n "$pids" ]; then
    echo "Stopping ${label} on port ${port} (PID: $(echo "$pids" | tr '\n' ' '))..."
    echo "$pids" | xargs kill 2>/dev/null || true
    sleep 0.5
    echo "✓ Freed port ${port}"
  else
    echo "✓ Port ${port} (${label}) is already free"
  fi
}

free_port "$FRONTEND_PORT" "Node.js frontend"
free_port "$API_PORT" "FastAPI backend"
