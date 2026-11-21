#!/usr/bin/env bash
# AI Personal Finance Advisor - Stop Script (macOS & Linux)
# Stops Docker Compose services (if running) and frees the app port (default: 8787).

set -e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PORT="8787"

while [ $# -gt 0 ]; do
  case "$1" in
    --port)
      PORT="$2"
      shift 2
      ;;
    -h|--help)
      echo "Usage: ./bin/stop.sh [--port PORT]"
      echo "  --port PORT   Port to free (default: 8787)"
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      exit 1
      ;;
  esac
done

cd "$REPO_ROOT"

if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
  if [ -f "${REPO_ROOT}/docker-compose.yml" ]; then
    docker compose down --remove-orphans >/dev/null 2>&1 || true
    echo "✓ Stopped Docker Compose services (if any)"
  fi
fi

pids=""
if command -v lsof >/dev/null 2>&1; then
  pids=$(lsof -tiTCP:"$PORT" -sTCP:LISTEN 2>/dev/null || true)
elif command -v fuser >/dev/null 2>&1; then
  pids=$(fuser "${PORT}/tcp" 2>/dev/null || true)
fi

if [ -n "$pids" ]; then
  echo "Stopping server on port ${PORT} (PID: $(echo "$pids" | tr '\n' ' '))..."
  echo "$pids" | xargs kill 2>/dev/null || true
  sleep 0.5
  echo "✓ Freed port ${PORT}"
else
  echo "✓ Port ${PORT} is already free"
fi
