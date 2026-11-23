"""PDF pages 5-9: Investments, Retirement & MC, Protection, Action Items, and 90-Day Plan."""


from __future__ import annotations

import math
from datetime import datetime
from typing import Any, Dict, List, Tuple

from reportlab.graphics.shapes import Drawing, Line, Rect, String
from reportlab.lib import colors
from reportlab.lib.colors import Color, HexColor
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

try:
    from scoring import score_grade, score_signal
except ImportError:  # pragma: no cover - when imported as scripts.pdf.*
    from ..scoring import score_grade, score_signal

from .components import category_bar, esc, gauge_drawing, money, pct, pie_drawing
from .theme import (
    BLUE,
    GOLD,
    GOLD_LIGHT,
    GREEN,
    GREEN_LIGHT,
    INK,
    MARGIN_B,
    MARGIN_L,
    MARGIN_R,
    MARGIN_T,
    MUTED,
    NAVY,
    PAGE_BG,
    PAGE_H,
    PAGE_W,
    RED,
    RED_LIGHT,
    RULE,
    SOFT,
    _draw_footer,
    build_styles,
    hexstr,
    score_color,
)


def build_investments(story: List[Any], styles: Dict[str, ParagraphStyle], data: Dict[str, Any]) -> None:
    inv = data.get("investments", {})
    total = float(inv.get("total_value", 0))
    raw_alloc = inv.get("allocation", []) or []
    allocation: List[Tuple[str, float]] = [(a.get("name", "—"), float(a.get("pct", 0))) for a in raw_alloc]

    story.append(Paragraph("Investment Allocation", styles["h1"]))
    story.append(Paragraph(
        f"Total invested assets: <b>{money(total)}</b>. The pie below shows your current allocation. "
        "A well-diversified portfolio typically holds a mix appropriate for your age and risk tolerance.",
        styles["body_just"],
    ))
    story.append(Spacer(1, 0.1 * inch))

    pie = pie_drawing(allocation, width=3.4 * inch, height=2.8 * inch)
    commentary = inv.get("commentary") or (
        "Your equity exposure looks appropriate for your age band. "
        "Consider rebalancing if any asset class has drifted more than 5 percentage points from target."
    )
    target_rows = [["Asset Class", "Current", "Target", "Variance"]]
    for a in raw_alloc:
        cur = float(a.get("pct", 0))
        tgt = float(a.get("target_pct", cur))
        var = cur - tgt
        target_rows.append([a.get("name", "—"), pct(cur), pct(tgt), f"{'+' if var >= 0 else ''}{var:.1f}%"])
    tbl = Table(target_rows, colWidths=[1.5 * inch, 0.7 * inch, 0.7 * inch, 0.7 * inch])
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [PAGE_BG, SOFT]),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))

    layout = Table([[pie, tbl]], colWidths=[3.45 * inch, 3.65 * inch])
    layout.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story.append(layout)

    story.append(Spacer(1, 0.2 * inch))
    story.append(Paragraph(f"<b>Allocation insight.</b> {esc(commentary)}", styles["body_just"]))

    story.append(PageBreak())


def build_retirement(story: List[Any], styles: Dict[str, ParagraphStyle], data: Dict[str, Any]) -> None:
    r = data.get("retirement", {})
    current = float(r.get("current_balance", 0))
    needed = float(r.get("target_balance", 0))
    gap = needed - current
    age = int(r.get("current_age", 0))
    retire_age = int(r.get("retirement_age", 65))
    years_left = max(0, retire_age - age)
    monthly_save = float(r.get("monthly_contribution", 0))

    story.append(Paragraph("Retirement Projection", styles["h1"]))
    story.append(Paragraph(
        f"At age <b>{age}</b>, targeting retirement at age <b>{retire_age}</b> "
        f"({years_left} years away). Projections assume a 6–7% real return.",
        styles["body_just"],
    ))
    story.append(Spacer(1, 0.1 * inch))

    cards = Table(
        [[
            Paragraph(f"<font color='#6b7280' size=9>CURRENT BALANCE</font><br/><font color='#0c1220' size=16><b>{money(current)}</b></font>", styles["body"]),
            Paragraph(f"<font color='#6b7280' size=9>TARGET AT RETIREMENT</font><br/><font color='#0c1220' size=16><b>{money(needed)}</b></font>", styles["body"]),
            Paragraph(f"<font color='#6b7280' size=9>GAP</font><br/><font color='{hexstr(GREEN if gap <= 0 else RED)}' size=16><b>{money(gap)}</b></font>", styles["body"]),
            Paragraph(f"<font color='#6b7280' size=9>MONTHLY CONTRIBUTION</font><br/><font color='#0c1220' size=16><b>{money(monthly_save)}</b></font>", styles["body"]),
        ]],
        colWidths=[1.6 * inch] * 4,
        rowHeights=[0.7 * inch],
    )
    cards.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.4, RULE),
        ("INNERGRID", (0, 0), (-1, -1), 0.4, RULE),
        ("BACKGROUND", (0, 0), (-1, -1), SOFT),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
    ]))
    story.append(cards)

    # Progress bar to target
    story.append(Spacer(1, 0.25 * inch))
    story.append(Paragraph("Progress to Target", styles["h2"]))
    track_w = 6.5 * inch
    pctp = 0 if needed <= 0 else min(1.0, current / needed)
    d = Drawing(track_w, 0.45 * inch)
    d.add(Rect(0, 0.18 * inch, track_w, 0.18 * inch, fillColor=HexColor("#eef1f6"), strokeColor=None))
    d.add(Rect(0, 0.18 * inch, track_w * pctp, 0.18 * inch, fillColor=GREEN, strokeColor=None))
    d.add(String(track_w / 2, 0.22 * inch, f"{pctp * 100:.0f}% of target", fontName="Helvetica-Bold", fontSize=10, fillColor=NAVY, textAnchor="middle"))
    story.append(d)

    story.append(Spacer(1, 0.2 * inch))
    story.append(Paragraph("Scenario Comparison", styles["h2"]))
    scenarios = r.get("scenarios", []) or []
    if scenarios:
        rows = [["Scenario", "Monthly Save", "Projected Balance @ Retirement", "Result"]]
        for s in scenarios:
            rows.append([
                s.get("name", "—"),
                money(float(s.get("monthly", 0))),
                money(float(s.get("projected", 0))),
                s.get("verdict", "—"),
            ])
        tbl = Table(rows, colWidths=[1.6 * inch, 1.4 * inch, 2.3 * inch, 1.2 * inch])
        tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), NAVY),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [PAGE_BG, SOFT]),
            ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(tbl)

    mc = r.get("monte_carlo")
    if isinstance(mc, dict) and mc.get("trials"):
        story.append(Spacer(1, 0.16 * inch))
        story.append(Paragraph("Monte Carlo Stress Test", styles["h2"]))
        mc_rows = [
            ["Metric", "Value"],
            [f"{int(mc.get('drawdown_years', 30))}-Yr Retirement Survival ({int(mc.get('trials', 1000)):,} trials)", pct(float(mc.get("success_rate_pct", 0)))],
            ["10th Percentile @ Retirement (Downside)", money(float(mc.get("retire_p10", 0)))],
            ["50th Percentile @ Retirement (Median)", money(float(mc.get("retire_p50", 0)))],
            ["90th Percentile @ Retirement (Upside)", money(float(mc.get("retire_p90", 0)))],
        ]
        mc_tbl = Table(mc_rows, colWidths=[4.2 * inch, 2.3 * inch])
        mc_tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), NAVY),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9.5),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [PAGE_BG, SOFT]),
            ("ALIGN", (1, 0), (1, -1), "RIGHT"),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(mc_tbl)

    story.append(Spacer(1, 0.2 * inch))
    insight = r.get("commentary") or (
        f"To close the gap, increasing contributions by ~10–15% or adding $300–$500/mo can "
        f"materially shift your projected balance by {years_left} years from now."
    )
    story.append(Paragraph(f"<b>Retirement insight.</b> {esc(insight)}", styles["body_just"]))

    story.append(PageBreak())


def build_protection(story: List[Any], styles: Dict[str, ParagraphStyle], data: Dict[str, Any]) -> None:
    p = data.get("protection", {})
    items: List[Dict[str, Any]] = p.get("items", []) or []

    story.append(Paragraph("Protection Scorecard", styles["h1"]))
    story.append(Paragraph(
        "Protection covers insurance and estate planning — the foundation that prevents "
        "a single event from undoing years of saving and investing.",
        styles["body_just"],
    ))
    story.append(Spacer(1, 0.1 * inch))

    rows: List[List[Any]] = [["Coverage Area", "Status", "Recommendation"]]
    for it in items:
        status = it.get("status", "—")
        rows.append([it.get("name", "—"), status, it.get("recommendation", "—")])

    tbl = Table(rows, colWidths=[2.0 * inch, 1.4 * inch, 3.2 * inch])
    style_rows = [
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [PAGE_BG, SOFT]),
        ("ALIGN", (1, 1), (1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]
    for i, it in enumerate(items, start=1):
        st = (it.get("status") or "").lower()
        if "good" in st or "ok" in st or "yes" in st or "covered" in st:
            style_rows.append(("BACKGROUND", (1, i), (1, i), GREEN_LIGHT))
            style_rows.append(("TEXTCOLOR", (1, i), (1, i), GREEN))
        elif "partial" in st or "review" in st or "gap" in st:
            style_rows.append(("BACKGROUND", (1, i), (1, i), GOLD_LIGHT))
            style_rows.append(("TEXTCOLOR", (1, i), (1, i), GOLD))
        elif "miss" in st or "none" in st or "no" == st or "critical" in st:
            style_rows.append(("BACKGROUND", (1, i), (1, i), RED_LIGHT))
            style_rows.append(("TEXTCOLOR", (1, i), (1, i), RED))
    tbl.setStyle(TableStyle(style_rows))
    story.append(tbl)

    story.append(Spacer(1, 0.2 * inch))
    note = p.get("commentary") or (
        "Term life insurance is cheap when you're young and healthy — lock in coverage early. "
        "Disability insurance is often the most overlooked policy and protects your largest asset: your future income."
    )
    story.append(Paragraph(f"<b>Protection insight.</b> {esc(note)}", styles["body_just"]))

    story.append(PageBreak())


def build_action_items(story: List[Any], styles: Dict[str, ParagraphStyle], data: Dict[str, Any]) -> None:
    actions: List[Dict[str, Any]] = (data.get("action_items", []) or [])[:10]

    story.append(Paragraph("Top 10 Action Items", styles["h1"]))
    story.append(Paragraph(
        "Prioritized by impact and ease of execution. Work through these in order for the "
        "fastest improvement to your Financial Health Score.",
        styles["body_just"],
    ))
    story.append(Spacer(1, 0.1 * inch))

    rows: List[List[Any]] = [["#", "Action", "Category", "Priority", "Impact"]]
    for i, a in enumerate(actions, start=1):
        rows.append([
            str(i),
            Paragraph(esc(a.get("action", "—")), ParagraphStyle("ai", fontName="Helvetica", fontSize=9.5, leading=12)),
            a.get("category", "—"),
            a.get("priority", "—"),
            a.get("impact", "—"),
        ])
    tbl = Table(rows, colWidths=[0.35 * inch, 3.4 * inch, 1.1 * inch, 0.9 * inch, 0.85 * inch])
    style_rows = [
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9.5),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [PAGE_BG, SOFT]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (0, -1), "CENTER"),
        ("ALIGN", (2, 1), (-1, -1), "CENTER"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]
    for i, a in enumerate(actions, start=1):
        prio = (a.get("priority") or "").lower()
        if "high" in prio or "critical" in prio:
            style_rows.append(("TEXTCOLOR", (3, i), (3, i), RED))
            style_rows.append(("FONTNAME", (3, i), (3, i), "Helvetica-Bold"))
        elif "med" in prio:
            style_rows.append(("TEXTCOLOR", (3, i), (3, i), GOLD))
        elif "low" in prio:
            style_rows.append(("TEXTCOLOR", (3, i), (3, i), GREEN))
    tbl.setStyle(TableStyle(style_rows))
    story.append(tbl)

    story.append(PageBreak())


def build_90_day_plan(story: List[Any], styles: Dict[str, ParagraphStyle], data: Dict[str, Any]) -> None:
    plan = data.get("ninety_day_plan", {}) or {}
    m1 = plan.get("month_1", []) or []
    m2 = plan.get("month_2", []) or []
    m3 = plan.get("month_3", []) or []

    story.append(Paragraph("Your 90-Day Plan", styles["h1"]))
    story.append(Paragraph(
        "Three focused months. Each month has 3–5 concrete tasks. Completing all three "
        "months typically moves your Financial Health Score by 10–20 points.",
        styles["body_just"],
    ))
    story.append(Spacer(1, 0.15 * inch))

    def month_block(title: str, color: Color, items: List[str]) -> Table:
        header = Paragraph(
            f"<font color='#ffffff'><b>{esc(title)}</b></font>",
            ParagraphStyle("mh", fontName="Helvetica-Bold", fontSize=12, alignment=TA_CENTER, leading=14),
        )
        body_lines = [f"• {esc(it)}" for it in (items or ["—"])]
        body_para = Paragraph(
            "<br/>".join(body_lines),
            ParagraphStyle("mb", fontName="Helvetica", fontSize=9.5, leading=13, textColor=INK),
        )
        t = Table([[header], [body_para]], colWidths=[2.15 * inch], rowHeights=[0.38 * inch, None])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), color),
            ("BACKGROUND", (0, 1), (-1, 1), SOFT),
            ("BOX", (0, 0), (-1, -1), 0.5, color),
            ("VALIGN", (0, 0), (-1, 0), "MIDDLE"),
            ("VALIGN", (0, 1), (-1, 1), "TOP"),
            ("LEFTPADDING", (0, 1), (-1, 1), 10),
            ("RIGHTPADDING", (0, 1), (-1, 1), 10),
            ("TOPPADDING", (0, 1), (-1, 1), 10),
            ("BOTTOMPADDING", (0, 1), (-1, 1), 10),
        ]))
        return t

    cols = Table(
        [[
            month_block("MONTH 1 — Foundation", GREEN, m1),
            month_block("MONTH 2 — Acceleration", BLUE, m2),
            month_block("MONTH 3 — Optimization", GOLD, m3),
        ]],
        colWidths=[2.25 * inch, 2.25 * inch, 2.25 * inch],
    )
    cols.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story.append(cols)

    story.append(Spacer(1, 0.3 * inch))
    story.append(Paragraph("After 90 Days", styles["h2"]))
    after = plan.get("after_90_days") or (
        "Re-run your Full Health Analysis in the web app to recalculate your Financial Health Score. Most users see "
        "10–20 point gains in the first 90 days of focused execution."
    )
    story.append(Paragraph(esc(after), styles["body_just"]))

    story.append(Spacer(1, 0.3 * inch))
    final = Paragraph(
        "<b>Important disclaimer.</b> This Financial Plan is generated by an AI tool using the inputs you provided. "
        "It is for educational and informational purposes only and does not constitute financial, investment, tax, or "
        "legal advice. Consult a licensed financial advisor, CPA, or attorney before making any financial decisions. "
        "All projections are estimates based on assumptions that may not match real-world outcomes.",
        ParagraphStyle("final", fontName="Helvetica-Oblique", fontSize=9, leading=12, textColor=MUTED, alignment=TA_JUSTIFY),
    )
    fbox = Table([[final]], colWidths=[7.1 * inch])
    fbox.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), GOLD_LIGHT),
        ("BOX", (0, 0), (-1, -1), 0.6, GOLD),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
    ]))
    story.append(fbox)


