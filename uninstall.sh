#!/usr/bin/env bash
# AI Personal Finance Advisor - Uninstaller
# Removes all finance skills from Antigravity (~/.gemini/antigravity/) and/or Claude (~/.claude/).

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m'

AUTO_YES=0
for arg in "$@"; do
  case "$arg" in
    -y|--yes)
      AUTO_YES=1
      ;;
    *)
      echo "Unknown option: $arg" >&2
      exit 1
      ;;
  esac
done

AGY_SKILLS_DIR="${HOME}/.gemini/antigravity/skills"
CLAUDE_SKILLS_DIR="${HOME}/.claude/skills"
CLAUDE_AGENTS_DIR="${HOME}/.claude/agents"

echo ""
echo -e "${BOLD}${YELLOW}AI Personal Finance Advisor — Uninstaller${NC}"
echo "============================================="
echo ""
echo -e "${YELLOW}This will remove installed finance skills from:${NC}"
echo "  • ${AGY_SKILLS_DIR}/finance*"
echo "  • ${CLAUDE_SKILLS_DIR}/finance*"
echo "  • ${CLAUDE_AGENTS_DIR}/finance-*.md"
echo ""

if [ "$AUTO_YES" -eq 0 ]; then
  read -p "Continue with uninstall? (y/N) " -n 1 -r
  echo ""
  if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${BLUE}Uninstall cancelled.${NC}"
    exit 0
  fi
fi

removed_count=0

remove_skills_in_dir() {
  local skills_dir="$1"
  [ -d "$skills_dir" ] || return 0
  if [ -d "${skills_dir}/finance" ]; then
    rm -rf "${skills_dir}/finance"
    echo -e "${GREEN}✓${NC} Removed ${skills_dir}/finance/"
    removed_count=$((removed_count + 1))
  fi
  for dir in "${skills_dir}"/finance-*; do
    if [ -d "$dir" ]; then
      rm -rf "$dir"
      echo -e "${GREEN}✓${NC} Removed ${dir}/"
      removed_count=$((removed_count + 1))
    fi
  done
}

remove_skills_in_dir "$AGY_SKILLS_DIR"
remove_skills_in_dir "$CLAUDE_SKILLS_DIR"

if [ -d "${CLAUDE_AGENTS_DIR}" ]; then
  for file in "${CLAUDE_AGENTS_DIR}"/finance-*.md; do
    if [ -f "$file" ]; then
      rm -f "$file"
      echo -e "${GREEN}✓${NC} Removed ${file}"
      removed_count=$((removed_count + 1))
    fi
  done
fi

echo ""
if [ "$removed_count" -eq 0 ]; then
  echo -e "${YELLOW}Nothing to remove. AI Personal Finance Advisor was not installed.${NC}"
else
  echo -e "${BOLD}${GREEN}Uninstall complete.${NC} Removed ${removed_count} item(s)."
fi
echo ""
