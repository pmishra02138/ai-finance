#!/usr/bin/env bash
# AI Personal Finance Advisor - Installer
# Repo: zubair-trabzada/ai-finance
#
# Local AGY install (default): ./install.sh
# Docker localhost install (Mac): ./install.sh --docker
# Legacy Claude target:           ./install.sh --claude

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
BOLD='\033[1m'
NC='\033[0m'

REPO="zubair-trabzada/ai-finance"
BRANCH="main"
TARBALL_URL="https://github.com/${REPO}/archive/refs/heads/${BRANCH}.tar.gz"

TARGET_MODE="agy"     # agy | claude
INSTALL_MODE="local"  # local | docker
TMP_DIR=""

cleanup() {
  if [ -n "$TMP_DIR" ] && [ -d "$TMP_DIR" ]; then
    rm -rf "$TMP_DIR"
  fi
}
trap cleanup EXIT

for arg in "$@"; do
  case "$arg" in
    --docker)
      INSTALL_MODE="docker"
      ;;
    --local)
      INSTALL_MODE="local"
      ;;
    --claude)
      TARGET_MODE="claude"
      ;;
    --agy)
      TARGET_MODE="agy"
      ;;
    -h|--help)
      echo "Usage: ./install.sh [--local | --docker] [--agy | --claude]"
      echo "  --local   Install skills & scripts locally (default)"
      echo "  --docker  Build and start the localhost:8787 Docker container (Mac/Linux)"
      echo "  --agy     Install into ~/.gemini/antigravity/skills/ (default)"
      echo "  --claude  Install into ~/.claude/skills/"
      exit 0
      ;;
    *)
      echo "Unknown option: $arg" >&2
      exit 1
      ;;
  esac
done

if [ "$TARGET_MODE" = "claude" ]; then
  BASE_DIR="${HOME}/.claude"
  SKILLS_DIR="${BASE_DIR}/skills"
  AGENTS_DIR="${BASE_DIR}/agents"
  TARGET_LABEL="Claude Code (~/.claude/skills/)"
else
  BASE_DIR="${HOME}/.gemini/antigravity"
  SKILLS_DIR="${BASE_DIR}/skills"
  AGENTS_DIR=""
  TARGET_LABEL="Antigravity (~/.gemini/antigravity/skills/)"
fi

# Detect local vs remote install
SCRIPT_PATH="${BASH_SOURCE[0]:-}"
IS_LOCAL=0
SOURCE_DIR=""

if [ -n "$SCRIPT_PATH" ] && [ -f "$SCRIPT_PATH" ]; then
  SOURCE_DIR="$(cd "$(dirname "$SCRIPT_PATH")" && pwd)"
  if [ -d "${SOURCE_DIR}/skills" ] && [ -d "${SOURCE_DIR}/finance" ]; then
    IS_LOCAL=1
  fi
fi

print_banner() {
  echo ""
  echo -e "${BOLD}${YELLOW}╔══════════════════════════════════════════════════════════╗${NC}"
  echo -e "${BOLD}${YELLOW}║                                                          ║${NC}"
  echo -e "${BOLD}${YELLOW}║       AI PERSONAL FINANCE ADVISOR — Installer            ║${NC}"
  echo -e "${BOLD}${YELLOW}║       Antigravity (AGY) & Localhost Docker Edition       ║${NC}"
  echo -e "${BOLD}${YELLOW}║                                                          ║${NC}"
  echo -e "${BOLD}${YELLOW}╚══════════════════════════════════════════════════════════╝${NC}"
  echo ""
}

err() { echo -e "${RED}✗ $1${NC}" >&2; }
ok() { echo -e "${GREEN}✓${NC} $1"; }
info() { echo -e "${BLUE}ℹ${NC} $1"; }
warn() { echo -e "${YELLOW}⚠${NC} $1"; }

check_python() {
  if ! command -v python3 >/dev/null 2>&1; then
    err "Python 3 not found. Please install Python 3.8 or later."
    return 1
  fi

  local pyver major minor
  pyver=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
  major=$(echo "$pyver" | cut -d. -f1)
  minor=$(echo "$pyver" | cut -d. -f2)

  if [ "$major" -lt 3 ] || { [ "$major" -eq 3 ] && [ "$minor" -lt 8 ]; }; then
    err "Python 3.8+ required (found ${pyver})."
    return 1
  fi

  ok "Python ${pyver} detected"
  return 0
}

check_reportlab() {
  if command -v uv >/dev/null 2>&1 && [ -f "${SOURCE_DIR}/pyproject.toml" ]; then
    info "uv detected — syncing dependencies via uv..."
    if (cd "$SOURCE_DIR" && uv sync --no-install-project --no-dev >/dev/null 2>&1); then
      ok "Dependencies synced with uv (.venv)"
      return 0
    fi
  fi

  if python3 -c "import reportlab" >/dev/null 2>&1; then
    local rlver
    rlver=$(python3 -c "import reportlab; print(reportlab.Version)")
    ok "ReportLab ${rlver} detected"
    return 0
  fi

  warn "ReportLab not installed. Attempting to install..."
  if pip3 install --quiet --user "reportlab>=4.0.0" 2>/dev/null \
    || python3 -m pip install --quiet --user "reportlab>=4.0.0" 2>/dev/null; then
    ok "ReportLab installed"
    return 0
  fi

  warn "Could not auto-install dependencies (e.g., PEP 668 externally managed Python)."
  echo "    Recommended: uv sync   (or run with Docker: ./install.sh --docker)"
  echo "    Or manually: pip3 install -r requirements.txt"
  return 0
}

fetch_remote() {
  info "Downloading repo tarball..."
  TMP_DIR=$(mktemp -d)
  if command -v curl >/dev/null 2>&1; then
    curl -fsSL "$TARBALL_URL" | tar -xz -C "$TMP_DIR"
  elif command -v wget >/dev/null 2>&1; then
    wget -qO- "$TARBALL_URL" | tar -xz -C "$TMP_DIR"
  else
    err "Neither curl nor wget found."
    exit 1
  fi
  SOURCE_DIR="${TMP_DIR}/ai-finance-${BRANCH}"
  if [ ! -d "$SOURCE_DIR" ]; then
    err "Tarball extraction failed: ${SOURCE_DIR} not found."
    exit 1
  fi
  ok "Repo downloaded to ${SOURCE_DIR}"
}

install_orchestrator() {
  local src="${SOURCE_DIR}/finance"
  if [ ! -d "$src" ]; then
    warn "No orchestrator folder at ${src}, skipping."
    return
  fi
  mkdir -p "${SKILLS_DIR}/finance"
  cp -R "${src}/." "${SKILLS_DIR}/finance/"
  ok "Installed orchestrator → ${SKILLS_DIR}/finance/"
}

install_skills() {
  local src="${SOURCE_DIR}/skills"
  if [ ! -d "$src" ]; then
    warn "No skills/ folder at ${src}, skipping."
    return
  fi
  local count=0
  for dir in "$src"/*/; do
    [ -d "$dir" ] || continue
    local name
    name=$(basename "$dir")
    mkdir -p "${SKILLS_DIR}/${name}"
    cp -R "${dir}." "${SKILLS_DIR}/${name}/"
    count=$((count + 1))
  done
  ok "Installed ${count} sub-skills → ${SKILLS_DIR}/finance-*/"
}

install_agents() {
  [ -n "$AGENTS_DIR" ] || return 0
  local src="${SOURCE_DIR}/agents"
  [ -d "$src" ] || return 0
  mkdir -p "${AGENTS_DIR}"
  local count=0
  for file in "$src"/*.md; do
    [ -f "$file" ] || continue
    cp "$file" "${AGENTS_DIR}/"
    count=$((count + 1))
  done
  if [ "$count" -gt 0 ]; then
    ok "Installed ${count} agents → ${AGENTS_DIR}/"
  fi
}

install_scripts() {
  local src="${SOURCE_DIR}/scripts"
  if [ ! -d "$src" ]; then
    warn "No scripts/ folder at ${src}, skipping."
    return
  fi
  mkdir -p "${SKILLS_DIR}/finance/scripts"
  cp -R "${src}/." "${SKILLS_DIR}/finance/scripts/"
  chmod +x "${SKILLS_DIR}/finance/scripts/"*.py 2>/dev/null || true
  ok "Installed scripts → ${SKILLS_DIR}/finance/scripts/"
}

install_docker_localhost() {
  info "Setting up Docker localhost service (macOS/Linux)..."
  if ! command -v docker >/dev/null 2>&1; then
    err "Docker CLI not found. On macOS, install Docker Desktop: https://www.docker.com/products/docker-desktop/"
    exit 1
  fi
  if ! docker info >/dev/null 2>&1; then
    err "Docker daemon is not running. Start Docker Desktop on macOS and retry."
    exit 1
  fi
  mkdir -p "${SOURCE_DIR}/output" "${SOURCE_DIR}/data"
  (
    cd "$SOURCE_DIR"
    docker compose up -d --build app
  )
  ok "Docker container running at http://localhost:8787"
  echo ""
  echo -e "${BOLD}${CYAN}Localhost endpoints:${NC}"
  echo -e "  ${GREEN}•${NC} Web UI:   http://localhost:8787  (default login: user / password)"
  echo -e "  ${GREEN}•${NC} API Docs: http://localhost:8787/api/docs"
  echo -e "  ${GREEN}•${NC} Health:   curl http://localhost:8787/api/health"
  echo ""
}

print_summary() {
  local skill_count
  skill_count=$(find "${SKILLS_DIR}" -maxdepth 1 -type d -name "finance*" 2>/dev/null | wc -l | tr -d ' ')

  echo ""
  echo -e "${BOLD}${GREEN}╔══════════════════════════════════════════════════════════╗${NC}"
  echo -e "${BOLD}${GREEN}║              INSTALLATION COMPLETE                       ║${NC}"
  echo -e "${BOLD}${GREEN}╚══════════════════════════════════════════════════════════╝${NC}"
  echo ""
  echo -e "${BOLD}Installed (${TARGET_LABEL}):${NC}"
  echo -e "  ${GREEN}•${NC} ${skill_count} skill folder(s) under ${SKILLS_DIR}/"
  echo ""
  echo -e "${BOLD}${CYAN}Quick start:${NC} open Antigravity in your workspace or ask for ${MAGENTA}finance-analyze${NC} / ${MAGENTA}finance-quick${NC}"
  echo -e "${YELLOW}⚠  This is NOT financial advice. Consult a licensed financial advisor.${NC}"
  echo ""
}

main() {
  print_banner

  info "Detecting environment..."
  if [ "$IS_LOCAL" -eq 1 ]; then
    ok "Local install detected (source: ${SOURCE_DIR})"
  else
    info "Remote install detected"
    fetch_remote
  fi

  if [ "$INSTALL_MODE" = "docker" ]; then
    install_docker_localhost
  fi

  echo ""
  info "Checking prerequisites..."
  check_python || exit 1
  check_reportlab

  echo ""
  info "Creating skill directories (${TARGET_LABEL})..."
  mkdir -p "${SKILLS_DIR}"
  ok "${SKILLS_DIR} ready"

  echo ""
  info "Installing components..."
  install_orchestrator
  install_skills
  install_agents
  install_scripts

  print_summary
}

main "$@"
