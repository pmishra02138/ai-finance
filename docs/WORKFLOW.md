# Visual Workflow & Architecture Guide (`ai-finance`)

> Visual overview of how users move through the 5-stage planning workflow, how `specs/*.json` powers both the UI and backend, and how Deterministic + Monte Carlo calculations sync into SQLite and the 9-page PDF report.
>
> For detailed formulas and scoring rules, see [FINANCIAL_SPEC.md](FINANCIAL_SPEC.md).

---

## 1. 5-Stage Guided User Workflow

Users can work top-to-bottom or jump to any module. Clicking **Run & Sync to Plan** saves that module's inputs/results, patches the active financial plan in SQLite, and automatically recalculates the composite Financial Health Score.

```mermaid
flowchart LR
    Login["Sign In / Register\n(user / password)"] --> SelectPlan["Select or Create\nFinancial Plan"]

    SelectPlan --> S1["Stage 1: Baseline\n• Quick Snapshot\n• Net Worth Tracker"]
    S1 --> S2["Stage 2: Foundation\n• Budget 50/30/20\n• Emergency Fund\n• Debt Payoff"]
    S2 --> S3["Stage 3: Growth\n• Portfolio Review\n• Investment Screener\n• Tax Optimization"]
    S3 --> S4["Stage 4: Horizons (MC)\n• Retirement Planner\n• FIRE Calculator\n• Goal Planner\n• Scenario Compare"]
    S4 --> S5["Stage 5: Synthesis\n• Full Health Analysis\n• PDF Report Export"]

    S1 -. "Run & Sync" .-> MasterPlan[("Master Plan in SQLite\n(Auto-recalculates Score)")]
    S2 -. "Run & Sync" .-> MasterPlan
    S3 -. "Run & Sync" .-> MasterPlan
    S4 -. "Run & Sync" .-> MasterPlan
    MasterPlan --> S5
    S5 --> PDF["9-Page FINANCE-PLAN.pdf\n(Preview or Download)"]
```

---

## 2. System Architecture & Single Source of Truth

Everything runs on a **single port (`http://localhost:8787`)** via FastAPI + Uvicorn. The 5 JSON files in `specs/` drive both the dynamic browser forms and backend domain constants, while calculations are split cleanly between deterministic math and pure-stdlib Monte Carlo simulations.

```mermaid
flowchart TD
    Specs["specs/*.json\n(Stages, Form Fields, IRS Limits, MC Defaults)"]

    subgraph Backend ["FastAPI Server — scripts/server.py (:8787)"]
        Registry["scripts/skill_registry.py\n(/api/skills & Constants)"]
        Router["REST API Router\n(/api/auth, /api/plans, /api/skills)"]
        DetCalc["Deterministic Calculators\nbaseline.py • foundation.py\ngrowth.py • synthesis.py"]
        MCCalc["Hybrid Monte Carlo Calculators\nhorizons.py + monte_carlo.py\n(1,000 seeded trials)"]
        Scoring["scripts/scoring.py\n(Grade A+..F & Signal)"]
        PDFPkg["scripts/pdf/\ntheme • components • pages • demo_data"]
        DB["scripts/db.py\n(SQLite WAL Persistence)"]
    end

    subgraph Frontend ["Static SPA — frontend/public/"]
        AppJS["app.js\n(Auth, Plan Switcher, Navigation)"]
        SkillsJS["skills.js\n(Dynamic Forms + Baseline vs. MC Panel)"]
        ChartsJS["charts.js\n(Inline SVG Gauge, Bars, Donuts)"]
    end

    SQLite[("data/ai_finance.db\nusers • sessions • financial_plans • skill_runs")]
    PDFOut["9-Page FINANCE-PLAN.pdf"]

    Specs --> Registry
    Specs --> DetCalc
    Specs --> MCCalc

    Registry --> Router
    AppJS <--> Router
    SkillsJS <--> Router
    SkillsJS --> ChartsJS

    Router --> DetCalc
    Router --> MCCalc
    DetCalc --> Scoring
    MCCalc --> Scoring
    Router --> DB
    DB <--> SQLite
    Router --> PDFPkg
    PDFPkg --> PDFOut
```

---

## 3. Run & Sync + PDF Export Lifecycle

What happens step-by-step when a user runs a Stage 4 module (such as **Retirement Planner**) with **Run & Sync to Plan**, then exports their PDF report:

```mermaid
sequenceDiagram
    actor User
    participant UI as Browser SPA (skills.js / app.js)
    participant API as FastAPI (scripts/server.py)
    participant Calc as Calculators (horizons.py + monte_carlo.py)
    participant DB as SQLite (scripts/db.py)
    participant PDF as ReportLab (scripts/pdf/pages.py)

    User->>UI: Edits Retirement inputs & clicks "Run & Sync to Plan"
    UI->>API: POST /api/plans/{id}/skills/finance-retirement/run (sync_to_plan=true)
    API->>DB: Load active financial plan payload
    API->>Calc: run_skill("finance-retirement", inputs, payload)
    Calc->>Calc: Compute deterministic 5%/6%/7% baselines
    Calc->>Calc: Run 1,000-trial Monte Carlo (30-yr drawdown, ~20 ms)
    Calc-->>API: Result (metrics, monte_carlo, chart, tables, plan_patch)
    API->>DB: Upsert skill_runs row
    API->>API: Merge plan_patch & recalculate composite health_score + grade
    API->>DB: Update financial_plans row
    API-->>UI: Return {run, result, updated_plan}
    UI->>UI: Render Baseline vs. MC panel, SVG chart, & updated gauge

    User->>UI: Clicks "Download PDF"
    UI->>API: GET /api/plans/{id}/pdf
    API->>DB: Fetch latest synced plan payload
    API->>PDF: build_pdf(payload) (includes Page 6 MC Stress Test)
    PDF-->>API: 9-page PDF bytes
    API-->>UI: application/pdf download (FINANCE-PLAN-{id}.pdf)
```

---

## 4. How to Update Rules or Add Fields

```mermaid
flowchart LR
    Edit["1. Update docs/FINANCIAL_SPEC.md\n(Plain-English requirement)"] --> Spec["2. Update specs/*.json\n(Form fields / constants)"]
    Spec --> Code["3. Update scripts/calculators/\n(Formula or MC logic if needed)"]
    Code --> Test["4. Run unittest suite\n(tests/test_calculators.py + test_e2e.py)"]
```
