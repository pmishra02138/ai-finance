const state = {
  token: localStorage.getItem("ai_finance_token") || "",
  user: null,
  plans: [],
  activePlanId: null,
  activePayload: null,
  catalog: { stages: [], skills: [] },
  skillRuns: {},
  activeSkillName: null, // null = Overview/JSON view
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
  $("overviewSummary").textContent = p.executive_summary || "Select any skill in the 5-stage sidebar to run an interactive analysis.";
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
  const actions = (p.action_items || []).slice(0, 5);
  $("overviewActions").innerHTML = actions.length
    ? `<div class="recs-block"><h4>Top Action Items</h4><ul>${actions.map((a) => `<li><strong>[${esc(a.priority || "Med")}]</strong> ${esc(a.action || "")}</li>`).join("")}</ul></div>`
    : "";
}

function renderStageNav() {
  const nav = $("stageNav");
  nav.innerHTML = "";
  const completedCount = Object.keys(state.skillRuns).length;
  $("completionPill").textContent = `${completedCount}/${state.catalog.skills.length || 14}`;

  for (const stage of state.catalog.stages || []) {
    const group = document.createElement("div");
    group.className = "stage-group";
    group.dataset.stage = stage.id;
    const title = document.createElement("div");
    title.className = "stage-group-title";
    title.textContent = stage.title;
    group.appendChild(title);

    for (const sk of stage.skills) {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "skill-btn" + (state.activeSkillName === sk.name ? " active" : "");
      const done = Boolean(state.skillRuns[sk.name]);
      btn.innerHTML = `<span>${window.FinanceCharts.escapeHtml(sk.label)}</span>${
        done ? '<span class="check-dot" title="Completed">✓</span>' : '<span class="pending-dot">○</span>'
      }`;
      btn.addEventListener("click", () => openSkill(sk.name));
      group.appendChild(btn);
    }
    nav.appendChild(group);
  }
}

function openOverview() {
  state.activeSkillName = null;
  $("overviewPanel").classList.remove("hidden");
  $("skillPanel").classList.add("hidden");
  renderPlanHeader();
  renderStageNav();
}

function setSkillStatusBadge(label) {
  const badge = $("skillStatusBadge");
  if (!label) {
    badge.innerHTML = "";
    badge.classList.add("hidden");
    return;
  }
  const esc = window.FinanceCharts.escapeHtml;
  badge.innerHTML = `<span class="pill-check" aria-hidden="true">✓</span><span>${esc(label)}</span>`;
  badge.classList.remove("hidden");
}

function openSkill(skillName) {
  const meta = (state.catalog.skills || []).find((s) => s.name === skillName);
  if (!meta) return;
  state.activeSkillName = skillName;
  $("overviewPanel").classList.add("hidden");
  $("skillPanel").classList.remove("hidden");
  $("skillHeaderCard").dataset.stage = meta.stage_id;

  $("skillStageKicker").textContent = meta.stage_title;
  $("skillHeading").textContent = meta.label;
  $("skillDesc").textContent = meta.description;

  const saved = state.skillRuns[skillName];
  setSkillStatusBadge(saved ? "Saved" : "");

  const fields = window.FinanceSkills.getFields(skillName, state.activePayload, saved && saved.inputs);
  window.FinanceSkills.renderForm($("skillFormContainer"), fields);
  window.FinanceSkills.renderResult($("skillResultContainer"), saved && saved.outputs);
  renderStageNav();
}

async function executeActiveSkill(syncToPlan) {
  if (!state.activePlanId || !state.activeSkillName) return;
  try {
    const inputs = window.FinanceSkills.readForm($("skillFormContainer"));
    const res = await apiFetch(`/plans/${state.activePlanId}/skills/${state.activeSkillName}/run`, {
      method: "POST",
      body: JSON.stringify({ inputs, sync_to_plan: syncToPlan }),
    });
    if (!res.ok) {
      const err = await res.text();
      showStatus(`Unable to run calculation: ${err}`, true);
      return;
    }
    const data = await res.json();
    state.skillRuns[state.activeSkillName] = data.run;
    if (data.updated_plan) {
      state.activePayload = data.updated_plan.payload;
      await refreshPlanListOnly();
      renderPlanHeader();
    }
    setSkillStatusBadge(syncToPlan ? "Analysis complete & plan updated" : "Analysis saved");
    window.FinanceSkills.renderResult($("skillResultContainer"), data.result);
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
    apiFetch(`/plans/${planId}/skills`),
  ]);
  if (!planRes.ok) {
    showStatus("Failed to load plan", true);
    return;
  }
  const plan = await planRes.json();
  state.activePlanId = plan.id;
  state.activePayload = plan.payload;
  state.skillRuns = {};
  if (runsRes.ok) {
    const runsData = await runsRes.json();
    for (const r of runsData.runs || []) {
      state.skillRuns[r.skill_name] = r;
    }
  }
  renderPlanSelect();
  renderPlanHeader();
  if (state.activeSkillName) {
    openSkill(state.activeSkillName);
  } else {
    renderStageNav();
  }
}

async function loadInitialAppData() {
  const [skillsRes, plansRes] = await Promise.all([apiFetch("/skills"), apiFetch("/plans")]);
  if (skillsRes.ok) {
    state.catalog = await skillsRes.json();
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
  $("newPlanRow").classList.remove("hidden");
  $("newPlanNameInput").focus();
}

function closeNewPlanPrompt() {
  $("newPlanRow").classList.add("hidden");
}

async function createNewPlan() {
  const customName = $("newPlanNameInput").value.trim();
  const demoRes = await apiFetch("/demo-data");
  const demo = await demoRes.json();
  demo.client_name = customName || `Financial Plan (${new Date().toLocaleDateString()})`;
  const res = await apiFetch("/plans", {
    method: "POST",
    body: JSON.stringify({ title: demo.client_name, payload: demo }),
  });
  if (!res.ok) {
    showStatus("Failed to create plan", true);
    return;
  }
  const created = await res.json();
  closeNewPlanPrompt();
  await refreshPlanListOnly();
  await selectPlan(created.id);
  showStatus(`Created "${demo.client_name}".`);
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
  state.skillRuns = {};
  localStorage.removeItem("ai_finance_token");
  $("loginView").classList.remove("hidden");
  $("appView").classList.add("hidden");
  $("userControls").classList.add("hidden");
}

function showApp() {
  $("loginView").classList.add("hidden");
  $("appView").classList.remove("hidden");
  $("userControls").classList.remove("hidden");
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
  $("deletePlanBtn").addEventListener("click", requestDeletePlanConfirmation);
  $("confirmCancelBtn").addEventListener("click", closeDeleteModal);
  $("confirmDeleteBtn").addEventListener("click", confirmDeleteActivePlan);
  $("confirmModal").addEventListener("click", (e) => {
    if (e.target === $("confirmModal")) closeDeleteModal();
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !$("confirmModal").classList.contains("hidden")) {
      closeDeleteModal();
    }
  });
  $("runSkillBtn").addEventListener("click", () => executeActiveSkill(false));
  $("runAndSyncBtn").addEventListener("click", () => executeActiveSkill(true));
  $("previewPdfBtn").addEventListener("click", () => fetchPdf(true));
  $("downloadPdfBtn").addEventListener("click", () => fetchPdf(false));

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
