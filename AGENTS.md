# AGENTS.md — Project Guidelines for `ai-finance`

## Repository Structure
- `docs/FINANCIAL_SPEC.md` — Plain-English human-readable specification of all 5 stages, 14 modules, formulas, 0–100 scoring rules, and Monte Carlo assumptions.
- `docs/WORKFLOW.md` — Visual Mermaid diagrams covering the 5-stage user workflow, system architecture, and Run & Sync / PDF request lifecycle.
- `specs/` — Machine-readable single source of truth for all 5 stages and 14 financial modules (`baseline.json`, `foundation.json`, `growth.json`, `horizons.json`, `synthesis.json`), defining stage layout, UI form schemas, engine modes (`deterministic` vs. `hybrid_monte_carlo`), and domain threshold constants.
- `scripts/scoring.py` — Shared pure-stdlib Financial Health Score grading and signal helpers (`score_grade`, `score_signal`).
- `scripts/module_registry.py` — Loader reading `specs/*.json` for `/api/modules` and calculator domain constants.
- `scripts/calculators/` — Modular calculation engine for all 14 modules:
  - `__init__.py` (`CALCULATORS`, `run_module`)
  - `common.py` (shared math, formatting, compounding)
  - `monte_carlo.py` (pure-stdlib seeded Monte Carlo simulation engine)
  - `baseline.py`, `foundation.py`, `growth.py`, `synthesis.py` (deterministic calculators)
  - `horizons.py` (hybrid deterministic baseline + Monte Carlo calculators)
- `scripts/pdf/` — Modular ReportLab 9-page PDF generator (`__init__.py`, `theme.py`, `components.py`, `pages.py`, `demo_data.py`).
- `scripts/generate_finance_pdf.py` — Thin CLI entrypoint (`--data <json>` or `--demo`) and compatibility shim for `scripts/pdf/`.
- `scripts/db.py` — SQLite persistence layer (`data/ai_finance.db`) with `users`, `sessions`, `financial_plans`, and `module_runs` tables (seeds default user `user` / `password`).
- `scripts/server.py` — Unified single-port FastAPI + Uvicorn server (`http://localhost:8787`) serving both the static frontend (`frontend/public/`) and `/api/*` endpoints (`/api/health`, `/api/auth/*`, `/api/plans/*`, `/api/modules`, `/api/demo`, `/api/demo-data`, `/api/generate`, `/api/docs`).
- `frontend/public/` — Spec-driven static SPA frontend (`index.html`, `styles.css`, `app.js`, `modules.js`, `charts.js`) served directly by FastAPI on port `8787`.
- `bin/start.sh` / `bin/stop.sh` — Unified macOS/Linux single-port launcher & stopper (`8787`), supporting `--local`, `--docker`, and `--restart`.
- `bin/start.ps1` / `bin/stop.ps1` — Unified Windows PowerShell single-port launcher & stopper (`-Docker`, `-Restart`, `-Port`).
- `Dockerfile`, `docker-compose.yml`, `.dockerignore` — Single-container non-root Docker setup on port `8787` for macOS/Linux/Windows.
- `pyproject.toml` / `requirements.txt` — Python dependencies (`reportlab>=4.0.0`, `fastapi>=0.110.0`, `uvicorn>=0.27.0`) managed with `uv`.

## Coding & Content Conventions

### Modularity & Architecture
- **Keep modules focused and small:** Proactively split Python or JS files into clean subpackages/modules before they exceed ~400–500 lines or accumulate multiple distinct responsibilities (e.g., routing, business logic, persistence, rendering, and demo data should live in separate modules).
- **Decouple shared helpers:** Place pure-stdlib shared utilities (like `scripts/scoring.py` and `scripts/calculators/monte_carlo.py`) in standalone modules so business logic never depends on heavyweight rendering or framework packages (like ReportLab or FastAPI).
- **Single source of truth (`specs/`):** Keep module metadata, form field schemas, and domain constants (e.g., IRS limits, Monte Carlo defaults) in `specs/*.json` rather than duplicating them across backend and frontend code.
- **Preserve thin entrypoints:** Keep CLI scripts and server entrypoints thin, delegating implementation to modular packages while maintaining backward-compatible re-exports when refactoring.

### Financial Modeling
- **Deterministic where exact:** Use deterministic math for cash flow, net worth, budgeting, emergency funds, fixed-APR debt amortization, tax limits, portfolio drift, and composite health scoring.
- **Hybrid Deterministic + Monte Carlo where volatility matters:** Use seeded pure-stdlib Monte Carlo simulations alongside deterministic baselines for long-horizon market-dependent modules (Retirement, FIRE, Goals, Scenario Compare).
- Include the educational / not-financial-advice disclaimer in the UI and generated PDF outputs.

### Python (`scripts/`)
- Target **Python 3.10+** compatibility and **ReportLab >= 4.0.0**.
- **XML safety:** Always escape dynamic/user-supplied strings with `xml.sax.saxutils.escape()` before passing them into ReportLab `Paragraph(...)`.
- **Defensive data handling:** Use `.get()` with sensible defaults, validate input types (e.g., JSON root is a `dict`), and guard against empty lists (such as `investments.allocation` or `debt.accounts`) so charts and tables never raise `ZeroDivisionError` or `KeyError`.
- **Page geometry:** Usable content width is `PAGE_W - MARGIN_L - MARGIN_R` (`7.1 * inch`). Do not exceed this width in tables or drawings, and avoid fixed small row heights where dynamic text can overflow.
- Keep `_demo_data()` internally consistent (category scores, composite score, cash flow totals, and debt minimum payments should match).

### Shell (`bin/start.sh`, `bin/stop.sh`)
- Keep scripts `set -e` safe, quote variable expansions (`"$var"`), and avoid referencing files that do not exist without handling their absence cleanly.

## Verification
After making changes, run the applicable checks before reporting completion:
- Python syntax: `python3 -m py_compile scripts/*.py scripts/calculators/*.py scripts/pdf/*.py tests/*.py`
- Shell syntax: `bash -n bin/start.sh bin/stop.sh`
- JS syntax: `node --check frontend/public/app.js && node --check frontend/public/modules.js && node --check frontend/public/charts.js`
- Full test suite: `uv run --no-sync python -m unittest discover -s tests -v`
- PDF smoke test: `uv run --no-sync python scripts/generate_finance_pdf.py --demo --output /tmp/FINANCE-PLAN-sample.pdf`
- Docker smoke test (if Docker is running): `docker compose up -d --build app && curl -sf http://localhost:8787/api/health`
