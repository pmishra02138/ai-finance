![AI Personal Finance Advisor](.github/banner.svg)

# AI Personal Finance Advisor

> **Full-Stack Personal Financial Planning Web App, Hybrid Deterministic + Monte Carlo Calculation Engine, SQLite Persistence, and 9-Page PDF Report Generator.**

> ⚠️ **This is NOT financial advice.** This tool is for informational and educational purposes only. Consult a licensed financial advisor, CPA, or attorney before making any financial decisions.

![License](https://img.shields.io/badge/License-MIT-blue.svg)

---

## ⭐ Overview

`ai-finance` is a **unified single-port FastAPI + static SPA web application** (`http://localhost:8787`) powered by structured JSON module specifications (`specs/*.json`) and a modular Python calculation engine.

Everything runs locally on your machine with **zero external LLM API keys or token costs**:
- **Spec-Driven 5-Stage Financial Planning UI** covering 14 interactive modules across Baseline, Foundation, Growth, Horizons, and Synthesis.
- **Hybrid Deterministic + Monte Carlo Engine:** Exact deterministic math for budgeting, debt, taxes, and portfolio rebalancing, paired with fast seeded **1,000-trial Monte Carlo simulations** (showing probability of success + 10th / 50th / 90th percentile bands alongside deterministic baselines) for Retirement, FIRE, Goals, and Scenario Comparisons.
- **SQLite Persistence (`data/ai_finance.db`)** with user accounts (seeded default `user` / `password` plus registration), saved plans, and per-module history.
- **Professional 9-Page PDF Reports (`FINANCE-PLAN.pdf`)** generated via ReportLab with score gauges, category bars, allocation pie charts, payoff timelines, Monte Carlo retirement stress tests, and a 90-day action plan.
- **Single-Port Docker & Cross-Platform Launchers** for macOS, Linux, and Windows.

---

## 🚀 Quick Start

### 1. Clone the Repository
```bash
git clone https://github.com/pmishra02138/ai-finance.git
cd ai-finance
```

### 2. Start the Web App (Port `8787`)

**macOS / Linux (local `uv`):**
```bash
./bin/start.sh
```

**macOS / Linux (Docker):**
```bash
./bin/start.sh --docker
```

**Windows (PowerShell):**
```powershell
.\bin\start.ps1
# or with Docker:
.\bin\start.ps1 -Docker
```

Open **`http://localhost:8787`** in your browser and sign in with **`user`** / **`password`** (or register a new account).

**Stop the server:**
- macOS / Linux: `./bin/stop.sh`
- Windows: `.\bin\stop.ps1`

---

## 🧭 5-Stage Planning Workflow (14 Modules)

| Stage | Modules | Engine | What You Can Analyze |
| :--- | :--- | :--- | :--- |
| **1. Baseline & Triage** | Quick Snapshot, Net Worth Tracker | Deterministic | Savings rate, DTI, reserve coverage, balance sheet, Millionaire Next Door tier, wealth milestones |
| **2. Foundation & Defense** | Budget & Cash Flow, Emergency Fund, Debt Payoff | Deterministic | 50/30/20 split, target runway (3–12 months), Avalanche vs. Snowball payoff comparison |
| **3. Growth & Optimization** | Portfolio Review, Investment Screener, Tax Optimization | Deterministic | Age-based allocation drift & rebalancing trades, model ETF strategies, 401(k)/HSA/IRA + age 50+ catch-up savings |
| **4. Horizons & Trade-Offs** | Retirement Planner, FIRE Calculator, Goal Planner, Scenario Compare | **Deterministic + Monte Carlo** | Baseline projections side-by-side with 1,000-trial survival/win probabilities and 10th/50th/90th percentile outcomes |
| **5. Synthesis & Export** | Full Health Analysis, PDF Report Export | Deterministic | Composite Financial Health Score (0–100), letter grade (`A+`–`F`), and 9-page `FINANCE-PLAN.pdf` export |

Clicking **Run & Sync to Plan** in any module updates your master plan in SQLite and automatically recalculates your overall Financial Health Score, grade, and signal.

---

## 📄 Standalone PDF Generation & Testing

### Generate a Sample PDF Directly
```bash
uv sync --no-install-project --no-dev
uv run --no-sync python scripts/generate_finance_pdf.py --demo
# → FINANCE-PLAN-sample.pdf
```

Or using a custom JSON file:
```bash
uv run --no-sync python scripts/generate_finance_pdf.py --data plan.json --output FINANCE-PLAN.pdf
```

### Run the Test Suite
```bash
uv run --no-sync python -m unittest discover -s tests -v
```

---

## 🏗️ Project Structure

```text
ai-finance/
├── bin/                         # Cross-platform start/stop scripts
│   ├── start.sh / stop.sh       # macOS & Linux launchers
│   └── start.ps1 / stop.ps1     # Windows PowerShell launchers
├── docs/
│   ├── FINANCIAL_SPEC.md        # Plain-English spec of all 14 modules, formulas & Monte Carlo rules
│   └── WORKFLOW.md              # Visual Mermaid diagrams (5-stage workflow, architecture, data flow)
├── specs/                       # Machine-readable runtime specs for UI forms & constants
│   ├── baseline.json            # Stage 1 specs
│   ├── foundation.json          # Stage 2 specs
│   ├── growth.json              # Stage 3 specs (incl. IRS limits)
│   ├── horizons.json            # Stage 4 specs (incl. Monte Carlo defaults)
│   └── synthesis.json           # Stage 5 specs
├── frontend/public/             # Spec-driven static SPA (index.html, styles.css, app.js, skills.js, charts.js)
├── scripts/
│   ├── server.py                # Unified single-port FastAPI + static frontend server (8787)
│   ├── db.py                    # SQLite persistence (users, sessions, financial_plans, skill_runs)
│   ├── scoring.py               # Shared score-to-grade and signal helpers (pure stdlib)
│   ├── skill_registry.py        # Loader reading specs/*.json for API & calculators
│   ├── generate_finance_pdf.py  # Thin CLI entrypoint for 9-page PDF export
│   ├── calculators/             # Stage-grouped calculation engine (14 modules)
│   │   ├── __init__.py          # CALCULATORS registry & run_skill() dispatcher
│   │   ├── common.py            # Shared math, formatting, and compounding helpers
│   │   ├── monte_carlo.py       # Pure-stdlib seeded Monte Carlo simulation engine
│   │   ├── baseline.py          # Stage 1: Quick Snapshot, Net Worth
│   │   ├── foundation.py        # Stage 2: Budget, Emergency Fund, Debt Payoff
│   │   ├── growth.py            # Stage 3: Portfolio, Screener, Taxes
│   │   ├── horizons.py          # Stage 4: Retirement, FIRE, Goals, Compare (Hybrid MC)
│   │   └── synthesis.py         # Stage 5: Full Health Analysis, PDF Readiness
│   └── pdf/                     # Modular ReportLab 9-page PDF generator
│       ├── __init__.py          # Package exports (build_pdf, _demo_data)
│       ├── theme.py             # Palette, paragraph styles, page geometry, footer
│       ├── components.py        # Gauge, category bars, pie chart, XML escaping
│       ├── pages.py             # 9 page builders (incl. Monte Carlo stress test)
│       └── demo_data.py         # Internally consistent sample plan payload
├── tests/
│   ├── test_calculators.py      # Unit tests for specs, deterministic & Monte Carlo calculators
│   └── test_e2e.py              # Full-stack E2E tests (Specs, DB, Auth, API, UI, PDF, Docker)
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
├── requirements.txt
├── AGENTS.md
└── README.md
```

---

## 📜 License

[MIT License](LICENSE) — Free to use and modify.

---

## ⚠️ Disclaimer

**This software is NOT financial advice.**

This tool is provided for informational and educational purposes only. The Financial Health Score, projections, Monte Carlo simulations, recommendations, and any output generated by this software are based on inputs provided by the user and general financial principles, and should NOT be relied upon as a substitute for personalized advice from:

- A **licensed financial advisor** (CFP, CFA, fiduciary)
- A **Certified Public Accountant (CPA)** for tax matters
- An **attorney** for estate, legal, or contractual matters
- An **insurance professional** for coverage decisions

**Past performance does not guarantee future results.** Projections and simulations involve assumptions about market returns, volatility, inflation, and personal circumstances that may not match real-world outcomes.

---

## 🙏 Acknowledgments

Originally inspired by [zubair-trabzada/ai-finance-claude](https://github.com/zubair-trabzada/ai-finance-claude).
