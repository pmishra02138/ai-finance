# Financial Modeling & Module Specification (`ai-finance`)

> **Human-readable specification** for all 5 stages and 14 financial modules in `ai-finance`.
>
> - **Runtime UI & Constants:** Driven by machine-readable `specs/*.json` (served via `/api/skills`).
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

## 2. Engine Strategy: Deterministic vs. Hybrid Monte Carlo

- **Deterministic (Stages 1, 2, 3, and 5):** Used wherever exact accounting, tax rules, or fixed-APR amortization apply. Zero randomness.
- **Hybrid Deterministic + Monte Carlo (Stage 4):** Displays a clean **deterministic baseline** side-by-side with a **1,000-trial seeded Monte Carlo simulation** (`scripts/calculators/monte_carlo.py`, default seed `42` for reproducibility):
  - Annual returns are drawn from a normal distribution `N(mean, volatility)`, floored at `-65%` in any single year to prevent impossible negative portfolio values.
  - Reports **probability of success / survival** plus **10th percentile (downside)**, **50th percentile (median)**, and **90th percentile (upside)** outcomes.
  - Runs in ~15–25 ms in pure Python stdlib with zero external dependencies.

---

## 3. Stage-by-Stage Module Specifications

### Stage 1: Baseline & Triage (`specs/baseline.json` → `calculators/baseline.py`)

#### 1.1 Quick Snapshot (`finance-quick`) — *Deterministic*
- **Inputs:** Monthly Income, Monthly Expenses, Total Savings & Investments, Total Debt, Current Age, Target Retirement Age.
- **Core Math:**
  - `Monthly Surplus = Income − Expenses`
  - `Savings Rate = Surplus / Income × 100`
  - `Debt-to-Annual-Income (DTI) = Total Debt / (Income × 12) × 100`
  - `Reserve Coverage = Total Savings / Monthly Expenses` (months)
  - `Retirement Projection`: Compounded monthly at `6%` real return assuming `50%` of positive monthly surplus is invested, compared against `25 × Annual Expenses`.
- **Score (0–100):** Up to `35 pts` (savings rate) + `25 pts` (reserve coverage) + `20 pts` (low DTI) + `20 pts` (retirement on-track %).
- **Plan Sync:** Updates `health_score`, `grade`, `signal`, `cash_flow.monthly_income`, `retirement.current_age`, and `retirement.retirement_age`.

#### 1.2 Net Worth Tracker (`finance-networth`) — *Deterministic*
- **Inputs:** Cash, Investments & Retirement, Real Estate, Other Assets, Mortgage Debt, Other Debts, Current Age, Gross Annual Income.
- **Core Math:**
  - `Net Worth = Total Assets − Total Liabilities`
  - **Millionaire Next Door (MND) Benchmark:** `Expected Net Worth = (Age × Annual Income) / 10`.
    - `>= 2.0×`: Prodigious Accumulator (PAW)
    - `1.0× – 1.99×`: Average Accumulator (AAW)
    - `< 1.0×`: Under Accumulator (UAW)
  - Tracks distance to the next milestone (`$100k`, `$250k`, `$500k`, `$1M`, `$5M`, `$10M`).
- **Score (0–100):** `clamp(40 + MND Ratio × 35)`.
- **Plan Sync:** Updates `investments.total_value`.

---

### Stage 2: Foundation & Defense (`specs/foundation.json` → `calculators/foundation.py`)

#### 2.1 Budget & Cash Flow (`finance-budget`) — *Deterministic*
- **Inputs:** Monthly Income, Monthly Essential Needs, Monthly Discretionary Wants.
- **Core Math (50/30/20 Framework):**
  - `Savings & Extra Debt = Income − Needs − Wants`
  - Benchmarks: Needs `<= 50%`, Wants `<= 30%`, Savings `>= 20%`.
- **Score (0–100):** Up to `40 pts` (savings `>= 20%`) + `35 pts` (needs `<= 50%`) + `25 pts` (wants `<= 30%`).
- **Plan Sync:** Updates `categories.cash_flow`, `cash_flow.monthly_income`, `cash_flow.budget_50_30_20`, and preserves any existing itemized `cash_flow.expenses` list (does not overwrite detailed line items).

#### 2.2 Emergency Fund (`finance-emergency`) — *Deterministic*
- **Inputs:** Monthly Essential Expenses, Current Emergency Fund, Monthly Addition, Income Stability (`stable` / `variable` / `high_risk`), Dependents, Self-Employed flag.
- **Core Math:**
  - Base target: `3` mos (stable), `6` mos (variable), `9` mos (high risk).
  - Add `+2` mos if dependents `> 0`; add `+3` mos if self-employed; clamped to `3–12` months.
  - `Target Fund = Target Months × Monthly Essential Expenses`.
  - `Months to Goal = ceil((Target − Current) / Monthly Addition)`.
- **Score (0–100):** `clamp(Current Fund / Target Fund × 100)`.
- **Plan Sync:** Updates `categories.protection` (`max(40, score × 0.8 + 15)`).

#### 2.3 Debt Payoff (`finance-debt`) — *Deterministic*
- **Inputs:** Extra Monthly Payment, list of Debt Accounts (`name`, `balance`, `apr`, `min_payment`).
- **Core Math:**
  - Month-by-month amortization (up to 600 months) comparing **Avalanche** (highest APR first) vs. **Snowball** (smallest balance first), automatically rolling paid-off minimum payments into the next target account.
  - Calculates months to debt-free, total interest for both strategies, interest saved, and exact payoff order.
- **Score (0–100):** `100` if debt-free; otherwise `clamp(95 − Weighted APR × 2.2 − min(35, Avalanche Months × 0.45))`.
- **Plan Sync:** Updates `categories.debt` and `debt` (`strategy`, `payoff_months`, `total_interest`, `accounts`).

---

### Stage 3: Growth & Optimization (`specs/growth.json` → `calculators/growth.py`)

#### 3.1 Portfolio Review (`finance-portfolio`) — *Deterministic*
- **Inputs:** Total Invested Value, Current Age, Weighted Expense Ratio (%), and current % weights for US Stocks, International Stocks, Bonds, REITs, and Cash.
- **Core Math:**
  - Age-based target equity: `clamp(110 − Age, 30, 90)` split `70%` US / `30%` International; REITs `3%`; remaining allocated to Bonds (min `5%`) and Cash.
  - Flags a warning and score penalty if input weights do not sum to `100%` (±`0.5%`).
  - Computes exact Buy/Trim dollar trades and annual fee drag (`Value × ER%`).
- **Score (0–100):** `clamp(95 − Max Drift × 1.8 − Fee Penalty − Sum Penalty)`.
- **Plan Sync:** Updates `categories.investments` and `investments` (`total_value`, `allocation`).

#### 3.2 Investment Screener (`finance-screen`) — *Deterministic*
- **Inputs:** Strategy (`3-fund`, `dividend`, `bonds`, `reits`, `esg`) and Amount to Allocate.
- **Core Math:** Maps the chosen model ETF portfolio weights into exact dollar allocations and displays expected nominal return and weighted expense ratio.
- **Score:** Informational (`None`). No plan patch.

#### 3.3 Tax Optimization (`finance-taxes`) — *Deterministic*
- **Inputs:** Age, Gross Annual Income, Marginal Federal Tax Bracket (%), Current 401(k) / HSA / IRA contributions, Harvestable Capital Losses, HDHP/HSA eligibility, Family HSA coverage.
- **Core Math (limits read from `specs/growth.json`):**
  - 401(k) limit: `$23,500` (`+$7,500` catch-up at age `50+`).
  - HSA limit (if eligible): `$4,300` single / `$8,550` family (`+$1,000` catch-up at age `55+`).
  - IRA limit: `$7,000` (`+$1,000` catch-up at age `50+`).
  - Estimated tax savings: `Unused 401(k) × Marginal Rate` + `Unused HSA × (Marginal Rate + 7.65% FICA)` + `min($3,000, Harvestable Losses) × Marginal Rate`.
- **Score (0–100):** `clamp(Total Used Space / Total Available Space × 100)`.

---

### Stage 4: Horizons & Trade-Offs (`specs/horizons.json` → `calculators/horizons.py`)

All four modules in Stage 4 run **both** a deterministic baseline and a **1,000-trial seeded Monte Carlo simulation**, rendered side-by-side in the UI.

#### 4.1 Retirement Planner (`finance-retirement`) — *Deterministic + Monte Carlo*
- **Inputs:** Current Age, Target Retirement Age, Current Balance, Monthly Contribution, Desired Annual Retirement Spend, Expected Annual Social Security.
- **Deterministic Baseline:**
  - `Net Annual Need = max(0, Desired Spend − Social Security)`
  - `25× Target Nest Egg = Net Annual Need × 25`
  - Monthly-compounded projections at `5%` (Conservative), `6%` (Moderate baseline), `7%` (Aggressive), plus `+$200/mo` and `+$400/mo` sensitivity scenarios.
- **Monte Carlo Stress Test (1,000 trials):**
  - Accumulation phase (`6.0%` mean real return, `14.0%` volatility) followed by a **30-year drawdown phase** (`4.5%` mean return, `10.0%` volatility) withdrawing `Net Annual Need` annually.
  - Reports **30-Yr Survival Probability (%)** and **10th / 50th / 90th percentile** nest egg at retirement.
- **Score (0–100):** `clamp(Baseline 6% Projection / Target × 100)`.
- **Plan Sync:** Updates `categories.retirement` and `retirement` (including `monte_carlo` stats, which also appear on Page 6 of the PDF).

#### 4.2 FIRE Calculator (`finance-fire`) — *Deterministic + Monte Carlo*
- **Inputs:** Annual Expenses, Current Invested Portfolio, Annual Savings, Safe Withdrawal Rate (`2%–6%`, default `4%`), Expected Real Return (%), Current Age.
- **Deterministic Baseline:**
  - `Regular FI = Annual Expenses / SWR`
  - `Lean FI = 75% × Regular FI`, `Fat FI = 150% × Regular FI`
  - `Coast FI = Regular FI / (1 + r)^(65 − Age)`
  - Simulates years to reach Regular FI at steady annual return.
- **Monte Carlo Stress Test (1,000 trials):**
  - Tests starting at `Regular FI` and withdrawing `Annual Expenses` over a **40-year early-retirement horizon** (`14%` volatility), reporting **40-Yr Survival Probability (%)** and ending-balance percentiles.
- **Score (0–100):** `clamp(Current Invested / Regular FI × 100)`.

#### 4.3 Goal Planner (`finance-goals`) — *Deterministic + Monte Carlo*
- **Inputs:** Goal Name, Target Amount, Currently Saved, Years Until Goal, Expected Annual Return (%).
- **Deterministic Baseline:** Exact required monthly contribution to close the future-value shortfall, plus a `+2 years` timeline scenario and horizon-appropriate vehicle recommendation (`< 3 yrs`: HYSA/T-Bills; `3–7 yrs`: Balanced 40/60; `> 7 yrs`: Diversified Index ETFs).
- **Monte Carlo Stress Test (1,000 trials):**
  - Simulates saving the deterministic monthly amount under vehicle-matched volatility (`1.5%` short, `7.5%` medium, `13%` long) to report **On-Time Goal Probability (%)** and 10th/50th/90th percentile ending values.

#### 4.4 Scenario Compare (`finance-compare`) — *Deterministic + Monte Carlo*
- **Inputs:** Scenario A & B names, upfront costs, monthly costs, monthly investments, Horizon (years), Expected Return (%).
- **Deterministic Baseline:** Invests the upfront cost difference + monthly investment amounts at steady return, comparing `Net Position = Invested FV − Total Cash Cost`.
- **Monte Carlo Stress Test (1,000 trials):**
  - Runs both scenarios along **shared** randomized annual market paths (`14%` volatility) so they face identical market conditions each trial, reporting **Monte Carlo Win Probability (%)** and median/percentile invested values.

---

### Stage 5: Synthesis & Export (`specs/synthesis.json` → `calculators/synthesis.py`)

#### 5.1 Full Health Analysis (`finance-analyze`) — *Deterministic*
- **Inputs:** 5 pillar scores (`Cash Flow`, `Debt`, `Investments`, `Retirement`, `Protection`), pre-filled from the synced plan.
- **Core Math:** Equal-weighted average (`20%` each) of the 5 pillars → Composite Score, Grade, Signal, Strongest Pillar, and Priority Gap.
- **Plan Sync:** Updates `health_score`, `grade`, `signal`, and all 5 `categories`. *(Note: syncing any individual category module in Stages 2–4 also triggers automatic composite score recalculation in `scripts/server.py`.)*

#### 5.2 PDF Report Export (`finance-report-pdf`) — *Deterministic*
- Summarizes readiness of the active synced plan and triggers ReportLab rendering of the **9-page `FINANCE-PLAN.pdf`** (`scripts/pdf/pages.py`):
  1. Cover Page (Score Gauge, Grade, Signal, Executive Summary)
  2. 5-Pillar Score Dashboard & Category Notes
  3. Cash Flow Analysis & Expense Breakdown
  4. Debt Summary, Account Table & Payoff Timeline
  5. Investment Allocation Pie Chart & Target Variance
  6. Retirement Projection, Scenarios & **Monte Carlo Stress Test**
  7. Protection Scorecard
  8. Top 10 Prioritized Action Items
  9. 90-Day Action Plan & Disclaimer
