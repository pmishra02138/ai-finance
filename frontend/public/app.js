const state = {
  token: localStorage.getItem("ai_finance_token") || "",
  user: null,
  plans: [],
  activePlanId: null,
  activePayload: null,
  catalog: { stages: [], modules: [] },
  moduleRuns: {},
  activeModuleName: null, // null = Overview view
  copilotHistory: [],
};

const $ = (id) => document.getElementById(id);

function showStatus(msg, isError = false) {
  const el = $("statusBanner");
  el.textContent = msg;
  el.classList.toggle("error", isError);
  el.classList.remove("hidden");
  setTimeout(() => el.classList.add("hidden"), 5000);
}

async function apiFetch(path, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (state.token) {
    headers["Authorization"] = `Bearer ${state.token}`;
  }
  if (options.body && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }
  const res = await fetch(`/api${path}`, { ...options, headers });
  if (res.status === 401 && !path.startsWith("/auth/")) {
    handleSignOut(false);
    throw new Error("Session expired. Please sign in again.");
  }
  return res;
}

function renderPlanHeader() {
  const p = state.activePayload || {};
  const score = Number(p.health_score || 0);
  $("gaugeContainer").innerHTML = window.FinanceCharts.renderGaugeSVG(score);
  $("planTitleHeading").textContent = p.client_name || "Personal Financial Plan";
  $("gradeBadge").textContent = p.grade || "--";
  $("signalText").textContent = p.signal || "";

  const cats = p.categories || {};
  const entries = [
    ["Cash Flow", Number(cats.cash_flow || 0)],
    ["Debt", Number(cats.debt || 0)],
    ["Investments", Number(cats.investments || 0)],
    ["Retirement", Number(cats.retirement || 0)],
    ["Protection", Number(cats.protection || 0)],
  ];
  const container = $("categoryBars");
  container.innerHTML = "";
  for (const [label, val] of entries) {
    const pct = Math.max(0, Math.min(100, val));
    const row = document.createElement("div");
    row.className = "bar-row";
    row.innerHTML = `
      <strong>${label}</strong>
      <div class="bar-track"><div class="bar-fill" style="width:${pct}%;background:${window.FinanceCharts.scoreColor(pct)}"></div></div>
      <span>${Math.round(pct)}/100</span>
    `;
    container.appendChild(row);
  }

  const esc = window.FinanceCharts.escapeHtml;
  $("overviewSummary").textContent = p.executive_summary || "Select any module in the 5-stage sidebar to run an interactive analysis.";
  const cf = p.cash_flow || {};
  const inv = p.investments || {};
  const ret = p.retirement || {};
  const debtAccs = (p.debt && p.debt.accounts) || [];
  const totalDebt = debtAccs.reduce((acc, d) => acc + Number(d.balance || 0), 0);
  $("overviewMetrics").innerHTML = `
    <div class="metric-card"><div class="metric-label">Monthly Income</div><div class="metric-value">$${Number(cf.monthly_income || 0).toLocaleString()}</div></div>
    <div class="metric-card"><div class="metric-label">Invested Assets</div><div class="metric-value">$${Number(inv.total_value || 0).toLocaleString()}</div></div>
    <div class="metric-card"><div class="metric-label">Total Debt</div><div class="metric-value">$${Math.round(totalDebt).toLocaleString()}</div></div>
    <div class="metric-card"><div class="metric-label">Retirement Goal</div><div class="metric-value">$${Number(ret.target_balance || 0).toLocaleString()}</div></div>
  `;
  const actions = (p.action_items || []).slice(0, 6);
  $("overviewActions").innerHTML = window.FinanceModules.renderActionItems(actions, "Top Prioritized Action Items");
}

function renderStageNav() {
  const nav = $("stageNav");
  nav.innerHTML = "";
  const completedCount = Object.keys(state.moduleRuns).length;
  $("completionPill").textContent = `${completedCount}/${state.catalog.modules.length || 10}`;

  for (const stage of state.catalog.stages || []) {
    const group = document.createElement("div");
    group.className = "stage-group";
    group.dataset.stage = stage.id;
    const title = document.createElement("div");
    title.className = "stage-group-title";
    title.textContent = stage.title;
    group.appendChild(title);

    for (const mod of stage.modules) {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "module-btn" + (state.activeModuleName === mod.name ? " active" : "");
      const run = state.moduleRuns[mod.name];
      const esc = window.FinanceCharts.escapeHtml;
      const pillarTag = mod.pillar
        ? `<span class="score-star" title="Counts toward Health Score (${esc(mod.pillar)})">★</span>`
        : "";
      let statusDot = '<span class="pending-dot" title="Not run yet">○</span>';
      if (run) {
        const isPreviewOnly = mod.syncs_to_plan !== false && run.outputs && run.outputs._synced === false;
        if (isPreviewOnly) {
          statusDot = '<span class="check-dot preview" title="Previewed only — click Save to My Plan to sync">✓</span>';
        } else if (mod.syncs_to_plan === false) {
          statusDot = '<span class="check-dot" title="Calculated">✓</span>';
        } else {
          statusDot = '<span class="check-dot" title="Saved to My Plan">✓✓</span>';
        }
      }
      btn.innerHTML = `<span class="module-btn-main"><span>${esc(mod.label)}</span>${pillarTag}</span>${statusDot}`;
      btn.addEventListener("click", () => openModule(mod.name));
      group.appendChild(btn);
    }
    nav.appendChild(group);
  }
}

function openOverview() {
  state.activeModuleName = null;
  $("overviewNavBtn").classList.add("active");
  $("scoreBannerCard").classList.remove("hidden");
  $("overviewPanel").classList.remove("hidden");
  $("modulePanel").classList.add("hidden");
  renderPlanHeader();
  renderStageNav();
}

function setModuleStatusBadge(label, isPreview = false) {
  const badge = $("moduleStatusBadge");
  if (!label) {
    badge.innerHTML = "";
    badge.classList.remove("preview");
    badge.classList.add("hidden");
    return;
  }
  const esc = window.FinanceCharts.escapeHtml;
  badge.classList.toggle("preview", isPreview);
  badge.innerHTML = `<span class="pill-check" aria-hidden="true">${isPreview ? "!" : "✓"}</span><span>${esc(label)}</span>`;
  badge.classList.remove("hidden");
}

function openModule(moduleName) {
  const meta = (state.catalog.modules || []).find((m) => m.name === moduleName);
  if (!meta) return;
  state.activeModuleName = moduleName;
  $("overviewNavBtn").classList.remove("active");
  // Show full Financial Health Score + PDF banner only on Plan Overview and Full Health Analysis
  $("scoreBannerCard").classList.toggle("hidden", moduleName !== "finance-analyze");
  $("overviewPanel").classList.add("hidden");
  $("modulePanel").classList.remove("hidden");
  $("moduleHeaderCard").dataset.stage = meta.stage_id;

  $("moduleStageKicker").textContent = meta.stage_title;
  const pillarBadge = $("modulePillarBadge");
  if (meta.pillar) {
    pillarBadge.textContent = `Counts Toward Health Score • ${meta.pillar}`;
    pillarBadge.classList.remove("hidden");
  } else if (meta.name === "finance-analyze") {
    pillarBadge.textContent = "Overall Health Score";
    pillarBadge.classList.remove("hidden");
  } else {
    pillarBadge.textContent = "Informational • Not in Health Score";
    pillarBadge.classList.remove("hidden");
  }

  $("moduleHeading").textContent = meta.label;
  $("moduleDesc").textContent = meta.description;
  $("runAndSyncBtn").classList.toggle("hidden", meta.syncs_to_plan === false);

  const saved = state.moduleRuns[moduleName];
  if (!saved) {
    setModuleStatusBadge("");
  } else if (meta.syncs_to_plan !== false && saved.outputs && saved.outputs._synced === false) {
    setModuleStatusBadge("Preview only (not synced to plan)", true);
  } else if (meta.syncs_to_plan === false) {
    setModuleStatusBadge("Calculated");
  } else {
    setModuleStatusBadge("Saved to My Plan");
  }

  const fields = window.FinanceModules.getFields(meta, state.activePayload, saved && saved.inputs);
  window.FinanceModules.renderForm($("moduleFormContainer"), fields, meta.form_note || "");
  window.FinanceModules.renderResult($("moduleResultContainer"), saved && saved.outputs);
  renderStageNav();

  // If Full Health Analysis was run earlier (or any upstream pillar changed), auto-refresh with latest synced scores
  if (moduleName === "finance-analyze" && state.activePlanId) {
    const stale =
      !saved ||
      fields.some((f) => saved.inputs && Number(saved.inputs[f.key]) !== Number(f.value));
    if (stale) {
      executeActiveModule(false);
    }
  }
}

async function executeActiveModule(syncToPlan) {
  if (!state.activePlanId || !state.activeModuleName) return;
  try {
    const inputs = window.FinanceModules.readForm($("moduleFormContainer"));
    const res = await apiFetch(`/plans/${state.activePlanId}/modules/${state.activeModuleName}/run`, {
      method: "POST",
      body: JSON.stringify({ inputs, sync_to_plan: syncToPlan }),
    });
    if (!res.ok) {
      const err = await res.text();
      showStatus(`Unable to run calculation: ${err}`, true);
      return;
    }
    const data = await res.json();
    state.moduleRuns[state.activeModuleName] = data.run;
    if (data.updated_plan) {
      state.activePayload = data.updated_plan.payload;
      await refreshPlanListOnly();
      renderPlanHeader();
    }
    const activeMeta = (state.catalog.modules || []).find((m) => m.name === state.activeModuleName);
    if (activeMeta && activeMeta.syncs_to_plan === false) {
      setModuleStatusBadge("Calculated");
    } else {
      setModuleStatusBadge(
        syncToPlan ? "Saved to My Plan" : "Preview only (not synced to plan)",
        !syncToPlan
      );
    }
    window.FinanceModules.renderResult($("moduleResultContainer"), data.result);
    renderStageNav();
  } catch (err) {
    showStatus(`Input or network error: ${err.message}`, true);
  }
}

function renderPlanSelect() {
  const sel = $("planSelect");
  sel.innerHTML = "";
  for (const plan of state.plans) {
    const opt = document.createElement("option");
    opt.value = String(plan.id);
    opt.textContent = `${plan.title} (${Math.round(plan.health_score)} • ${plan.grade})`;
    if (plan.id === state.activePlanId) opt.selected = true;
    sel.appendChild(opt);
  }
}

async function refreshPlanListOnly() {
  const res = await apiFetch("/plans");
  if (!res.ok) return;
  const data = await res.json();
  state.plans = data.plans || [];
  renderPlanSelect();
}

async function selectPlan(planId) {
  const [planRes, runsRes] = await Promise.all([
    apiFetch(`/plans/${planId}`),
    apiFetch(`/plans/${planId}/modules`),
  ]);
  if (!planRes.ok) {
    showStatus("Failed to load plan", true);
    return;
  }
  const plan = await planRes.json();
  state.activePlanId = plan.id;
  state.activePayload = plan.payload;
  state.copilotHistory = [];
  renderCopilotMessages();
  state.moduleRuns = {};
  if (runsRes.ok) {
    const runsData = await runsRes.json();
    for (const r of runsData.runs || []) {
      state.moduleRuns[r.module_name] = r;
    }
  }
  renderPlanSelect();
  renderPlanHeader();
  if (state.activeModuleName) {
    openModule(state.activeModuleName);
  } else {
    renderStageNav();
  }
}

async function loadInitialAppData() {
  const [modulesRes, plansRes] = await Promise.all([apiFetch("/modules"), apiFetch("/plans")]);
  if (modulesRes.ok) {
    state.catalog = await modulesRes.json();
  }
  if (plansRes.ok) {
    const data = await plansRes.json();
    state.plans = data.plans || [];
  }
  if (state.plans.length === 0) {
    const demoRes = await apiFetch("/demo-data");
    const demo = await demoRes.json();
    const createRes = await apiFetch("/plans", {
      method: "POST",
      body: JSON.stringify({ title: demo.client_name, payload: demo }),
    });
    if (createRes.ok) {
      const created = await createRes.json();
      state.plans = [created];
    }
  }
  if (state.plans.length > 0) {
    await selectPlan(state.plans[0].id);
  }
  openOverview();
}

function openNewPlanPrompt() {
  $("newPlanNameInput").value = "";
  $("newPlanTemplate").value = "sample";
  $("newPlanModal").classList.remove("hidden");
  $("newPlanNameInput").focus();
}

function closeNewPlanPrompt() {
  $("newPlanModal").classList.add("hidden");
}

async function createNewPlan() {
  const customName = $("newPlanNameInput").value.trim();
  const template = $("newPlanTemplate").value;
  const planTitle = customName || `Financial Plan (${new Date().toLocaleDateString()})`;
  let payload;
  if (template === "blank") {
    payload = {
      client_name: planTitle,
      health_score: 0,
      grade: "--",
      signal: "New Plan — Run Modules to Score",
      categories: { cash_flow: 0, debt: 0, investments: 0, retirement: 0, protection: 0 },
      cash_flow: { monthly_income: 0, gross_annual_income: 0, expenses: [] },
      debt: { accounts: [] },
      investments: { total_value: 0, allocation: [] },
      retirement: { current_age: 35, retirement_age: 65, current_balance: 0, target_balance: 0, monthly_contribution: 0 },
      protection: { items: [] },
      action_items: [],
    };
  } else {
    const demoRes = await apiFetch("/demo-data");
    payload = await demoRes.json();
    payload.client_name = planTitle;
  }
  const res = await apiFetch("/plans", {
    method: "POST",
    body: JSON.stringify({ title: planTitle, payload }),
  });
  if (!res.ok) {
    showStatus("Failed to create plan", true);
    return;
  }
  const created = await res.json();
  closeNewPlanPrompt();
  await refreshPlanListOnly();
  await selectPlan(created.id);
  showStatus(`Created "${planTitle}".`);
}

function requestResetPlanConfirmation() {
  if (!state.activePlanId) return;
  const activePlan = state.plans.find((p) => p.id === state.activePlanId);
  const planName = (activePlan && activePlan.title) || "this financial plan";
  $("resetModalBody").textContent = `This will clear all saved module analyses in "${planName}" and reset it to your chosen starting point.`;
  $("resetPlanTemplate").value = "blank";
  $("resetPlanModal").classList.remove("hidden");
}

function closeResetModal() {
  $("resetPlanModal").classList.add("hidden");
}

async function confirmResetActivePlan() {
  if (!state.activePlanId) return;
  const template = $("resetPlanTemplate").value || "blank";
  closeResetModal();
  const res = await apiFetch(`/plans/${state.activePlanId}/reset`, {
    method: "POST",
    body: JSON.stringify({ template }),
  });
  if (!res.ok) {
    showStatus("Failed to reset plan", true);
    return;
  }
  await refreshPlanListOnly();
  await selectPlan(state.activePlanId);
  openOverview();
  showStatus(`Plan reset to ${template === "sample" ? "sample defaults" : "blank"}.`);
}

function requestDeletePlanConfirmation() {
  if (!state.activePlanId) return;
  const activePlan = state.plans.find((p) => p.id === state.activePlanId);
  const planName = (activePlan && activePlan.title) || "this financial plan";
  $("confirmModalBody").textContent = `This will permanently delete "${planName}" and all saved analyses. This action cannot be undone.`;
  $("confirmModal").classList.remove("hidden");
}

function closeDeleteModal() {
  $("confirmModal").classList.add("hidden");
}

async function confirmDeleteActivePlan() {
  if (!state.activePlanId) return;
  closeDeleteModal();
  const res = await apiFetch(`/plans/${state.activePlanId}`, { method: "DELETE" });
  if (!res.ok) {
    showStatus("Failed to delete plan", true);
    return;
  }
  state.activePlanId = null;
  await loadInitialAppData();
  showStatus("Financial plan deleted.");
}

function toggleCopilotDrawer() {
  const drawer = $("copilotDrawer");
  if (drawer.classList.contains("hidden")) {
    drawer.classList.remove("hidden", "minimized");
    $("copilotMinimizeBtn").textContent = "−";
    $("copilotMinimizeBtn").title = "Minimize";
    renderCopilotMessages();
    $("copilotInput").focus();
  } else if (drawer.classList.contains("minimized")) {
    drawer.classList.remove("minimized");
    $("copilotMinimizeBtn").textContent = "−";
    $("copilotMinimizeBtn").title = "Minimize";
    $("copilotInput").focus();
  } else {
    drawer.classList.add("hidden");
  }
}

function toggleCopilotMinimize() {
  const drawer = $("copilotDrawer");
  const minimized = drawer.classList.toggle("minimized");
  $("copilotMinimizeBtn").textContent = minimized ? "□" : "−";
  $("copilotMinimizeBtn").title = minimized ? "Restore" : "Minimize";
}

function formatCopilotHtml(raw) {
  const esc = window.FinanceCharts.escapeHtml;
  const formatInline = (s) =>
    esc(s)
      .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
      .replace(/(^|[^*])\*([^*\n]+?)\*(?!\*)/g, "$1<em>$2</em>")
      .replace(/`([^`]+)`/g, "<code>$1</code>");

  const splitTableRow = (line) =>
    line
      .replace(/^\|/, "")
      .replace(/\|$/, "")
      .split("|")
      .map((cell) => cell.trim());

  const isTableSep = (line) => /^\|?(\s*:?-{2,}:?\s*\|)+\s*:?-{2,}:?\s*\|?$/.test(line);

  const lines = String(raw || "").replace(/\r\n/g, "\n").split("\n");
  const html = [];
  let listType = null; // "ul" | "ol"
  let tableRows = [];

  const closeList = () => {
    if (listType) {
      html.push(`</${listType}>`);
      listType = null;
    }
  };

  const flushTable = () => {
    if (tableRows.length === 0) return;
    const [head, ...body] = tableRows;
    html.push('<div class="copilot-table-wrap"><table class="copilot-table"><thead><tr>');
    for (const h of head) html.push(`<th>${formatInline(h)}</th>`);
    html.push("</tr></thead>");
    if (body.length > 0) {
      html.push("<tbody>");
      for (const r of body) {
        html.push("<tr>");
        for (const c of r) html.push(`<td>${formatInline(c)}</td>`);
        html.push("</tr>");
      }
      html.push("</tbody>");
    }
    html.push("</table></div>");
    tableRows = [];
  };

  for (const rawLine of lines) {
    const line = rawLine.trim();
    if (!line) {
      closeList();
      flushTable();
      continue;
    }
    if (line.startsWith("|") && line.includes("|", 1)) {
      closeList();
      if (!isTableSep(line)) {
        tableRows.push(splitTableRow(line));
      }
      continue;
    }
    flushTable();

    if (/^-{3,}$/.test(line)) {
      closeList();
      html.push("<hr />");
      continue;
    }
    const ulMatch = line.match(/^[-*•]\s+(.*)$/);
    const olMatch = line.match(/^\d+[.)]\s+(.*)$/);
    const hMatch = line.match(/^#{1,4}\s+(.*)$/);

    if (hMatch) {
      closeList();
      html.push(`<h4>${formatInline(hMatch[1])}</h4>`);
    } else if (ulMatch) {
      if (listType !== "ul") {
        closeList();
        listType = "ul";
        html.push("<ul>");
      }
      html.push(`<li>${formatInline(ulMatch[1])}</li>`);
    } else if (olMatch) {
      if (listType !== "ol") {
        closeList();
        listType = "ol";
        html.push("<ol>");
      }
      html.push(`<li>${formatInline(olMatch[1])}</li>`);
    } else {
      closeList();
      html.push(`<p>${formatInline(line)}</p>`);
    }
  }
  closeList();
  flushTable();
  return html.join("");
}

function renderCopilotMessages() {
  const box = $("copilotMessages");
  if (!box) return;
  box.innerHTML = "";
  if (state.copilotHistory.length === 0) {
    const welcome = document.createElement("div");
    welcome.className = "copilot-msg assistant";
    welcome.innerHTML = "<p>Ask me anything about your active financial plan—your health score, debt payoff, tax headroom, or retirement Monte Carlo outlook. <em>(Educational summary only.)</em></p>";
    box.appendChild(welcome);
    return;
  }
  for (const m of state.copilotHistory) {
    const div = document.createElement("div");
    div.className = `copilot-msg ${m.role === "user" ? "user" : (m.isError ? "error" : "assistant")}`;
    if (m.role === "user" || m.isError) {
      div.textContent = m.content;
    } else {
      div.innerHTML = formatCopilotHtml(m.content);
    }
    box.appendChild(div);
  }
  box.scrollTop = box.scrollHeight;
}

async function sendCopilotMessage(message) {
  if (!state.activePlanId) return;
  $("copilotDrawer").classList.remove("hidden");
  const priorHistory = state.copilotHistory.filter((m) => !m.isError).map((m) => ({ role: m.role, content: m.content }));
  state.copilotHistory.push({ role: "user", content: message });
  renderCopilotMessages();

  const sendBtn = $("copilotSendBtn");
  sendBtn.disabled = true;
  sendBtn.textContent = "...";
  try {
    const res = await apiFetch(`/plans/${state.activePlanId}/chat`, {
      method: "POST",
      body: JSON.stringify({ message, history: priorHistory }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      state.copilotHistory.push({ role: "assistant", content: data.detail || "Copilot request failed.", isError: true });
    } else {
      state.copilotHistory.push({ role: "assistant", content: data.reply || "No reply returned." });
    }
  } catch (_err) {
    state.copilotHistory.push({ role: "assistant", content: "Network error reaching Plan Insights.", isError: true });
  } finally {
    sendBtn.disabled = false;
    sendBtn.textContent = "Send";
    renderCopilotMessages();
  }
}

async function fetchPdf(inline) {
  if (!state.activePlanId) return;
  const res = await apiFetch(`/plans/${state.activePlanId}/pdf${inline ? "?inline=true" : ""}`);
  if (!res.ok) {
    showStatus("PDF generation failed", true);
    return;
  }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  if (inline) {
    window.open(url, "_blank");
    setTimeout(() => URL.revokeObjectURL(url), 60000);
  } else {
    const a = document.createElement("a");
    a.href = url;
    a.download = `FINANCE-PLAN-${state.activePlanId}.pdf`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  }
}

async function handleAuthSubmit(path, username, password, errorEl) {
  errorEl.classList.add("hidden");
  try {
    const res = await apiFetch(path, {
      method: "POST",
      body: JSON.stringify({ username, password }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: "Authentication failed" }));
      errorEl.textContent = err.detail || "Authentication failed";
      errorEl.classList.remove("hidden");
      return;
    }
    const data = await res.json();
    state.token = data.token;
    state.user = data.user;
    localStorage.setItem("ai_finance_token", state.token);
    showApp();
    await loadInitialAppData();
  } catch (err) {
    errorEl.textContent = err.message;
    errorEl.classList.remove("hidden");
  }
}

async function handleSignOut(callApi = true) {
  if (callApi && state.token) {
    await apiFetch("/auth/logout", { method: "POST" }).catch(() => {});
  }
  state.token = "";
  state.user = null;
  state.plans = [];
  state.activePlanId = null;
  state.moduleRuns = {};
  localStorage.removeItem("ai_finance_token");
  $("loginView").classList.remove("hidden");
  $("appView").classList.add("hidden");
  $("userControls").classList.add("hidden");
  $("copilotToggleBtn").classList.add("hidden");
  $("copilotDrawer").classList.add("hidden");
}

function showApp() {
  $("loginView").classList.add("hidden");
  $("appView").classList.remove("hidden");
  $("userControls").classList.remove("hidden");
  $("copilotToggleBtn").classList.remove("hidden");
  $("userBadge").textContent = state.user ? state.user.username : "user";
}

async function bootstrap() {
  $("tabSignIn").addEventListener("click", () => {
    $("tabSignIn").classList.add("active");
    $("tabRegister").classList.remove("active");
    $("loginForm").classList.remove("hidden");
    $("registerForm").classList.add("hidden");
  });
  $("tabRegister").addEventListener("click", () => {
    $("tabRegister").classList.add("active");
    $("tabSignIn").classList.remove("active");
    $("registerForm").classList.remove("hidden");
    $("loginForm").classList.add("hidden");
  });

  $("loginForm").addEventListener("submit", (e) => {
    e.preventDefault();
    handleAuthSubmit("/auth/login", $("usernameInput").value.trim(), $("passwordInput").value, $("loginError"));
  });
  $("registerForm").addEventListener("submit", (e) => {
    e.preventDefault();
    handleAuthSubmit("/auth/register", $("regUsernameInput").value.trim(), $("regPasswordInput").value, $("registerError"));
  });

  $("logoutBtn").addEventListener("click", () => handleSignOut(true));
  $("planSelect").addEventListener("change", (e) => selectPlan(Number(e.target.value)));
  $("newPlanBtn").addEventListener("click", openNewPlanPrompt);
  $("confirmNewPlanBtn").addEventListener("click", createNewPlan);
  $("cancelNewPlanBtn").addEventListener("click", closeNewPlanPrompt);
  $("newPlanNameInput").addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      createNewPlan();
    } else if (e.key === "Escape") {
      closeNewPlanPrompt();
    }
  });
  $("overviewNavBtn").addEventListener("click", openOverview);
  $("resetPlanBtn").addEventListener("click", requestResetPlanConfirmation);
  $("resetCancelBtn").addEventListener("click", closeResetModal);
  $("confirmResetBtn").addEventListener("click", confirmResetActivePlan);
  $("deletePlanBtn").addEventListener("click", requestDeletePlanConfirmation);
  $("confirmCancelBtn").addEventListener("click", closeDeleteModal);
  $("confirmDeleteBtn").addEventListener("click", confirmDeleteActivePlan);
  $("newPlanModal").addEventListener("click", (e) => {
    if (e.target === $("newPlanModal")) closeNewPlanPrompt();
  });
  $("resetPlanModal").addEventListener("click", (e) => {
    if (e.target === $("resetPlanModal")) closeResetModal();
  });
  $("confirmModal").addEventListener("click", (e) => {
    if (e.target === $("confirmModal")) closeDeleteModal();
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      if (!$("confirmModal").classList.contains("hidden")) closeDeleteModal();
      if (!$("resetPlanModal").classList.contains("hidden")) closeResetModal();
      if (!$("newPlanModal").classList.contains("hidden")) closeNewPlanPrompt();
    }
  });
  $("runModuleBtn").addEventListener("click", () => executeActiveModule(false));
  $("runAndSyncBtn").addEventListener("click", () => executeActiveModule(true));
  $("previewPdfBtn").addEventListener("click", () => fetchPdf(true));
  $("downloadPdfBtn").addEventListener("click", () => fetchPdf(false));
  $("copilotToggleBtn").addEventListener("click", toggleCopilotDrawer);
  $("copilotMinimizeBtn").addEventListener("click", toggleCopilotMinimize);
  $("copilotCloseBtn").addEventListener("click", () => {
    $("copilotDrawer").classList.add("hidden");
    $("copilotDrawer").classList.remove("minimized");
    $("copilotMinimizeBtn").textContent = "−";
  });
  document.querySelectorAll(".copilot-chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      const prompt = chip.getAttribute("data-prompt");
      if (prompt) sendCopilotMessage(prompt);
    });
  });
  $("copilotForm").addEventListener("submit", (e) => {
    e.preventDefault();
    const msg = $("copilotInput").value.trim();
    if (msg) {
      $("copilotInput").value = "";
      sendCopilotMessage(msg);
    }
  });

  if (state.token) {
    try {
      const res = await apiFetch("/auth/me");
      if (res.ok) {
        state.user = await res.json();
        showApp();
        await loadInitialAppData();
        return;
      }
    } catch (_e) {
      // Fall through to login view
    }
  }
  handleSignOut(false);
}

bootstrap();
