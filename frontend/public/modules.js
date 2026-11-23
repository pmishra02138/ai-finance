/* Spec-driven form builder & result renderer (Deterministic + Monte Carlo) */

window.FinanceModules = (function () {
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

  function getByPath(obj, dotPath) {
    if (!obj || !dotPath) return undefined;
    return dotPath.split(".").reduce((cur, key) => (cur && cur[key] !== undefined ? cur[key] : undefined), obj);
  }

  function resolveFieldDefault(specField, plan) {
    if (specField.plan_path) {
      const val = getByPath(plan, specField.plan_path);
      if (val !== undefined && val !== null) return val;
    }
    if (specField.plan_agg === "sum_expenses") {
      const total = sumExpenses(plan);
      if (total > 0) return total;
    } else if (specField.plan_agg === "sum_debt") {
      const total = sumDebt(plan);
      if (total > 0) return total;
    } else if (specField.plan_agg === "gross_annual_income") {
      const gross = getByPath(plan, "cash_flow.gross_annual_income");
      if (gross !== undefined && gross !== null) return Number(gross);
      const mo = getByPath(plan, "cash_flow.monthly_income");
      if (mo !== undefined && mo !== null) return Math.round((Number(mo) * 12) / 0.76);
    } else if (specField.plan_agg === "annual_income") {
      const mo = getByPath(plan, "cash_flow.monthly_income");
      if (mo !== undefined && mo !== null) return Number(mo) * 12;
    }
    return specField.default;
  }

  function getFields(moduleMeta, plan, savedInputs) {
    const specFields = (moduleMeta && Array.isArray(moduleMeta.fields) ? moduleMeta.fields : []) || [];
    return specFields.map((f) => {
      const baseVal = resolveFieldDefault(f, plan || {});
      const hasSaved = !f.prefer_plan && savedInputs && savedInputs[f.key] !== undefined;
      let val = hasSaved ? savedInputs[f.key] : baseVal;
      if (f.type === "json" && typeof val !== "string") {
        val = JSON.stringify(val, null, 2);
      }
      return { ...f, value: val };
    });
  }

  function renderDebtRow(acc = {}) {
    return `
      <div class="debt-row">
        <input type="text" class="debt-name" placeholder="Account name (e.g. Visa)" value="${esc(acc.name || "")}" />
        <input type="number" class="debt-balance" placeholder="Balance ($)" min="0" value="${esc(acc.balance ?? 0)}" />
        <input type="number" class="debt-apr" placeholder="APR (%)" min="0" step="0.1" value="${esc(acc.apr ?? 0)}" />
        <input type="number" class="debt-min" placeholder="Min Pmt ($)" min="0" value="${esc(acc.min_payment ?? 0)}" />
        <button type="button" class="btn ghost-danger sm remove-debt-btn" title="Remove account">Remove</button>
      </div>
    `;
  }

  function renderForm(container, fields, formNote = "") {
    if (!fields.length) {
      container.innerHTML = `<p class="muted">This module uses your active saved financial plan directly. Click <strong>Preview Results</strong> to check readiness or export your 9-page PDF above.</p>`;
      return;
    }
    const noteHtml = formNote ? `<div class="form-note">${esc(formNote)}</div>` : "";
    const html = fields
      .map((f) => {
        const id = `module_field_${f.key}`;
        if (f.type === "select") {
          const opts = (f.options || [])
            .map((o) => `<option value="${esc(o.value)}" ${o.value === f.value ? "selected" : ""}>${esc(o.label)}</option>`)
            .join("");
          return `<label>${esc(f.label)}<select id="${id}" data-key="${esc(f.key)}" data-type="select">${opts}</select></label>`;
        }
        if (f.type === "checkbox") {
          return `<label class="checkbox-label"><input id="${id}" data-key="${esc(f.key)}" data-type="checkbox" type="checkbox" ${f.value ? "checked" : ""}/><span>${esc(f.label)}</span></label>`;
        }
        if (f.type === "debt_list") {
          const list = Array.isArray(f.value) ? f.value : [];
          const rowsHtml = list.map((acc) => renderDebtRow(acc)).join("");
          return `
            <div class="full-span debt-editor" data-key="${esc(f.key)}" data-type="debt_list">
              <div class="debt-editor-head">
                <span class="debt-editor-label">${esc(f.label)}</span>
                <button type="button" class="btn ghost sm add-debt-btn">+ Add Debt Account</button>
              </div>
              <div class="debt-cols-head">
                <span>Account Name</span><span>Balance ($)</span><span>APR (%)</span><span>Min Payment ($)</span><span></span>
              </div>
              <div class="debt-rows">${rowsHtml}</div>
            </div>
          `;
        }
        if (f.type === "json") {
          return `<label class="full-span">${esc(f.label)}<textarea id="${id}" data-key="${esc(f.key)}" data-type="json" class="code-editor sm" spellcheck="false">${esc(f.value)}</textarea></label>`;
        }
        const stepAttr = f.step ? `step="${esc(f.step)}"` : "";
        const roAttr = f.read_only ? `readonly aria-readonly="true" class="readonly-input"` : "";
        return `<label>${esc(f.label)}<input id="${id}" data-key="${esc(f.key)}" data-type="${esc(f.type)}" type="${esc(f.type)}" ${stepAttr} ${roAttr} value="${esc(f.value)}"/></label>`;
      })
      .join("");
    container.innerHTML = `${noteHtml}<div class="form-grid">${html}</div>`;

    container.querySelectorAll(".add-debt-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        const rows = btn.closest(".debt-editor").querySelector(".debt-rows");
        rows.insertAdjacentHTML("beforeend", renderDebtRow({ name: "", balance: 0, apr: 0, min_payment: 0 }));
      });
    });
    container.addEventListener("click", (e) => {
      if (e.target.classList.contains("remove-debt-btn")) {
        e.target.closest(".debt-row").remove();
      }
    });
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
      } else if (type === "debt_list") {
        const accounts = [];
        el.querySelectorAll(".debt-row").forEach((row) => {
          const name = row.querySelector(".debt-name").value.trim();
          const balance = Number(row.querySelector(".debt-balance").value || 0);
          const apr = Number(row.querySelector(".debt-apr").value || 0);
          const min_payment = Number(row.querySelector(".debt-min").value || 0);
          if (name || balance > 0) {
            accounts.push({ name: name || "Debt Account", balance, apr, min_payment });
          }
        });
        out[key] = accounts;
      } else if (type === "json") {
        out[key] = JSON.parse(el.value);
      } else {
        out[key] = el.value;
      }
    });
    return out;
  }

  function renderMonteCarloPanel(mc) {
    if (!mc) return "";
    const prob = Math.max(0, Math.min(100, Number(mc.success_rate_pct || 0)));
    const probColor = window.FinanceCharts.scoreColor(prob);
    const pctItems = (mc.percentiles || [])
      .map(
        (p, idx) => `
        <div class="mc-pct-item ${idx === 1 ? "mc-pct-median" : ""}">
          <div class="mc-pct-label">${esc(p.label)}</div>
          <div class="mc-pct-value">${esc(p.value)}</div>
        </div>`
      )
      .join("");

    return `
      <div class="mc-panel">
        <div class="mc-panel-head">
          <h4>Deterministic Baseline vs. Monte Carlo Simulation</h4>
          <span class="mc-meta-badge">${esc(mc.trials)} trials • ${esc(mc.volatility_pct)}% vol</span>
        </div>
        <div class="mc-compare-grid">
          <div class="mc-card">
            <div class="mc-card-kicker">Deterministic Baseline</div>
            <div class="mc-card-label">${esc(mc.baseline_label)}</div>
            <div class="mc-card-value">${esc(mc.baseline_value)}</div>
          </div>
          <div class="mc-card mc-card-prob">
            <div class="mc-card-kicker">Monte Carlo Probability</div>
            <div class="mc-card-label">${esc(mc.success_label)}</div>
            <div class="mc-card-value" style="color:${probColor}">${prob.toFixed(1)}%</div>
            <div class="mc-prob-track"><div class="mc-prob-fill" style="width:${prob}%;background:${probColor}"></div></div>
          </div>
        </div>
        <div class="mc-percentiles">${pctItems}</div>
        <p class="mc-note">${esc(mc.note || "")}</p>
      </div>
    `;
  }

  function priorityTone(prio) {
    const p = String(prio || "Med").toLowerCase();
    if (p.includes("high") || p.includes("crit")) return { cls: "high", label: "High" };
    if (p.includes("low")) return { cls: "low", label: "Low" };
    return { cls: "med", label: "Med" };
  }

  function renderActionItems(items, heading = "Top Prioritized Action Items") {
    const list = Array.isArray(items) ? items : [];
    if (!list.length) return "";
    const rows = list
      .map((a) => {
        const tone = priorityTone(a.priority);
        const cat = a.category ? `<span class="action-tag">${esc(a.category)}</span>` : "";
        const imp = a.impact ? `<span class="action-impact">Impact: ${esc(a.impact)}</span>` : "";
        return `
          <div class="action-item prio-${tone.cls}">
            <span class="prio-badge prio-${tone.cls}">${tone.label}</span>
            <div class="action-body">
              <div class="action-text">${esc(a.action || "")}</div>
              <div class="action-meta">${cat}${imp}</div>
            </div>
          </div>`;
      })
      .join("");

    return `
      <div class="actions-section">
        <div class="actions-header">
          <h4>${esc(heading)}</h4>
          <div class="prio-legend" aria-label="Priority color legend">
            <span class="legend-chip"><span class="legend-dot high"></span>High = Urgent</span>
            <span class="legend-chip"><span class="legend-dot med"></span>Med = 30–90 days</span>
            <span class="legend-chip"><span class="legend-dot low"></span>Low = Quick win</span>
          </div>
        </div>
        <div class="action-list">${rows}</div>
      </div>
    `;
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

    const mcHtml = renderMonteCarloPanel(result.monte_carlo);
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

    const actionsHtml = renderActionItems(result.action_items);

    const recsHtml = (result.recommendations || []).length
      ? `<div class="recs-block"><h4>Key Takeaways</h4><ul>${result.recommendations.map((r) => `<li>${esc(r)}</li>`).join("")}</ul></div>`
      : "";

    container.innerHTML = `
      <div class="result-summary">${esc(result.summary || "")}</div>
      <div class="metrics-grid">${metricsHtml}</div>
      ${mcHtml}
      ${chartHtml}
      ${tablesHtml}
      ${actionsHtml}
      ${recsHtml}
    `;
  }

  return { getFields, renderForm, readForm, renderResult, renderActionItems };
})();
