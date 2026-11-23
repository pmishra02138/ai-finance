"""Reusable ReportLab drawings, tables, and safe text/number formatting helpers."""

from __future__ import annotations

import math
from typing import Any, List, Optional, Tuple
from xml.sax.saxutils import escape as xml_escape

from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics.shapes import Drawing, Rect, String, Wedge
from reportlab.lib import colors
from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, Table, TableStyle

from .theme import BLUE, GOLD, GREEN, INK, MUTED, NAVY, PAGE_BG, RED, RULE, SOFT, score_color


def esc(value: Any) -> str:
    """Escape dynamic text for safe interpolation into ReportLab Paragraph XML."""
    return xml_escape(str(value))


def money(n: float) -> str:
    sign = "-" if n < 0 else ""
    return f"{sign}${abs(n):,.0f}"


def pct(n: float, decimals: int = 1) -> str:
    return f"{n:.{decimals}f}%"


def gauge_drawing(score: float, width: float = 4.2 * inch, height: float = 2.3 * inch) -> Drawing:
    """Half-circle gauge for the Financial Health Score."""
    d = Drawing(width, height)
    cx = width / 2
    cy = 0.35 * inch
    radius = min(width / 2.4, height - 0.1 * inch)

    # Background arc (gray track)
    d.add(Wedge(cx, cy, radius, 180, 0, fillColor=HexColor("#eef1f6"), strokeColor=None))
    inner = radius * 0.62
    d.add(Wedge(cx, cy, inner, 180, 0, fillColor=PAGE_BG, strokeColor=None))

    # Colored arc proportional to score
    score = max(0.0, min(100.0, float(score)))
    end_angle = 180 - (score / 100.0) * 180  # sweep from 180 -> 0
    fill = score_color(score)
    if score > 0:
        d.add(Wedge(cx, cy, radius, 180, end_angle, fillColor=fill, strokeColor=None))
        d.add(Wedge(cx, cy, inner, 180, end_angle, fillColor=PAGE_BG, strokeColor=None))

    # Tick labels
    for i, label in enumerate(["0", "25", "50", "75", "100"]):
        ang_deg = 180 - i * 45
        ang = math.radians(ang_deg)
        tx = cx + (radius + 0.12 * inch) * math.cos(ang)
        ty = cy + (radius + 0.12 * inch) * math.sin(ang)
        s = String(tx, ty, label, fontName="Helvetica", fontSize=7, fillColor=MUTED, textAnchor="middle")
        d.add(s)

    # Score number
    num = String(cx, cy + 0.18 * inch, f"{int(round(score))}", fontName="Helvetica-Bold", fontSize=36, fillColor=NAVY, textAnchor="middle")
    d.add(num)
    sub = String(cx, cy - 0.02 * inch, "out of 100", fontName="Helvetica", fontSize=8.5, fillColor=MUTED, textAnchor="middle")
    d.add(sub)
    return d


def category_bar(label: str, score: float, width: float = 6.5 * inch) -> Table:
    """A single horizontal bar row used on the score dashboard."""
    score = max(0.0, min(100.0, float(score)))
    fill = score_color(score)
    track_w = width - 2.3 * inch
    bar_w = max(0.05 * inch, track_w * (score / 100.0))

    d = Drawing(track_w, 0.28 * inch)
    d.add(Rect(0, 0.06 * inch, track_w, 0.16 * inch, fillColor=HexColor("#eef1f6"), strokeColor=None))
    d.add(Rect(0, 0.06 * inch, bar_w, 0.16 * inch, fillColor=fill, strokeColor=None))

    label_para = Paragraph(f"<b>{esc(label)}</b>", ParagraphStyle("lbl", fontName="Helvetica-Bold", fontSize=10, textColor=INK, leading=12))
    score_para = Paragraph(
        f"<font color='#1f2937'><b>{int(round(score))}</b></font> "
        f"<font color='#6b7280' size=8>/ 100</font>",
        ParagraphStyle("sc", fontName="Helvetica", fontSize=10, alignment=TA_RIGHT, leading=12),
    )

    tbl = Table(
        [[label_para, d, score_para]],
        colWidths=[1.6 * inch, track_w, 0.7 * inch],
        rowHeights=[0.32 * inch],
    )
    tbl.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 2),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    return tbl


def pie_drawing(slices: List[Tuple[str, float]], width: float = 3.4 * inch, height: float = 3.0 * inch) -> Drawing:
    """Allocation pie chart."""
    d = Drawing(width, height)
    if not slices:
        d.add(String(width / 2, height / 2, "No allocation data", fontName="Helvetica", fontSize=10, fillColor=MUTED, textAnchor="middle"))
        return d
    p = Pie()
    p.x = 0.4 * inch
    p.y = 0.2 * inch
    p.width = 2.4 * inch
    p.height = 2.4 * inch
    p.data = [max(0.001, float(v)) for _, v in slices]
    p.labels = [f"{n} ({v:.0f}%)" for n, v in slices]
    p.simpleLabels = 1
    p.slices.strokeColor = colors.white
    p.slices.strokeWidth = 1.2
    palette = [GREEN, BLUE, GOLD, RED, HexColor("#7c5cff"), HexColor("#16b6c9"), MUTED]
    for i in range(len(slices)):
        p.slices[i].fillColor = palette[i % len(palette)]
    p.sideLabels = 1
    p.sideLabelsOffset = 0.06 * inch
    d.add(p)
    return d


def kv_table(
    rows: List[Tuple[str, str]],
    col_widths: Optional[List[float]] = None,
    header: Optional[Tuple[str, str]] = None,
) -> Table:
    """Simple two-column key/value table."""
    data: List[List[Any]] = []
    if header:
        data.append([header[0], header[1]])
    data.extend(rows)
    cw = col_widths or [2.6 * inch, 4.0 * inch]
    tbl = Table(data, colWidths=cw)
    style = [
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("TEXTCOLOR", (0, 0), (-1, -1), INK),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("ROWBACKGROUNDS", (0, 1 if header else 0), (-1, -1), [PAGE_BG, SOFT]),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, RULE),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica"),
    ]
    if header:
        style += [
            ("BACKGROUND", (0, 0), (-1, 0), NAVY),
            ("TEXTCOLOR", (0, 0), (-1, 0), HexColor("#ffffff")),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 10.5),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
            ("TOPPADDING", (0, 0), (-1, 0), 8),
        ]
    tbl.setStyle(TableStyle(style))
    return tbl
