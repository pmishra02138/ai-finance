"""PDF pages 1-4: Cover, Score Dashboard, Cash Flow, and Debt Payoff."""


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


