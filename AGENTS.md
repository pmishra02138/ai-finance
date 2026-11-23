# AGENTS.md — Project Guidelines for `ai-finance`

## Repository Structure
- `.agents/skills/` — Antigravity (AGY) workspace skill symlinks pointing to `../../finance` and `../../skills/finance-*`.
- `finance/SKILL.md` — Main orchestrator skill (with YAML frontmatter).
- `skills/finance-*/SKILL.md` — 14 sub-skills (each must include YAML frontmatter with `name` and `description`).
- `scripts/scoring.py` — Shared pure-stdlib Financial Health Score grading and signal helpers (`score_grade`, `score_signal`).
- `scripts/calculators/` — Modular deterministic calculation engine for all 14 skills (`__init__.py`, `common.py`, `baseline.py`, `foundation.py`, `growth.py`, `horizons.py`, `synthesis.py`).
- `scripts/pdf/` — Modular ReportLab 9-page PDF generator (`__init__.py`, `theme.py`, `components.py`, `pages.py`, `demo_data.py`).
- `scripts/generate_finance_pdf.py` — Thin CLI entrypoint (`--data <json>` or `--demo`) and compatibility shim for `scripts/pdf/`.
- `scripts/db.py` — SQLite persistence layer (`data/ai_finance.db`) with `users`, `sessions`, `financial_plans`, and `skill_runs` tables (seeds default user `user` / `password`).
- `scripts/server.py` — Unified single-port FastAPI + Uvicorn server (`http://localhost:8787`) serving both the static frontend (`frontend/public/`) and `/api/*` endpoints (`/api/health`, `/api/auth/*`, `/api/plans/*`, `/api/skills`, `/api/demo`, `/api/demo-data`, `/api/generate`, `/api/docs`).
- `frontend/public/` — Static SPA frontend (`index.html`, `styles.css`, `app.js`, `skills.js`, `charts.js`) served directly by FastAPI on port `8787`.
- `bin/start.sh` / `bin/stop.sh` — Unified macOS/Linux single-port launcher & stopper (`8787`), supporting `--local`, `--docker`, and `--restart`.
- `bin/start.ps1` / `bin/stop.ps1` — Unified Windows PowerShell single-port launcher & stopper (`-Docker`, `-Restart`, `-Port`).
- `Dockerfile`, `docker-compose.yml`, `.dockerignore` — Single-container non-root Docker setup on port `8787` for macOS/Linux/Windows.
- `install.sh` / `uninstall.sh` — Installer/uninstaller supporting `--local` (AGY `~/.gemini/antigravity/skills/` + `uv sync`), `--docker` (`localhost:8787`), and `--claude` (`~/.claude/skills/`).
- `pyproject.toml` / `requirements.txt` — Python dependencies (`reportlab>=4.0.0`, `fastapi>=0.110.0`, `uvicorn>=0.27.0`) managed with `uv`.

## Coding & Content Conventions

### Modularity & Architecture
- **Keep modules focused and small:** Proactively split Python or JS files into clean subpackages/modules before they exceed ~400–500 lines or accumulate multiple distinct responsibilities (e.g., routing, business logic, persistence, rendering, and demo data should live in separate modules).
- **Decouple shared helpers:** Place pure-stdlib shared utilities (like `scripts/scoring.py`) in standalone modules so business logic never depends on heavyweight rendering or framework packages (like ReportLab or FastAPI).
- **Preserve thin entrypoints:** Keep CLI scripts and server entrypoints thin, delegating implementation to modular packages while maintaining backward-compatible re-exports when refactoring.

### Skills (`.agents/skills/`, `finance/`, and `skills/finance-*/`)
- Keep YAML frontmatter (`name`, `description`) at the top of every `SKILL.md`.
- Use AGY-compatible tool names (`invoke_subagent`, `run_command`) and workspace-relative script paths (`scripts/generate_finance_pdf.py`), never Claude-only `Task` or `~/.claude/` assumptions.
- Include the educational / not-financial-advice disclaimer in every skill and generated output.
- Keep command names, file paths, CLI flags, and score-to-grade thresholds consistent with `scripts/generate_finance_pdf.py` and `README.md`.

### Python (`scripts/scoring.py`, `scripts/calculators/`, `scripts/pdf/`, `scripts/generate_finance_pdf.py`, `scripts/server.py`)
- Target **Python 3.8+** compatibility and **ReportLab >= 4.0.0**.
- **XML safety:** Always escape dynamic/user-supplied strings with `xml.sax.saxutils.escape()` before passing them into ReportLab `Paragraph(...)`.
- **Defensive data handling:** Use `.get()` with sensible defaults, validate input types (e.g., JSON root is a `dict`), and guard against empty lists (such as `investments.allocation` or `debt.accounts`) so charts and tables never raise `ZeroDivisionError` or `KeyError`.
- **Page geometry:** Usable content width is `PAGE_W - MARGIN_L - MARGIN_R` (`7.1 * inch`). Do not exceed this width in tables or drawings, and avoid fixed small row heights where dynamic text can overflow.
- Keep `_demo_data()` internally consistent (category scores, composite score, cash flow totals, and debt minimum payments should match).

### Shell (`install.sh`, `uninstall.sh`)
- Keep scripts `set -e` safe, quote variable expansions (`"$var"`), and clean up temporary directories via `trap` on `EXIT`.
- Avoid referencing directories or files that do not exist in the repository without handling their absence cleanly.

## Verification
After making changes, run the applicable checks before reporting completion:
- Python syntax: `python3 -m py_compile scripts/*.py scripts/calculators/*.py scripts/pdf/*.py`
- Shell syntax: `bash -n install.sh uninstall.sh bin/start.sh bin/stop.sh`
- E2E suite: `uv run python -m unittest discover -s tests -v` (or `python3 -m unittest discover -s tests -v`)
- Symlinks check: `ls -la .agents/skills/`
- PDF smoke test (if `reportlab` is installed): `uv run python scripts/generate_finance_pdf.py --demo --output /tmp/FINANCE-PLAN-sample.pdf`
- Docker smoke test (if Docker is running on Mac): `docker compose up -d --build api && curl -sf http://localhost:8787/health`
