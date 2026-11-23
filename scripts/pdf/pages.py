"""Page builders and document assembly for the 9-page Financial Plan PDF."""

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


def build_cover(story: List[Any], styles: Dict[str, ParagraphStyle], data: Dict[str, Any]) -> None:
    client = data.get("client_name") or "Personal Financial Plan"
    as_of = data.get("as_of") or datetime.now().strftime("%B %d, %Y")
    score = float(data.get("health_score", 0))
    grade = data.get("grade") or score_grade(score)
    signal = data.get("signal") or score_signal(score)

    story.append(Spacer(1, 0.4 * inch))
    story.append(Paragraph("FINANCIAL HEALTH REPORT", styles["kicker"]))
    story.append(Paragraph(esc(client), styles["title"]))
    story.append(Paragraph(f"Prepared {esc(as_of)}", styles["subtitle"]))

    story.append(Spacer(1, 0.15 * inch))
    story.append(gauge_drawing(score, width=4.6 * inch, height=2.4 * inch))
    story.append(Spacer(1, 0.05 * inch))

    grade_box = Table(
        [
            [
                Paragraph(f"<font size=22 color='#0c1220'><b>{esc(grade)}</b></font>", styles["body"]),
                Paragraph("<font size=11 color='#6b7280'>OVERALL GRADE</font>", styles["body"]),
            ],
            [
                Paragraph(f"<font size=13 color='{hexstr(score_color(score))}'><b>{esc(signal)}</b></font>", styles["body"]),
                Paragraph("<font size=11 color='#6b7280'>SIGNAL</font>", styles["body"]),
            ],
        ],
        colWidths=[2.6 * inch, 2.6 * inch],
        rowHeights=[0.45 * inch, 0.45 * inch],
    )
    grade_box.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.6, RULE),
        ("LINEBELOW", (0, 0), (-1, 0), 0.4, RULE),
        ("LINEAFTER", (0, 0), (0, -1), 0.4, RULE),
        ("BACKGROUND", (0, 0), (-1, -1), SOFT),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(grade_box)

    story.append(Spacer(1, 0.35 * inch))
    summary = data.get("executive_summary") or (
        "This report summarizes your overall financial health across five dimensions: "
        "cash flow, debt, investments, retirement readiness, and protection. "
        "Each section includes a score, key findings, and prioritized actions."
    )
    story.append(Paragraph("Executive Summary", styles["h2"]))
    story.append(Paragraph(esc(summary), styles["body_just"]))

    story.append(PageBreak())


def build_score_dashboard(story: List[Any], styles: Dict[str, ParagraphStyle], data: Dict[str, Any]) -> None:
    story.append(Paragraph("Score Dashboard", styles["h1"]))
    story.append(Paragraph(
        "Your Financial Health Score is a weighted composite of five categories. "
        "Each is scored 0–100. Green = strong, amber = needs attention, red = critical.",
        styles["body"],
    ))
    story.append(Spacer(1, 0.15 * inch))

    cats = data.get("categories", {})
    rows = [
        ("Cash Flow", float(cats.get("cash_flow", 0))),
        ("Debt", float(cats.get("debt", 0))),
        ("Investments", float(cats.get("investments", 0))),
        ("Retirement", float(cats.get("retirement", 0))),
        ("Protection", float(cats.get("protection", 0))),
    ]
    for label, sc in rows:
        story.append(category_bar(label, sc))
        story.append(Spacer(1, 0.04 * inch))

    story.append(Spacer(1, 0.25 * inch))
    story.append(Paragraph("Category Notes", styles["h2"]))
    notes = data.get("category_notes", {})
    note_rows = [
        ("Cash Flow", notes.get("cash_flow", "—")),
        ("Debt", notes.get("debt", "—")),
        ("Investments", notes.get("investments", "—")),
        ("Retirement", notes.get("retirement", "—")),
        ("Protection", notes.get("protection", "—")),
    ]
    for label, note in note_rows:
        story.append(Paragraph(f"<b>{esc(label)}.</b> {esc(note)}", styles["body"]))

    story.append(PageBreak())


def build_cash_flow(story: List[Any], styles: Dict[str, ParagraphStyle], data: Dict[str, Any]) -> None:
    cf = data.get("cash_flow", {})
    income = float(cf.get("monthly_income", 0))
    expenses_list: List[Tuple[str, float]] = [(str(n), float(v)) for n, v in (cf.get("expenses", []) or [])]
    total_exp = sum(v for _, v in expenses_list)
    surplus = income - total_exp
    savings_rate = (surplus / income * 100.0) if income else 0.0

    story.append(Paragraph("Cash Flow Analysis", styles["h1"]))
    story.append(Paragraph(
        "Monthly inflows and outflows. A healthy savings rate is typically 15–25% of "
        "gross income; aggressive savers target 30%+.",
        styles["body"],
    ))

    # Summary cards
    cards = Table(
        [[
            Paragraph(f"<font color='#6b7280' size=9>MONTHLY INCOME</font><br/><font color='#0c1220' size=18><b>{money(income)}</b></font>", styles["body"]),
            Paragraph(f"<font color='#6b7280' size=9>MONTHLY EXPENSES</font><br/><font color='#0c1220' size=18><b>{money(total_exp)}</b></font>", styles["body"]),
            Paragraph(f"<font color='#6b7280' size=9>NET SURPLUS</font><br/><font color='{hexstr(GREEN if surplus >= 0 else RED)}' size=18><b>{money(surplus)}</b></font>", styles["body"]),
            Paragraph(f"<font color='#6b7280' size=9>SAVINGS RATE</font><br/><font color='#0c1220' size=18><b>{pct(savings_rate)}</b></font>", styles["body"]),
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
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(Spacer(1, 0.15 * inch))
    story.append(cards)
    story.append(Spacer(1, 0.25 * inch))

    # Expense breakdown table
    story.append(Paragraph("Expense Breakdown", styles["h2"]))
    rows: List[List[Any]] = [["Category", "Monthly Amount", "% of Income"]]
    for name, amount in expenses_list:
        share = (amount / income * 100.0) if income else 0.0
        rows.append([name, money(amount), pct(share)])
    rows.append(["TOTAL", money(total_exp), pct((total_exp / income * 100.0) if income else 0.0)])
    tbl = Table(rows, colWidths=[3.0 * inch, 1.8 * inch, 1.8 * inch])
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("ROWBACKGROUNDS", (0, 1), (-1, -2), [PAGE_BG, SOFT]),
        ("BACKGROUND", (0, -1), (-1, -1), GREEN_LIGHT),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("LINEBELOW", (0, 0), (-1, -1), 0.3, RULE),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(tbl)

    story.append(Spacer(1, 0.2 * inch))
    commentary = cf.get("commentary") or (
        "Your largest expense categories drive the most leverage. "
        "A 5% reduction in housing and food typically yields the highest savings rate gains."
    )
    story.append(Paragraph(f"<b>Insight.</b> {esc(commentary)}", styles["body_just"]))

    story.append(PageBreak())


def build_debt_summary(story: List[Any], styles: Dict[str, ParagraphStyle], data: Dict[str, Any]) -> None:
    debt = data.get("debt", {})
    debts: List[Dict[str, Any]] = debt.get("accounts", []) or []
    total_balance = sum(float(d.get("balance", 0)) for d in debts)
    total_min = sum(float(d.get("min_payment", 0)) for d in debts)
    method = debt.get("strategy", "Avalanche (highest APR first)")
    payoff_months = int(debt.get("payoff_months", 0))
    total_interest = float(debt.get("total_interest", 0))

    story.append(Paragraph("Debt Summary & Payoff Plan", styles["h1"]))
    story.append(Paragraph(
        f"Strategy: <b>{esc(method)}</b>. The avalanche method minimizes total interest by attacking the highest-APR balance first. "
        "The snowball method builds momentum by attacking the smallest balance first.",
        styles["body_just"],
    ))
    story.append(Spacer(1, 0.1 * inch))

    cards = Table(
        [[
            Paragraph(f"<font color='#6b7280' size=9>TOTAL DEBT</font><br/><font color='#0c1220' size=16><b>{money(total_balance)}</b></font>", styles["body"]),
            Paragraph(f"<font color='#6b7280' size=9>MIN. PAYMENTS</font><br/><font color='#0c1220' size=16><b>{money(total_min)}/mo</b></font>", styles["body"]),
            Paragraph(f"<font color='#6b7280' size=9>PAYOFF TIMELINE</font><br/><font color='#0c1220' size=16><b>{payoff_months} months</b></font>", styles["body"]),
            Paragraph(f"<font color='#6b7280' size=9>TOTAL INTEREST</font><br/><font color='#e74c3c' size=16><b>{money(total_interest)}</b></font>", styles["body"]),
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
    story.append(Spacer(1, 0.2 * inch))

    story.append(Paragraph("Account Detail", styles["h2"]))
    rows: List[List[Any]] = [["Account", "Balance", "APR", "Min Pmt", "Payoff Order"]]
    for i, d in enumerate(debts, start=1):
        rows.append([
            d.get("name", "—"),
            money(float(d.get("balance", 0))),
            pct(float(d.get("apr", 0))),
            money(float(d.get("min_payment", 0))),
            f"#{d.get('order', i)}",
        ])
    tbl = Table(rows, colWidths=[2.2 * inch, 1.2 * inch, 0.9 * inch, 1.1 * inch, 1.2 * inch])
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [PAGE_BG, SOFT]),
        ("LINEBELOW", (0, 0), (-1, -1), 0.3, RULE),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(tbl)

    # Payoff timeline visual (simple bar)
    story.append(Spacer(1, 0.25 * inch))
    story.append(Paragraph("Payoff Timeline", styles["h2"]))
    months = max(payoff_months, 1)
    timeline_w = 6.5 * inch
    d = Drawing(timeline_w, 0.4 * inch)
    d.add(Rect(0, 0.18 * inch, timeline_w, 0.16 * inch, fillColor=HexColor("#eef1f6"), strokeColor=None))
    d.add(Rect(0, 0.18 * inch, timeline_w, 0.16 * inch, fillColor=GREEN, strokeColor=None))
    years = max(1, math.ceil(months / 12))
    for y in range(years + 1):
        x = min((y * 12 / months) * timeline_w, timeline_w)
        d.add(Line(x, 0.12 * inch, x, 0.38 * inch, strokeColor=MUTED, strokeWidth=0.4))
        d.add(String(x, 0.02 * inch, f"Yr {y}", fontName="Helvetica", fontSize=7.5, fillColor=MUTED, textAnchor="middle"))
    story.append(d)
    story.append(Paragraph(
        f"<font color='#6b7280' size=9>At your current strategy you become debt-free in approximately <b>{payoff_months} months</b> "
        f"({months / 12:.1f} years), paying <b>{money(total_interest)}</b> in interest.</font>",
        styles["body"],
    ))

    story.append(PageBreak())


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


def build_pdf(data: Dict[str, Any], output_path: str) -> None:
    """Assemble and render the complete 9-page Financial Plan PDF."""
    styles = build_styles()

    doc = BaseDocTemplate(
        output_path,
        pagesize=LETTER,
        leftMargin=MARGIN_L,
        rightMargin=MARGIN_R,
        topMargin=MARGIN_T,
        bottomMargin=MARGIN_B,
        title=f"Financial Plan — {data.get('client_name', 'Personal')}",
        author="AI Personal Finance Advisor",
        subject="Personal Financial Plan",
        creator="ai-finance",
    )
    frame = Frame(
        MARGIN_L, MARGIN_B,
        PAGE_W - MARGIN_L - MARGIN_R,
        PAGE_H - MARGIN_T - MARGIN_B,
        id="content", showBoundary=0,
    )
    doc.addPageTemplates([PageTemplate(id="main", frames=[frame], onPage=_draw_footer)])

    story: List[Any] = []
    build_cover(story, styles, data)
    build_score_dashboard(story, styles, data)
    build_cash_flow(story, styles, data)
    build_debt_summary(story, styles, data)
    build_investments(story, styles, data)
    build_retirement(story, styles, data)
    build_protection(story, styles, data)
    build_action_items(story, styles, data)
    build_90_day_plan(story, styles, data)

    doc.build(story)
