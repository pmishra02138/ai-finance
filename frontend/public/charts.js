/* Lightweight inline SVG charts (zero external dependencies) */

window.FinanceCharts = (function () {
  const PALETTE = ["#2d8a4e", "#2563eb", "#e8a838", "#dc2626", "#7c3aed", "#0891b2", "#6b7280"];

  function scoreColor(score) {
    if (score >= 70) return "#2d8a4e";
    if (score >= 40) return "#e8a838";
    return "#dc2626";
  }

  function escapeHtml(str) {
    return String(str ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function renderGaugeSVG(score) {
    const s = Math.max(0, Math.min(100, Number(score || 0)));
    const r = 56;
    const circ = Math.PI * r;
    const dash = (s / 100) * circ;
    const color = scoreColor(s);
    return `
      <svg viewBox="0 0 150 92" width="150" height="92" aria-label="Score Gauge">
        <path d="M 19 76 A 56 56 0 0 1 131 76" fill="none" stroke="#e5e7eb" stroke-width="12" stroke-linecap="round"/>
        <path d="M 19 76 A 56 56 0 0 1 131 76" fill="none" stroke="${color}" stroke-width="12" stroke-linecap="round"
              stroke-dasharray="${dash.toFixed(1)} ${circ.toFixed(1)}"/>
        <text x="75" y="64" text-anchor="middle" font-size="24" font-weight="700" fill="#0c1220">${Math.round(s)}</text>
        <text x="75" y="80" text-anchor="middle" font-size="10" fill="#6b7280">out of 100</text>
      </svg>
    `;
  }

  function renderBarsSVG(chart) {
    const items = (chart && chart.items) || [];
    if (!items.length) return "";
    const maxVal = Math.max(...items.map((i) => Math.abs(Number(i.value || 0))), 1);
    const rowH = 30;
    const h = items.length * rowH + 12;
    const bars = items
      .map((item, idx) => {
        const val = Math.max(0, Number(item.value || 0));
        const pct = Math.min(100, (val / maxVal) * 100);
        const y = idx * rowH + 8;
        const fill = item.color || PALETTE[idx % PALETTE.length];
        const formatted = val >= 1000 ? `$${Math.round(val).toLocaleString()}` : `${Math.round(val * 10) / 10}`;
        return `
          <text x="0" y="${y + 14}" font-size="11.5" fill="#1f2937" font-weight="600">${escapeHtml(item.label)}</text>
          <rect x="112" y="${y + 3}" width="260" height="14" rx="7" fill="#eef1f6"/>
          <rect x="112" y="${y + 3}" width="${Math.max(4, (260 * pct) / 100).toFixed(1)}" height="14" rx="7" fill="${fill}"/>
          <text x="382" y="${y + 14}" font-size="11.5" fill="#1f2937" font-weight="600">${escapeHtml(formatted)}</text>
        `;
      })
      .join("");
    return `<svg viewBox="0 0 460 ${h}" class="svg-chart" role="img" aria-label="${escapeHtml(chart.title || "Bar chart")}">${bars}</svg>`;
  }

  function renderDonutSVG(chart) {
    const items = ((chart && chart.items) || []).filter((i) => Number(i.value || 0) > 0);
    if (!items.length) return "";
    const total = items.reduce((acc, i) => acc + Number(i.value || 0), 0);
    if (total <= 0) return "";
    const r = 46;
    const circ = 2 * Math.PI * r;
    let offset = 0;

    const slices = items
      .map((item, idx) => {
        const frac = Number(item.value) / total;
        const len = frac * circ;
        const color = item.color || PALETTE[idx % PALETTE.length];
        const seg = `<circle cx="64" cy="64" r="${r}" fill="none" stroke="${color}" stroke-width="20"
          stroke-dasharray="${len.toFixed(2)} ${(circ - len).toFixed(2)}"
          stroke-dashoffset="${(-offset).toFixed(2)}" transform="rotate(-90 64 64)"/>`;
        offset += len;
        return seg;
      })
      .join("");

    const legend = items
      .map((item, idx) => {
        const pct = ((Number(item.value) / total) * 100).toFixed(1);
        const color = item.color || PALETTE[idx % PALETTE.length];
        return `<div class="legend-item"><span class="legend-swatch" style="background:${color}"></span><span>${escapeHtml(item.label)} (${pct}%)</span></div>`;
      })
      .join("");

    return `
      <div class="donut-wrap">
        <svg viewBox="0 0 128 128" width="140" height="140" role="img" aria-label="${escapeHtml(chart.title || "Donut chart")}">
          ${slices}
        </svg>
        <div class="donut-legend">${legend}</div>
      </div>
    `;
  }

  function renderChart(chart) {
    if (!chart || !chart.items || !chart.items.length) return "";
    const body = chart.type === "donut" ? renderDonutSVG(chart) : renderBarsSVG(chart);
    if (!body) return "";
    return `
      <div class="chart-card">
        <h4>${escapeHtml(chart.title || "Visualization")}</h4>
        ${body}
      </div>
    `;
  }

  return { renderGaugeSVG, renderChart, scoreColor, escapeHtml };
})();
