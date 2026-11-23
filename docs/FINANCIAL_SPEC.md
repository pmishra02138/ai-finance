# Financial Modeling & Module Specification (`ai-finance`)

> **Human-readable specification** for all 5 stages and 14 financial modules in `ai-finance`.
>
> - **Runtime UI & Constants:** Driven by machine-readable `specs/*.json` (served via `/api/modules`).
> - **Calculation Engine:** Implemented in `scripts/calculators/` and `scripts/scoring.py`.
> - **How to request changes:** Edit this document (or describe your change in plain English) and ask to sync — the spec, `specs/*.json`, Python calculators, and tests are updated together.
>
> ⚠️ **Educational Disclaimer:** All formulas, scores, and Monte Carlo simulations are for informational and educational purposes only and do **not** constitute financial, investment, tax, or legal advice.

---

## 1. Global Scoring & Grading Rules (`scripts/scoring.py`)

Every scored module and the composite Financial Health Score map a `0–100` number to a letter grade and status signal:

| Score Range | Grade | Status Signal | UI / PDF Color |
| :--- | :---: | :--- | :--- |
| `90 – 100` | `A+` | Excellent — On Track | Green (`>= 70`) |
| `85 – 89.9` | `A` | Excellent — On Track | Green |
| `80 – 84.9` | `A-` | Excellent — On Track | Green |
| `75 – 79.9` | `B+` | Healthy — Minor Tune-Up | Green |
| `70 – 74.9` | `B` | Healthy — Minor Tune-Up | Green |
| `65 – 69.9` | `B-` | Healthy — Minor Tune-Up | Amber (`40 – 69.9`) |
| `60 – 64.9` | `C+` | Fair — Action Needed | Amber |
| `55 – 59.9` | `C` | Fair — Action Needed | Amber |
| `50 – 54.9` | `C-` | Fair — Action Needed | Amber |
| `45 – 49.9` | `D+` | Weak — Plan Required | Amber |
| `40 – 44.9` | `D` | Weak — Plan Required | Amber |
| `< 40` | `F` | Weak (`>=35`) / Critical (`<35`) | Red (`< 40`) |

---

## 2. Core Modeling Principles

- **Gross vs. Net Income Separation:** Cash-flow and budgeting modules (`Quick Snapshot`, `Budget`) use **monthly net take-home pay** (`cash_flow.monthly_income`), while `Net Worth` and `Tax Optimization` use **pre-tax gross annual income** (`cash_flow.gross_annual_income`).
- **Deterministic Where Exact (Stages 1, 2, 3, 5):** Exact accounting, IRS limits, fixed-APR amortization, rebalancing trades, and weighted insurance/estate scorecards.
- **Hybrid Deterministic + Log-Normal Monte Carlo (Stage 4):** Displays a deterministic baseline side-by-side with a **1,000-trial seeded log-normal Monte Carlo simulation** (`scripts/calculators/monte_carlo.py`, default seed `42`):
  - Annual returns use log-normal compounding `exp((ln(1 + r) - 0.5*σ²) + σ*Z) - 1` (floored at `-65%`) to avoid arithmetic-mean drift over 30–40 year horizons.
  - Expected real return and volatility are **dynamically linked** to the user's synced equity/bond allocation from `Portfolio Review & Models` (`0%` equity → `3.0%` real return / `4.5%` vol; `100%` equity → `7.5%` real return / `17.0%` vol).
  - Reports **survival / win probability (%)** plus **10th (downside)**, **50th (median)**, and **90th (upside)** percentile outcomes in ~15–25 ms.

---

## 3. Stage-by-Stage Module Specifications

### Stage 1: Baseline & Triage (`specs/baseline.json` → `calculators/baseline.py`)

#### 1.1 Quick Snapshot (`finance-quick`) — *Deterministic*
- **Inputs:** Monthly Take-Home Pay, Monthly Expenses, **Liquid Cash & Emergency Savings**, **Invested & Retirement Savings**, Total Debt, Current Age, Target Retirement Age.
- **Core Math:** Separates liquid cash (used for Reserve Coverage in months) from invested savings (compounded at `6%` real return for retirement projection) so illiquid retirement accounts never overstate emergency liquidity.
- **Score Protection:** Never overwrites an already-synced detailed 5-pillar `health_score` — only sets `health_score` on brand-new plans without detailed category scores.

#### 1.2 Net Worth Tracker (`finance-networth`) — *Deterministic*
- **Inputs:** Cash, Investments & Retirement, Real Estate, Other Assets, Mortgage, Other Debts, Current Age, **Gross Annual Income (Pre-Tax)**.
- **Core Math:** `Net Worth = Assets − Liabilities`, benchmarked against *Millionaire Next Door* (`Age × Gross Annual Income / 10` for age `>= 35`; early-career ramp `max(0.25, (Age − 22) × 0.15) × Income` under age `35`) and next wealth milestone (`$100k`–`$10M`).
- **Plan Sync:** Updates `investments.total_value` and `cash_flow.gross_annual_income`.

---

### Stage 2: Foundation & Defense (`specs/foundation.json` → `calculators/foundation.py`)

#### 2.1 Budget & Cash Flow (`finance-budget`) — *Deterministic*
- **Inputs:** Monthly Take-Home Pay, Monthly Essential Needs, Monthly Discretionary Wants.
- **Core Math:** 50/30/20 split (`Needs <= 50%`, `Wants <= 30%`, `Savings >= 20%`).
- **Plan Sync:** Updates `categories.cash_flow`, `cash_flow.monthly_income`, `cash_flow.budget_50_30_20`, while preserving any existing itemized `cash_flow.expenses`.

#### 2.2 Emergency Fund (`finance-emergency`) — *Deterministic*
- **Inputs:** Monthly Essential Expenses, Current Emergency Fund, Monthly Addition, Income Stability (`stable` / `variable` / `high_risk`), Dependents, Self-Employed flag.
- **Core Math:** Target `3–12` months based on stability (`3/6/9`), `+2` mos for dependents, `+3` mos if self-employed.
- **Plan Sync:** Updates `protection.emergency_fund_months` (feeding into `Protection & Estate`).

#### 2.3 Debt Payoff (`finance-debt`) — *Deterministic*
- **Inputs:** Extra Monthly Payment, Debt Accounts (`name`, `balance`, `apr`, `min_payment`).
- **Core Math:** Month-by-month Avalanche vs. Snowball amortization with minimum-payment rollover.
- **High-APR vs. Low-APR & Negative Amortization:** Separates high-APR (`> 7%`), mid-APR (`5–7%`), and low-APR (`<= 5%`, e.g., 3% fixed mortgage) debt so low-rate amortized loans aren't unfairly penalized, and flags **Negative Amortization** whenever minimum payments fail to cover monthly interest.
- **Plan Sync:** Updates `categories.debt` and `debt`.

#### 2.4 Protection & Estate (`finance-protection`) — *Deterministic*
- **Inputs:** Status (`Good` / `Partial` / `Missing`) for **Term Life Insurance**, **Disability Insurance (LTD)**, **Health Insurance**, **Umbrella / Liability**, **Will, POA & Beneficiaries**, plus **Emergency Fund Coverage (Months)**.
- **Core Math (Weighted 0–100 Protection Pillar):** Estate Docs `25%` + Disability `20%` + Term Life `18%` + Health `15%` + Emergency Fund `12%` + Umbrella `10%`.
- **Plan Sync:** Updates `categories.protection` and populates `protection.items` + `protection.commentary` directly for Page 7 of the PDF report.

---

### Stage 3: Growth & Optimization (`specs/growth.json` → `calculators/growth.py`)

#### 3.1 Portfolio Review & Models (`finance-portfolio`) — *Deterministic*
- **Inputs:** Total Invested Value, Current Age, Weighted Expense Ratio (%), current % weights (US Stocks, Intl Stocks, Bonds, REITs, Cash), and **Reference Model ETF Template** (`3-fund`, `dividend`, `bonds`, `reits`, `esg`).
- **Core Math:** Age-based target equity (`clamp(110 − Age, 30, 90)`), flags non-100% allocation sums, computes exact Buy/Trim rebalancing trades and annual fee drag, and renders the chosen Model ETF dollar allocation table side-by-side.
- **Plan Sync:** Updates `categories.investments` and `investments.allocation` (which also calibrates Stage 4 Monte Carlo expected return & volatility).

#### 3.2 Tax Optimization (`finance-taxes`) — *Deterministic*
- **Inputs:** **Tax Filing Status** (`single` / `married`), Age, **Gross Annual Income (Pre-Tax)**, Marginal Federal Tax Bracket (%), current 401(k) / HSA / IRA contributions, Harvestable Capital Losses, HDHP/HSA eligibility, Family HSA coverage.
- **Core Math (IRS limits from `specs/growth.json`):**
  - 401(k): `$23,500` (`+$7,500` at age `50+`)
  - HSA: `$4,300` single / `$8,550` family (`+$1,000` at age `55+`)
  - IRA: `$7,000` (`+$1,000` at age `50+`), **doubled for Married Filing Jointly** (spousal IRA)
  - Adds Roth vs. Traditional guidance when marginal bracket `<= 12%`.
- **Plan Sync:** Updates `cash_flow.gross_annual_income`.

---

### Stage 4: Horizons & Trade-Offs (`specs/horizons.json` → `calculators/horizons.py`)

#### 4.1 Retirement Planner (`finance-retirement`) — *Deterministic + Log-Normal Monte Carlo*
- **Inputs:** Current Age, Retirement Age, Current Balance, Monthly Contribution, **Monthly Employer 401(k) Match**, Desired After-Tax Annual Spend, **Effective Retirement Tax Rate (%)**, Expected Annual Social Security, **Social Security Start Age**.
- **Deterministic Baseline:** Grosses up spending for withdrawal taxes (`Net Spend / (1 − Tax Rate)`), adds bridge funding for years between `retirement_age` and `social_security_start_age`, and models `5%` / `6%` / `7%` + `+$200/$400` scenarios including employer match.
- **Monte Carlo Stress Test (1,000 trials):** Portfolio-linked log-normal accumulation + dynamic drawdown (`max(25, 95 − Retirement Age)` years) where Social Security begins only at `social_security_start_age`. Retirement score blends deterministic fundedness (`45%`) and Monte Carlo survival (`55%`, capped at `79` if survival `< 80%`).
- **Plan Sync:** Updates `categories.retirement` and `retirement` (including `monte_carlo` stats for PDF Page 6).

#### 4.2 FIRE Calculator (`finance-fire`) — *Deterministic + Log-Normal Monte Carlo*
- **Inputs:** Expected After-Tax Annual Expenses, **Effective Tax Rate on Withdrawals (%)**, Current Invested Portfolio, Annual Savings, **Safe Withdrawal Rate (SWR, %)**, Expected Real Return (%), Current Age.
- **Deterministic Baseline:** Tax-adjusted Lean (75%), Regular (100%), Fat (150%), and Coast FI targets + years to FI.
- **Monte Carlo Stress Test (1,000 trials):** Portfolio-linked log-normal 40-year early-retirement survival simulation.

#### 4.3 Goal Planner (`finance-goals`) — *Deterministic + Log-Normal Monte Carlo*
- **Inputs:** Goal Name, Target Amount, Currently Saved, Years Until Goal, Expected Annual Return (%).
- **Deterministic + MC:** Exact required monthly contribution, an **80% Monte Carlo Confidence Save** solved via binary search, horizon-matched investment vehicle, and 10th/50th/90th percentile ending values.

#### 4.4 Scenario Compare (`finance-compare`) — *Deterministic + Log-Normal Monte Carlo*
- **Inputs:** Scenario A & B names, upfront costs, monthly costs, monthly investments, **Ending Asset Equity (e.g., Home Equity)**, Horizon (years), Expected Return (%).
- **Core Math:** `Net Position = Invested FV + Ending Asset Equity − Total Cash Cost`, paired with shared-path log-normal Monte Carlo win probability so Rent vs. Buy comparisons account for home equity fairly.

---

### Stage 5: Synthesis & Export (`specs/synthesis.json` → `calculators/synthesis.py`)

#### 5.1 Full Health Analysis (`finance-analyze`) — *Deterministic*
- Equal-weighted (`20%` each) composite of all 5 pillars (`Cash Flow`, `Debt`, `Investments`, `Retirement`, `Protection`), read-only and auto-synced from your saved modules.
- Displays the full **Financial Health Score** gauge banner and **Preview PDF / Download PDF** buttons for exporting the **9-page `FINANCE-PLAN.pdf`** (`scripts/pdf/pages.py`), including the live synced Protection Scorecard (Page 7) and Retirement Monte Carlo Stress Test (Page 6).
