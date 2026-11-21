# Extensive Codebase Review — `ai-finance`

**Date:** 2026-11-20  
**Scope:** Complete full-stack codebase (~6,360 lines across Python backend, SQLite layer, 14 deterministic calculators, ReportLab PDF engine, Node.js proxy & SPA frontend, Docker configs, cross-platform shell/PowerShell scripts, 15 AGY skills, and test suites).  
**Baseline Verification:** 16/16 automated tests (`tests/test_calculators.py`, `tests/test_e2e.py`) passing (`OK` in ~1.3s), Python `py_compile`, Bash `bash -n`, and Node `node --check` passing.

---

## Executive Summary

The repository has evolved from a collection of Markdown skill prompts and a standalone ReportLab script into a unified full-stack application (`Node.js :3000` → `FastAPI :8787` → `SQLite` + `ReportLab` + `14 Deterministic Calculators`) with Antigravity (AGY) workspace skill discovery (`.agents/skills/`).

While all core user flows and 16 automated tests pass, an extensive audit surfaces **20 concrete findings** across security/auth, database concurrency, financial calculation edge cases, frontend UX/resource cleanup, Docker hardening, and documentation consistency:

| Severity | Count | Key Themes |
| :--- | :---: | :--- |
| **High** | 4 | SQLite connection closing (`with conn:` doesn't close FDs), lack of session token expiration/TTL, wildcard CORS with `allow_credentials=True`, SQLite WAL/busy-timeout under concurrency |
| **Medium** | 10 | Missing confirmation before deleting a plan, budget sync overwriting detailed expense rows, hardcoded 2025 tax limits without 50+ catch-up logic, portfolio % sum validation, SPA `200 OK` fallback on missing static assets, hardcoded `:3000` redirect in FastAPI `GET /`, `_demo_data()` internal math drift, grading scale drift in Markdown skills |
| **Low / Polish** | 6 | Root user in Dockerfiles, `zubair-trabzada` repo URLs in `install.sh`/`README.md`, unrevoked Blob URL on PDF preview, unclosed `Popen` pipes in `tests/test_e2e.py` (`ResourceWarning`), redundant `init_db()` calls per request |

---

## 1. Security, Authentication & Database Layer

### 1.1 [HIGH] `with _connect(db_path) as conn:` Does Not Close SQLite Connections
- **File:** [scripts/db.py](file:///Users/pmishra/Documents/Udemy/ai-finance/scripts/db.py#L55-L61) (used at lines 85, 152, 180, 198, 214, 220, 234, 257, 290, 307, 325, 349, 369)
- **Issue:** In Python's `sqlite3` module, using a `sqlite3.Connection` as a context manager (`with _connect(...) as conn:`) only manages the **transaction** (`COMMIT` on success, `ROLLBACK` on exception)—it **does not call `conn.close()`**. Connections remain open until garbage-collected, which can leak file descriptors or hold locks under load.
- **Fix:** Wrap `_connect()` with `contextlib.closing` or a custom `@contextmanager` that calls `conn.close()` in a `finally:` block.

### 1.2 [HIGH] SQLite Missing `WAL` Mode and Busy Timeout
- **File:** [scripts/db.py](file:///Users/pmishra/Documents/Udemy/ai-finance/scripts/db.py#L58-L60)
- **Issue:** `sqlite3.connect(path)` uses the default rollback journal and default timeout (`5.0s`). When FastAPI handles concurrent requests (e.g., running multiple skills or loading plans + skills via `Promise.all` in `frontend/public/app.js:194`), concurrent writes can trigger `sqlite3.OperationalError: database is locked`.
- **Fix:** Set `sqlite3.connect(path, timeout=15.0)` and execute `PRAGMA journal_mode = WAL;` and `PRAGMA busy_timeout = 15000;` inside `_connect()`.

### 1.3 [HIGH] Session Tokens Never Expire (No TTL or Cleanup)
- **File:** [scripts/db.py](file:///Users/pmishra/Documents/Udemy/ai-finance/scripts/db.py#L93-L99) and [scripts/db.py](file:///Users/pmishra/Documents/Udemy/ai-finance/scripts/db.py#L197-L211)
- **Issue:** `sessions` stores `created_at`, but `get_user_by_token()` never checks token age, and expired sessions are never pruned. Any bearer token stored in `localStorage` remains valid indefinitely unless `/auth/logout` is explicitly called.
- **Fix:** Add an `expires_at` column (or check `created_at` against a configurable TTL such as 7 days in `get_user_by_token()`) and delete expired rows during authentication.

### 1.4 [HIGH] Wildcard CORS (`allow_origins=["*"]`) Combined with `allow_credentials=True`
- **File:** [scripts/server.py](file:///Users/pmishra/Documents/Udemy/ai-finance/scripts/server.py#L64-L70)
- **Issue:** Configuring `CORSMiddleware` with `allow_origins=["*"]` and `allow_credentials=True` is overly permissive. Because the Node.js frontend proxies `/api/*` on the same origin (`http://localhost:3000`), cross-origin browser requests aren't even required in normal operation.
- **Fix:** Restrict `allow_origins` to `os.environ.get("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")`.

### 1.5 [MEDIUM] Default `user` / `password` Seeded Unconditionally & No Login Rate Limit
- **Files:** [scripts/db.py](file:///Users/pmishra/Documents/Udemy/ai-finance/scripts/db.py#L127-L136), [scripts/server.py](file:///Users/pmishra/Documents/Udemy/ai-finance/scripts/server.py#L159-L176)
- **Issue:**
  1. `init_db()` always seeds `user` / `password` if `"user"` does not exist. If a user binds the server to `0.0.0.0` on a shared network, the well-known default account is exposed.
  2. `/auth/login` and `/auth/register` have no rate limiting.
- **Fix:** Allow disabling default account seeding via an environment flag (e.g., `AI_FINANCE_SEED_DEFAULT_USER=0`) and add basic in-memory per-IP rate limiting on `/auth/*`.

---

## 2. Backend API, Calculators & PDF Engine

### 2.1 [MEDIUM] `calc_budget` Plan Sync Overwrites Detailed Expense Categories
- **Files:** [scripts/calculators.py](file:///Users/pmishra/Documents/Udemy/ai-finance/scripts/calculators.py#L369-L378), [scripts/server.py](file:///Users/pmishra/Documents/Udemy/ai-finance/scripts/server.py#L293-L299)
- **Issue:** When `finance-budget` is run with **Run & Sync to Plan**, its `plan_patch` sets:
  ```python
  "expenses": [("Essential Needs", needs), ("Discretionary Wants", wants)]
  ```
  Because `run_plan_skill` merges `cash_flow` keys shallowly, syncing `finance-budget` replaces the plan's detailed 11-item expense breakdown (Housing, Groceries, Childcare, etc.) on Page 3 of the PDF with just two summary rows.
- **Fix:** Preserve detailed `cash_flow.expenses` if already populated (or scale/store `budget_50_30_20` under its own sub-key in `cash_flow`) unless the user explicitly replaces the expense list.

### 2.2 [MEDIUM] `calc_taxes` Missing Age 50+ / 55+ Catch-Up Contribution Limits
- **File:** [scripts/calculators.py](file:///Users/pmishra/Documents/Udemy/ai-finance/scripts/calculators.py#L696-L709)
- **Issue:** `calc_taxes` hardcodes standard annual limits (`limit_401k = 23500.0`, `limit_hsa = 8550.0 / 4300.0`, `limit_ira = 7000.0`) and does not inspect `age` from `inputs` or `plan["retirement"]["current_age"]`. Users aged 50+ qualify for catch-up contributions (`+$7,500` on 401(k), `+$1,000` on IRA; `+$1,000` on HSA at age 55+).
- **Fix:** Read `age` from `inputs` / `plan` and add catch-up limits when `age >= 50` (and `age >= 55` for HSA).

### 2.3 [MEDIUM] `calc_portfolio` Does Not Validate That Allocation Percentages Sum to 100%
- **File:** [scripts/calculators.py](file:///Users/pmishra/Documents/Udemy/ai-finance/scripts/calculators.py#L533-L558)
- **Issue:** If a user enters allocation percentages that sum to `80%` or `130%`, `calc_portfolio` computes drift and dollar rebalancing trades without warning or normalizing, leading to unbalanced buy/sell trade recommendations.
- **Fix:** Check `total_pct = us_stocks + intl_stocks + bonds + reits + cash`; if `abs(total_pct - 100.0) > 0.5`, surface a warning in `summary`/`recommendations` or normalize weights.

### 2.4 [MEDIUM] Hardcoded `:3000` Port in FastAPI `GET /` Browser Redirect
- **File:** [scripts/server.py](file:///Users/pmishra/Documents/Udemy/ai-finance/scripts/server.py#L134-L138)
- **Issue:** `RedirectResponse(url=f"http://{host}:3000", status_code=307)` hardcodes port `3000`. When launched with `./start.sh --port 3001`, visiting `:8787` in a browser redirects to `:3000` instead of `:3001`.
- **Fix:** Read `FRONTEND_PORT = os.environ.get("FRONTEND_PORT", "3000")` (and export `FRONTEND_PORT` in `start.sh` / `start.ps1`).

### 2.5 [MEDIUM] Internal Math Drift in `_demo_data()`
- **File:** [scripts/generate_finance_pdf.py](file:///Users/pmishra/Documents/Udemy/ai-finance/scripts/generate_finance_pdf.py#L963-L1020)
- **Issue:**
  1. `_demo_data()["health_score"]` is `68`, whereas the 5 category scores (`78, 52, 71, 64, 58`) average to `64.6`. As soon as a user clicks **Run & Sync to Plan** on `finance-analyze` with the default values, the plan's score drops from `68` to `64.6`.
  2. `_demo_data()["cash_flow"]["expenses"]` sums to `$6,685` on `$9,200` income (`27.3%` savings rate), while `category_notes.cash_flow` claims `"21% savings rate"`.
  3. `_demo_data()["debt"]["accounts"]` minimum payments sum to `$810/mo` (`220 + 380 + 210`), while `cash_flow.expenses` lists `("Debt payments (min)", 360)`.
- **Fix:** Align `_demo_data()` numbers so category scores average to `68`, debt minimums match cash flow (`$810`), and the savings rate note matches the computed surplus (`22%`).

### 2.6 [MEDIUM] Grading Scale Drift Between Python Engine and Markdown Skills
- **Files:**
  - [scripts/generate_finance_pdf.py](file:///Users/pmishra/Documents/Udemy/ai-finance/scripts/generate_finance_pdf.py#L118-L141) (`>=90 A+`, `>=85 A`, `>=80 A-`, `>=75 B+`, `>=70 B`, `>=65 B-`, `>=60 C+`, `>=55 C`, `>=50 C-`, `>=45 D+`, `>=40 D`, `<40 F`)
  - [finance/SKILL.md](file:///Users/pmishra/Documents/Udemy/ai-finance/finance/SKILL.md#L56-L63) (`85-100 A+`, `70-84 A`, `55-69 B`, `40-54 C`, `25-39 D`, `0-24 F`)
  - [skills/finance-analyze/SKILL.md](file:///Users/pmishra/Documents/Udemy/ai-finance/skills/finance-analyze/SKILL.md#L226-L234) (`85-100 A+`, `75-84 A`, `65-74 B+`, `55-64 B`, `45-54 C`, `35-44 D`, `0-34 F`)
- **Issue:** An agent following `finance/SKILL.md` or `skills/finance-analyze/SKILL.md` in chat assigns a different letter grade for the same numerical score than the web app and PDF generator.
- **Fix:** Update the Markdown tables in `finance/SKILL.md` and `skills/finance-analyze/SKILL.md` to match `score_grade()` and `score_signal()` in `scripts/generate_finance_pdf.py`.

### 2.7 [LOW] Redundant `init_db()` Calls on Every `/health`, `/auth/login`, and `/auth/register` Request
- **File:** [scripts/server.py](file:///Users/pmishra/Documents/Udemy/ai-finance/scripts/server.py#L155-L172)
- **Issue:** `init_db(seed_demo_payload=_demo_data())` runs DDL (`CREATE TABLE IF NOT EXISTS ...`) and queries the `users` table on every `/health`, `/auth/login`, and `/auth/register` call.
- **Fix:** Track initialized DB paths in memory in `scripts/db.py` (e.g., `_INITIALIZED_PATHS: set[str]`) so `init_db()` is a fast no-op after the first call per DB path.

---

## 3. Frontend & Node.js Proxy (`frontend/`)

### 3.1 [MEDIUM] Missing Confirmation Prompt on `Delete Plan`
- **File:** [frontend/public/app.js](file:///Users/pmishra/Documents/Udemy/ai-finance/frontend/public/app.js#L308-L318)
- **Issue:** Clicking `Delete Plan` immediately fires `DELETE /api/plans/{id}` without confirmation, permanently deleting the plan and its cascaded `skill_runs` rows in SQLite.
- **Fix:** Guard `deleteActivePlan()` with `if (!window.confirm("Delete this financial plan and all saved skill runs?")) return;`.

### 3.2 [MEDIUM] Static Server Returns `200 OK` (`index.html`) for Missing Asset Files
- **File:** [frontend/server.js](file:///Users/pmishra/Documents/Udemy/ai-finance/frontend/server.js#L76-L88)
- **Issue:** When `fs.stat` fails for any path (such as `/favicon.ico` or a mistyped `/missing.js`), `serveStatic` serves `index.html` with status `200 OK` and `Content-Type: text/html`. If a script or stylesheet path is ever mistyped, the browser receives HTML instead of a `404` and fails with `Uncaught SyntaxError: Unexpected token '<'`.
- **Fix:** Only serve the `index.html` SPA fallback when `path.extname(relPath) === ""` (extensionless route); return `404 Not Found` when a file with an extension is missing.

### 3.3 [MEDIUM] No Upstream Request Timeout in `proxyToBackend`
- **File:** [frontend/server.js](file:///Users/pmishra/Documents/Udemy/ai-finance/frontend/server.js#L35-L62)
- **Issue:** `client.request(...)` does not set a timeout (`timeout: 15000` or `proxyReq.setTimeout(...)`). If the backend hangs, proxy sockets remain open indefinitely.
- **Fix:** Add ` proxyReq.setTimeout(15000, () => proxyReq.destroy(new Error("Upstream timeout")));`.

### 3.4 [LOW] Unrevoked Object URL on `Preview PDF`
- **File:** [frontend/public/app.js](file:///Users/pmishra/Documents/Udemy/ai-finance/frontend/public/app.js#L320-L337)
- **Issue:** When `inline === true` (`Preview PDF`), `URL.createObjectURL(blob)` is opened via `window.open(url, "_blank")` and never revoked with `URL.revokeObjectURL(url)`.
- **Fix:** Call `setTimeout(() => URL.revokeObjectURL(url), 60000);` after `window.open(...)`.

---

## 4. Infrastructure, Scripts, Docs & Tests

### 4.1 [LOW] Docker Containers Run as `root`
- **Files:** [Dockerfile](file:///Users/pmishra/Documents/Udemy/ai-finance/Dockerfile), [frontend/Dockerfile](file:///Users/pmishra/Documents/Udemy/ai-finance/frontend/Dockerfile)
- **Issue:** Both containers run their entrypoint processes as `root`.
- **Fix:** Use `USER node` (with proper `/app` ownership) in `frontend/Dockerfile` and create a non-root user in `Dockerfile`.

### 4.2 [LOW] Stale Upstream Repo Owner (`zubair-trabzada`) in `install.sh` and `README.md`
- **Files:** [install.sh](file:///Users/pmishra/Documents/Udemy/ai-finance/install.sh#L3-L20), [README.md](file:///Users/pmishra/Documents/Udemy/ai-finance/README.md#L50-L65)
- **Issue:** The git `origin` remote is `https://github.com/pmishra02138/ai-finance.git`, but `install.sh` (`REPO="zubair-trabzada/ai-finance"`) and `README.md` (`git clone` and `curl` URLs) still point to `zubair-trabzada/ai-finance`.
- **Fix:** Update `REPO` in `install.sh` and the clone/curl URLs in `README.md` to `pmishra02138/ai-finance`.

### 4.3 [LOW] Unclosed `subprocess.Popen` Pipes Cause `ResourceWarning` in `tests/test_e2e.py`
- **File:** [tests/test_e2e.py](file:///Users/pmishra/Documents/Udemy/ai-finance/tests/test_e2e.py#L299-L304) and [tests/test_e2e.py](file:///Users/pmishra/Documents/Udemy/ai-finance/tests/test_e2e.py#L469-L475)
- **Issue:** `fe_proc = subprocess.Popen(..., stdout=subprocess.PIPE, stderr=subprocess.PIPE)` opens file descriptors for `stdout` and `stderr` that are not closed in the `finally:` block, emitting two `ResourceWarning: unclosed file <_io.BufferedReader>` warnings on every test run.
- **Fix:** Close `fe_proc.stdout.close()` and `fe_proc.stderr.close()` in `finally:` after terminating `fe_proc` (or use `stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL`).

### 4.4 [LOW] Both `review.md` and `code_review.md` Exist in Repo Root
- **Files:** [review.md](file:///Users/pmishra/Documents/Udemy/ai-finance/review.md), [code_review.md](file:///Users/pmishra/Documents/Udemy/ai-finance/code_review.md)
- **Issue:** `review.md` reflects the initial pre-adaptation review of the repo, while `code_review.md` covers the current full-stack architecture.
- **Fix:** Archive or remove `review.md` once no longer needed so contributors have a single current review document.

---

## Prioritized Remediation Checklist

1. **Database & Auth Hardening (`scripts/db.py`, `scripts/server.py`):**
   - [ ] Ensure `_connect()` closes connections via `contextlib.closing` and enables `PRAGMA journal_mode = WAL;` + `timeout=15.0`.
   - [ ] Add session TTL check in `get_user_by_token()` and restrict `CORSMiddleware` origins.
   - [ ] Cache `init_db()` per DB path so `/health` and `/auth/*` don't re-run DDL on every request.
2. **Calculator & Data Accuracy (`scripts/calculators.py`, `scripts/generate_finance_pdf.py`, `SKILL.md`):**
   - [ ] Preserve detailed expense rows when syncing `finance-budget` to plan.
   - [ ] Add age 50+/55+ catch-up limits to `calc_taxes` and 100%-sum validation to `calc_portfolio`.
   - [ ] Align `_demo_data()` category average (`68`), debt minimums (`$810`), and grading tables in `finance/SKILL.md` & `skills/finance-analyze/SKILL.md`.
3. **Frontend & Infra Polish (`frontend/`, `install.sh`, `README.md`, `tests/test_e2e.py`):**
   - [ ] Add `window.confirm` before `Delete Plan` and revoke preview Blob URLs in `frontend/public/app.js`.
   - [ ] Return `404` for missing files with extensions in `frontend/server.js` and add proxy timeout.
   - [ ] Close `fe_proc` pipes in `tests/test_e2e.py` to eliminate `ResourceWarning`.
   - [ ] Update `zubair-trabzada/ai-finance` → `pmishra02138/ai-finance` in `install.sh` and `README.md`.
