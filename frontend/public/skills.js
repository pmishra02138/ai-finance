/* Declarative schemas & result renderer for all 14 financial skills */

window.FinanceSkills = (function () {
  const esc = (s) => window.FinanceCharts.escapeHtml(s);

  function sumExpenses(plan) {
    const list = (plan && plan.cash_flow && plan.cash_flow.expenses) || [];
    return list.reduce((acc, item) => {
      if (Array.isArray(item)) return acc + Number(item[1] || 0);
      if (item && typeof item === "object") return acc + Number(item.amount || item.value || 0);
      return acc;
    }, 0);
  }

  function sumDebt(plan) {
    const accs = (plan && plan.debt && plan.debt.accounts) || [];
    return accs.reduce((acc, d) => acc + Number(d.balance || 0), 0);
  }

  const SKILL_FORMS = {
    "finance-quick": (plan) => [
      { key: "monthly_income", label: "Monthly Income ($)", type: "number", value: plan?.cash_flow?.monthly_income ?? 9200 },
      { key: "monthly_expenses", label: "Monthly Expenses ($)", type: "number", value: sumExpenses(plan) || 6685 },
      { key: "total_savings", label: "Total Savings & Investments ($)", type: "number", value: plan?.investments?.total_value ?? 184000 },
      { key: "total_debt", label: "Total Debt ($)", type: "number", value: sumDebt(plan) || 41200 },
      { key: "age", label: "Current Age", type: "number", value: plan?.retirement?.current_age ?? 38 },
      { key: "retirement_age", label: "Target Retirement Age", type: "number", value: plan?.retirement?.retirement_age ?? 65 },
    ],
    "finance-networth": (plan) => [
      { key: "cash_assets", label: "Cash & Savings ($)", type: "number", value: 15000 },
      { key: "investment_assets", label: "Investments & Retirement ($)", type: "number", value: plan?.investments?.total_value ?? 184000 },
      { key: "real_estate_assets", label: "Real Estate Value ($)", type: "number", value: 0 },
      { key: "other_assets", label: "Other Assets ($)", type: "number", value: 15000 },
      { key: "mortgage_debt", label: "Mortgage Balance ($)", type: "number", value: 0 },
      { key: "other_debt", label: "Other Debts ($)", type: "number", value: sumDebt(plan) || 41200 },
      { key: "age", label: "Current Age", type: "number", value: plan?.retirement?.current_age ?? 38 },
      { key: "annual_income", label: "Gross Annual Income ($)", type: "number", value: (plan?.cash_flow?.monthly_income ?? 9200) * 12 },
    ],
    "finance-budget": (plan) => [
      { key: "monthly_income", label: "Monthly Income ($)", type: "number", value: plan?.cash_flow?.monthly_income ?? 9200 },
      { key: "monthly_needs", label: "Monthly Essential Needs ($)", type: "number", value: 4600 },
      { key: "monthly_wants", label: "Monthly Discretionary Wants ($)", type: "number", value: 1600 },
    ],
    "finance-emergency": () => [
      { key: "monthly_essential_expenses", label: "Monthly Essential Expenses ($)", type: "number", value: 4000 },
      { key: "current_emergency_fund", label: "Current Emergency Fund ($)", type: "number", value: 11000 },
      { key: "monthly_contribution", label: "Monthly Addition ($)", type: "number", value: 500 },
      {
        key: "job_stability",
        label: "Income Stability",
        type: "select",
        value: "stable",
        options: [
          { value: "stable", label: "Stable W-2" },
          { value: "variable", label: "Variable / Commission" },
          { value: "high_risk", label: "High Volatility / Seasonal" },
        ],
      },
      { key: "dependents", label: "Dependents", type: "number", value: 1 },
      { key: "self_employed", label: "Self-Employed / Business Owner", type: "checkbox", value: false },
    ],
    "finance-debt": (plan) => [
      { key: "extra_monthly_payment", label: "Extra Monthly Payment Toward Debt ($)", type: "number", value: 400 },
      {
        key: "accounts",
        label: "Debt Accounts (JSON Array)",
        type: "json",
        value: JSON.stringify(
          plan?.debt?.accounts || [
            { name: "Credit Card", balance: 8400, apr: 22.0, min_payment: 220 },
            { name: "Student Loan", balance: 18600, apr: 6.2, min_payment: 210 },
          ],
          null,
          2
        ),
      },
    ],
    "finance-portfolio": (plan) => [
      { key: "total_value", label: "Total Invested Value ($)", type: "number", value: plan?.investments?.total_value ?? 184000 },
      { key: "age", label: "Current Age", type: "number", value: plan?.retirement?.current_age ?? 38 },
      { key: "avg_expense_ratio", label: "Weighted Expense Ratio (%)", type: "number", step: "0.01", value: 0.08 },
      { key: "us_stocks_pct", label: "US Stocks (%)", type: "number", value: 58 },
      { key: "intl_stocks_pct", label: "International Stocks (%)", type: "number", value: 14 },
      { key: "bonds_pct", label: "Bonds (%)", type: "number", value: 18 },
      { key: "reits_pct", label: "REITs (%)", type: "number", value: 6 },
      { key: "cash_pct", label: "Cash / Money Market (%)", type: "number", value: 4 },
    ],
    "finance-screen": () => [
      {
        key: "strategy",
        label: "Investment Strategy",
        type: "select",
        value: "3-fund",
        options: [
          { value: "3-fund", label: "Boglehead 3-Fund Index" },
          { value: "dividend", label: "Dividend Growth" },
          { value: "bonds", label: "Conservative Bond & Income" },
          { value: "reits", label: "Real Estate (REIT) Tilt" },
          { value: "esg", label: "ESG Screened Core" },
        ],
      },
      { key: "investment_amount", label: "Amount to Allocate ($)", type: "number", value: 25000 },
    ],
    "finance-taxes": (plan) => [
      { key: "gross_annual_income", label: "Gross Annual Income ($)", type: "number", value: (plan?.cash_flow?.monthly_income ?? 9200) * 12 },
      { key: "marginal_tax_rate", label: "Marginal Federal Tax Bracket (%)", type: "number", value: 24 },
      { key: "current_401k", label: "Current Annual 401(k) Contribution ($)", type: "number", value: 11000 },
      { key: "current_hsa", label: "Current Annual HSA Contribution ($)", type: "number", value: 0 },
      { key: "current_ira", label: "Current Annual IRA Contribution ($)", type: "number", value: 0 },
      { key: "harvestable_losses", label: "Harvestable Capital Losses ($)", type: "number", value: 0 },
      { key: "hsa_eligible", label: "HDHP / HSA Eligible", type: "checkbox", value: true },
      { key: "family_hsa", label: "Family HSA Coverage", type: "checkbox", value: false },
    ],
    "finance-retirement": (plan) => [
      { key: "current_age", label: "Current Age", type: "number", value: plan?.retirement?.current_age ?? 38 },
      { key: "retirement_age", label: "Target Retirement Age", type: "number", value: plan?.retirement?.retirement_age ?? 65 },
      { key: "current_balance", label: "Current Retirement Balance ($)", type: "number", value: plan?.retirement?.current_balance ?? 184000 },
      { key: "monthly_contribution", label: "Monthly Contribution ($)", type: "number", value: plan?.retirement?.monthly_contribution ?? 920 },
      { key: "desired_annual_spending", label: "Desired Annual Retirement Spend ($)", type: "number", value: 58000 },
      { key: "social_security_annual", label: "Expected Annual Social Security ($)", type: "number", value: 0 },
    ],
    "finance-fire": (plan) => [
      { key: "annual_expenses", label: "Expected Annual Expenses ($)", type: "number", value: 60000 },
      { key: "current_invested", label: "Current Invested Portfolio ($)", type: "number", value: plan?.investments?.total_value ?? 184000 },
      { key: "annual_savings", label: "Annual Savings / Contributions ($)", type: "number", value: 24000 },
      { key: "withdrawal_rate", label: "Safe Withdrawal Rate (%)", type: "number", step: "0.1", value: 4.0 },
      { key: "expected_real_return", label: "Expected Real Return (%)", type: "number", step: "0.1", value: 6.0 },
      { key: "current_age", label: "Current Age", type: "number", value: plan?.retirement?.current_age ?? 38 },
    ],
    "finance-goals": () => [
      { key: "goal_name", label: "Goal Name", type: "text", value: "House Down Payment" },
      { key: "target_amount", label: "Target Amount ($)", type: "number", value: 80000 },
      { key: "current_saved", label: "Currently Saved ($)", type: "number", value: 20000 },
      { key: "years_to_goal", label: "Years Until Goal", type: "number", step: "0.5", value: 5 },
      { key: "expected_return", label: "Expected Annual Return (%)", type: "number", step: "0.1", value: 4.5 },
    ],
    "finance-compare": () => [
      { key: "scenario_a_name", label: "Scenario A Name", type: "text", value: "Rent & Invest Difference" },
      { key: "scenario_a_upfront", label: "Scenario A Upfront Cost ($)", type: "number", value: 0 },
      { key: "scenario_a_monthly_cost", label: "Scenario A Monthly Cost ($)", type: "number", value: 2400 },
      { key: "scenario_a_monthly_invest", label: "Scenario A Monthly Invest ($)", type: "number", value: 800 },
      { key: "scenario_b_name", label: "Scenario B Name", type: "text", value: "Buy Home" },
      { key: "scenario_b_upfront", label: "Scenario B Upfront Cost ($)", type: "number", value: 60000 },
      { key: "scenario_b_monthly_cost", label: "Scenario B Monthly Cost ($)", type: "number", value: 3200 },
      { key: "scenario_b_monthly_invest", label: "Scenario B Monthly Invest ($)", type: "number", value: 0 },
      { key: "horizon_years", label: "Comparison Horizon (Years)", type: "number", value: 10 },
      { key: "investment_return", label: "Expected Return (%)", type: "number", step: "0.1", value: 6.5 },
    ],
    "finance-analyze": (plan) => [
      { key: "cash_flow_score", label: "Cash Flow Score (0-100)", type: "number", value: plan?.categories?.cash_flow ?? 78 },
      { key: "debt_score", label: "Debt Score (0-100)", type: "number", value: plan?.categories?.debt ?? 52 },
      { key: "investments_score", label: "Investments Score (0-100)", type: "number", value: plan?.categories?.investments ?? 71 },
      { key: "retirement_score", label: "Retirement Score (0-100)", type: "number", value: plan?.categories?.retirement ?? 64 },
      { key: "protection_score", label: "Protection Score (0-100)", type: "number", value: plan?.categories?.protection ?? 58 },
    ],
    "finance-report-pdf": () => [],
  };

  function getFields(skillName, plan, savedInputs) {
    const factory = SKILL_FORMS[skillName] || (() => []);
    const fields = factory(plan || {});
    if (!savedInputs) return fields;
    return fields.map((f) => {
      if (savedInputs[f.key] === undefined) return f;
      const val = f.type === "json" && typeof savedInputs[f.key] !== "string"
        ? JSON.stringify(savedInputs[f.key], null, 2)
        : savedInputs[f.key];
      return { ...f, value: val };
    });
  }

  function renderForm(container, fields) {
    if (!fields.length) {
      container.innerHTML = `<p class="muted">This module uses your active synced financial plan directly. Click <strong>Run &amp; Validate</strong> or export your 9-page PDF below.</p>`;
      return;
    }
    const html = fields
      .map((f) => {
        const id = `skill_field_${f.key}`;
        if (f.type === "select") {
          const opts = f.options
            .map((o) => `<option value="${esc(o.value)}" ${o.value === f.value ? "selected" : ""}>${esc(o.label)}</option>`)
            .join("");
          return `<label>${esc(f.label)}<select id="${id}" data-key="${esc(f.key)}" data-type="select">${opts}</select></label>`;
        }
        if (f.type === "checkbox") {
          return `<label class="checkbox-label"><input id="${id}" data-key="${esc(f.key)}" data-type="checkbox" type="checkbox" ${f.value ? "checked" : ""}/><span>${esc(f.label)}</span></label>`;
        }
        if (f.type === "json") {
          return `<label class="full-span">${esc(f.label)}<textarea id="${id}" data-key="${esc(f.key)}" data-type="json" class="code-editor sm" spellcheck="false">${esc(f.value)}</textarea></label>`;
        }
        const stepAttr = f.step ? `step="${esc(f.step)}"` : "";
        return `<label>${esc(f.label)}<input id="${id}" data-key="${esc(f.key)}" data-type="${esc(f.type)}" type="${esc(f.type)}" ${stepAttr} value="${esc(f.value)}"/></label>`;
      })
      .join("");
    container.innerHTML = `<div class="form-grid">${html}</div>`;
  }

  function readForm(container) {
    const out = {};
    container.querySelectorAll("[data-key]").forEach((el) => {
      const key = el.dataset.key;
      const type = el.dataset.type;
      if (type === "checkbox") {
        out[key] = el.checked;
      } else if (type === "number") {
        out[key] = el.value === "" ? 0 : Number(el.value);
      } else if (type === "json") {
        out[key] = JSON.parse(el.value);
      } else {
        out[key] = el.value;
      }
    });
    return out;
  }

  function renderResult(container, result) {
    if (!result) {
      container.innerHTML = `<p class="muted">Run this calculator to view metrics, charts, tables, and recommendations.</p>`;
      return;
    }

    const metricsHtml = (result.metrics || [])
      .map(
        (m) => `
        <div class="metric-card tone-${esc(m.tone || "neutral")}">
          <div class="metric-label">${esc(m.label)}</div>
          <div class="metric-value">${esc(m.value)}</div>
        </div>`
      )
      .join("");

    const chartHtml = window.FinanceCharts.renderChart(result.chart);

    const tablesHtml = (result.tables || [])
      .map((t) => {
        const ths = (t.columns || []).map((c) => `<th>${esc(c)}</th>`).join("");
        const trs = (t.rows || [])
          .map((row) => `<tr>${row.map((cell) => `<td>${esc(cell)}</td>`).join("")}</tr>`)
          .join("");
        return `
          <div class="table-block">
            <h4>${esc(t.title)}</h4>
            <div class="table-scroll">
              <table class="data-table">
                <thead><tr>${ths}</tr></thead>
                <tbody>${trs}</tbody>
              </table>
            </div>
          </div>`;
      })
      .join("");

    const recsHtml = (result.recommendations || []).length
      ? `<div class="recs-block"><h4>Recommended Actions</h4><ul>${result.recommendations.map((r) => `<li>${esc(r)}</li>`).join("")}</ul></div>`
      : "";

    container.innerHTML = `
      <div class="result-summary">${esc(result.summary || "")}</div>
      <div class="metrics-grid">${metricsHtml}</div>
      ${chartHtml}
      ${tablesHtml}
      ${recsHtml}
    `;
  }

  return { getFields, renderForm, readForm, renderResult };
})();
