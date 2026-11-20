# Codebase Review — `ai-finance`

**Reviewed:** 2026-11-20  
**Scope:** Full repository (`install.sh`, `uninstall.sh`, `requirements.txt`, `README.md`, `finance/SKILL.md`, `skills/*/SKILL.md`, `scripts/generate_finance_pdf.py`)  
**Syntax Checks Run:** `python3 -m py_compile scripts/generate_finance_pdf.py` (passed) and `bash -n install.sh uninstall.sh` (passed). Note: `reportlab` is not installed in the local Python environment, so runtime PDF generation was not executed.

---

## Executive Summary

The repository is clean, readable, and well-structured conceptually, but it has **several critical integration mismatches** between the documentation/skills and the actual code on disk, plus **runtime edge-case bugs** in `scripts/generate_finance_pdf.py`.

Top priorities to fix:
1. **Broken PDF skill-to-script contract** (`skills/finance-report-pdf/SKILL.md` vs. `scripts/generate_finance_pdf.py`).
2. **Missing `agents/` directory** referenced by `README.md`, `install.sh`, and `uninstall.sh`.
3. **Unescaped XML/HTML in ReportLab `Paragraph` calls** in `scripts/generate_finance_pdf.py` (crashes on `&`, `<`, `>` in user text) and **empty-slice `ZeroDivisionError`** in `pie_drawing`.
4. **Inconsistent grading scales** across `finance/SKILL.md`, `skills/finance-analyze/SKILL.md`, and `scripts/generate_finance_pdf.py`.

---

## 1. Critical Findings

### 1.1 Broken Contract Between `finance-report-pdf` Skill and `generate_finance_pdf.py`
- **Files:**
  - `finance/SKILL.md` (line 106)
  - `skills/finance-report-pdf/SKILL.md` (lines 45, 68, 71, 82–155, 181–187, 198)
  - `scripts/generate_finance_pdf.py` (lines 1139–1156)
- **Issue:** `finance/SKILL.md` and `skills/finance-report-pdf/SKILL.md` instruct Claude to run:
  ```bash
  python3 ~/.claude/skills/finance/scripts/generate_finance_pdf.py
  ```
  with **no arguments**, stating that *"The script reads all FINANCE-*.md files from the current working directory, parses the structured sections, and assembles a PDF using ReportLab."*  
  In reality, `scripts/generate_finance_pdf.py` **does not scan or parse `FINANCE-*.md` files**. It requires `--data <path-to-json>` or `--demo`, and exits immediately with an `argparse` error if invoked without arguments.
- **Additional Spec Drift:** `skills/finance-report-pdf/SKILL.md` also documents features that do not exist in `generate_finance_pdf.py`:
  - 10–12 page layout with a Glossary & Disclosures final page and 30-day/90-day/1-year/5-year priorities (the script generates a 9-page layout with Executive Summary on Page 1).
  - CLI options `--sections=debt,retirement`, custom logo injection, and currency override.
- **Recommendation:** Either update `skills/finance-report-pdf/SKILL.md` and `finance/SKILL.md` so Claude serializes the extracted data to a JSON file matching `_demo_data()`'s schema and passes `--data <json_path>`, or implement the markdown scanner and missing CLI flags in `generate_finance_pdf.py`.

### 1.2 Missing `agents/` Directory Referenced Across the Repo
- **Files:** `README.md` (lines 11, 71, 204), `install.sh` (lines 27, 159–177, 194, 203, 246), `uninstall.sh` (lines 16, 25, 57–66)
- **Issue:** The installer, uninstaller, and README all expect an `agents/` directory containing 5 agent markdown files (`finance-cashflow`, `finance-debt`, `finance-investments`, `finance-retirement`, `finance-protection`) to install into `~/.claude/agents/`. **No `agents/` directory exists in the repository.** Running `./install.sh` always prints `⚠ No agents/ folder at ..., skipping.` and reports `0 agent file(s)`.
- **Recommendation:** Either add the 5 agent definitions under `agents/` or remove `agents/` references from `install.sh`, `uninstall.sh`, and `README.md` (since `skills/finance-analyze/SKILL.md` already embeds the 5 subagent prompts inline).

### 1.3 Unescaped XML/HTML in ReportLab `Paragraph` Calls (Crash Risk)
- **File:** `scripts/generate_finance_pdf.py` (lines 320, 417, 425, 427, 453, 489, 557, 687, 767, 822, 842, 897–898, 929)
- **Issue:** ReportLab's `Paragraph()` parses its input as XML. Dynamic strings from JSON (such as `client_name`, `executive_summary`, `category_notes`, `commentary`, `action_items[].action`, and `ninety_day_plan` items) are interpolated directly into `Paragraph(...)` without escaping. Any `&`, `<`, or `>` in user text (e.g., `"AT&T"`, `"Health & Dental"`, `"<5% fee"`) will raise a `xml.sax.SAXParseException` / `ValueError` and abort PDF generation.
- **Recommendation:** Wrap all dynamic user-supplied strings with `xml.sax.saxutils.escape()` before passing them into `Paragraph(...)`.

### 1.4 `ZeroDivisionError` on Empty Investment Allocation
- **File:** `scripts/generate_finance_pdf.py` (lines 339–358, 647, 657)
- **Issue:**
  - In `build_investments` (line 647), `[(a["name"], float(a["pct"])) for a in inv.get("allocation", [])]` uses direct key access (`a["name"]`, `a["pct"]`) instead of `.get()`, which raises `KeyError` on partial data—even though lines 664–667 use `.get()`.
  - If `inv.get("allocation")` is empty (`[]`), `pie_drawing([])` passes `p.data = []` to ReportLab's `Pie`, which raises `ZeroDivisionError`.
- **Recommendation:** Guard `pie_drawing` and `build_investments` against an empty `allocation` list (render a fallback placeholder message instead of a `Pie`), and use `.get()` consistently on line 647.

---

## 2. Moderate Findings

### 2.1 Inconsistent Grading & Signal Scales Across Files
Three different grading scales exist in the repository:
- `finance/SKILL.md` (lines 50–58): `85–100 A+`, `70–84 A`, `55–69 B`, `40–54 C`, `25–39 D`, `0–24 F`
- `skills/finance-analyze/SKILL.md` (lines 225–234): `85–100 A+`, `75–84 A`, `65–74 B+`, `55–64 B`, `45–54 C`, `35–44 D`, `0–34 F`
- `scripts/generate_finance_pdf.py` (lines 118–141): `>=90 A+`, `>=85 A`, `>=80 A-`, `>=75 B+`, `>=70 B`, `>=65 B-`, `>=60 C+`, `>=55 C`, `>=50 C-`, `>=45 D+`, `>=40 D`, `<40 F`

**Recommendation:** Standardize on one grading and signal scale in a single documented source of truth and align all three files.

### 2.2 `scripts/generate_finance_pdf.py` Layout & Input-Handling Issues
- **Margin overflow in Investments layout (line 682):** `Table([[pie, tbl]], colWidths=[3.6 * inch, 3.6 * inch])` totals `7.2 * inch`, exceeding the usable frame width of `7.1 * inch` (`8.5 - 2 * 0.7`).
- **Fixed row height in 90-Day Plan (line 900):** `rowHeights=[0.38 * inch, 2.4 * inch]` hardcodes the card body height to `2.4 * inch`. Longer task lists (4–5 multi-line items) will overflow or clip. Use `None` (auto-height) or `minRowHeights` instead.
- **Unchecked `expenses` types (line 498):** `sum(v for _, v in expenses_list)` does not cast `float(v)` and assumes 2-tuples/2-element lists. String numbers or `None` values will raise `TypeError`.
- **Progress bar contrast & clamping (lines 728–732):** In `build_retirement`, `pctp` is clamped to `1.0` (`100% of target` even if over-funded), and the `NAVY` (`#0c1220`) label sits directly on top of the `GREEN` (`#2d8a4e`) bar, resulting in low text contrast.
- **Debt timeline when `payoff_months == 0` (lines 623–639):** When there is no debt (`payoff_months = 0`), `months = max(payoff_months, 1)` still renders a full green `Yr 0`–`Yr 1` payoff bar. Also, `debts` are numbered by `d.get("order", i)` but not sorted by `order`.
- **`--demo` overrides explicit `--output FINANCE-PLAN.pdf` (lines 1153–1156):** If a user runs `--demo --output FINANCE-PLAN.pdf`, the script silently changes `args.output` to `FINANCE-PLAN-sample.pdf` because it checks `if args.output == "FINANCE-PLAN.pdf"` rather than `None`/default sentinel.
- **Unvalidated JSON root type (line 1160):** If `--data` contains a JSON array or `null` instead of an object, `data.get(...)` fails with `AttributeError`. Validate `isinstance(data, dict)`.
- **Brittle footer slice (lines 249–250):** `DISCLAIMER_TEXT[:115]` and `DISCLAIMER_TEXT[115:]` rely on a hardcoded character index; editing `DISCLAIMER_TEXT` can split a word mid-character.

### 2.3 Inconsistencies in `_demo_data()`
- **File:** `scripts/generate_finance_pdf.py` (lines 955–1093)
- `health_score` is `68` (`B-`), while the 5 equal-weighted category scores (`78, 52, 71, 64, 58`) average to `64.6` (`65`).
- `cash_flow.expenses` sums to `$6,685` on `$9,200` income (`27.3%` savings rate), whereas `category_notes.cash_flow` states `"21% savings rate"`.
- `debt.accounts` minimum payments sum to `$810/mo` (`220 + 380 + 210`), whereas `cash_flow.expenses` lists `("Debt payments (min)", 360)`.

### 2.4 Shell Script Issues (`install.sh` & `uninstall.sh`)
- **Temp directory leak (`install.sh`, lines 112–128):** `fetch_remote()` creates `tmp=$(mktemp -d)` and never removes it on exit or error. Add `trap 'rm -rf "${tmp:-}"' EXIT` or clean it up after installation.
- **Silent `pip3 --user` failure on PEP 668 systems (`install.sh`, lines 98–106):** Modern macOS (Homebrew Python) and Linux distros reject `pip3 install --user` with `externally-managed-environment`. Because stderr is suppressed (`2>/dev/null`) and `check_reportlab` returns `0` anyway, users may miss why PDF generation fails later. Consider checking/installing via `requirements.txt` or surfacing the actual error/venv guidance.
- **Stale files on upgrade (`install.sh`, lines 136–155):** `cp -R "${src}/."` merges into existing `~/.claude/skills/finance*` directories without cleaning old files if a skill or script is renamed/removed.
- **Non-interactive `uninstall.sh` (`uninstall.sh`, lines 28–33):** `read -p ... -n 1 -r` exits/cancels when stdin is not a TTY; consider adding a `-y` / `--yes` flag.

---

## 3. Minor Findings & Housekeeping

### 3.1 Missing YAML Frontmatter on `finance/SKILL.md`
- **File:** `finance/SKILL.md` (line 1)
- All 14 files under `skills/finance-*/SKILL.md` include YAML frontmatter (`name`, `description`), whereas `finance/SKILL.md` starts directly with a Markdown `#` heading. Adding frontmatter ensures consistent skill discovery.

### 3.2 Command Syntax & Skill Count Mismatches
- **Command naming:** `README.md` and `install.sh` document hyphenated commands (`/finance-analyze`, `/finance-quick`, etc.), while `finance/SKILL.md` and `skills/*/SKILL.md` use space-separated subcommands (`/finance analyze`, `/finance quick`, etc.).
- **Skill count:** `README.md` badge/subtitle says **14 skills**, while lines 70 and 189 say **13 sub-skills**. There are actually **14** `skills/finance-*` directories plus **1** `finance/` orchestrator (`15` total).

### 3.3 Unused Imports & Variables
- `scripts/generate_finance_pdf.py`:
  - Unused imports: `dataclass` (line 38), `Circle`, `Polygon` (line 61), `HorizontalBarChart` (line 62).
  - Unused style: `styles["footer"]` (lines 212–216).
- `install.sh`:
  - Unused variable: `RAW_BASE` (line 22).

### 3.4 Missing Tests & CI
- There are no unit tests (e.g., `pytest` for `generate_finance_pdf.py` covering empty/edge-case JSON payloads and XML-special characters) and no GitHub Actions workflow (`.github/` only contains `banner.svg`).

---

## 4. Recommended Next Steps

1. **Align `finance-report-pdf` and `generate_finance_pdf.py`** so `/finance report-pdf` works end-to-end without failing on missing `--data`.
2. **Harden `generate_finance_pdf.py`**: escape all dynamic strings for ReportLab `Paragraph`, guard empty `allocation`/`debts` lists, fix the `7.2 * inch` table width, and remove hardcoded `2.4 * inch` row heights.
3. **Resolve `agents/`**: either commit the 5 agent `.md` files or remove the dead `agents/` logic from `install.sh`, `uninstall.sh`, and `README.md`.
4. **Unify the grading scale** across `finance/SKILL.md`, `skills/finance-analyze/SKILL.md`, and `scripts/generate_finance_pdf.py`.
5. **Add basic tests** (JSON schema validation, XML character escaping, empty-list rendering, and `shellcheck` in CI).
