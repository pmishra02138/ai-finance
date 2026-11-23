"""PDF theme: color palette, paragraph styles, page geometry, and page footer."""

from __future__ import annotations

from typing import Dict

from reportlab.lib.colors import Color, HexColor
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import BaseDocTemplate

# ---------------------------------------------------------------------------
# Color palette
# ---------------------------------------------------------------------------
GREEN = HexColor("#2d8a4e")
GREEN_LIGHT = HexColor("#e8f5ed")
BLUE = HexColor("#4a9eff")
BLUE_LIGHT = HexColor("#eaf3ff")
GOLD = HexColor("#e8a838")
GOLD_LIGHT = HexColor("#fcf2dc")
RED = HexColor("#e74c3c")
RED_LIGHT = HexColor("#fde8e6")
NAVY = HexColor("#0c1220")
SLATE = HexColor("#1a2840")
INK = HexColor("#1f2937")
MUTED = HexColor("#6b7280")
RULE = HexColor("#e5e7eb")
PAGE_BG = HexColor("#ffffff")
SOFT = HexColor("#f7f9fc")


def score_color(score: float) -> Color:
    """Green (>=70), amber (40-69), red (<40)."""
    if score >= 70:
        return GREEN
    if score >= 40:
        return GOLD
    return RED


def score_color_light(score: float) -> Color:
    if score >= 70:
        return GREEN_LIGHT
    if score >= 40:
        return GOLD_LIGHT
    return RED_LIGHT


def hexstr(c: Color) -> str:
    """Return a #RRGGBB string for a reportlab Color."""
    r = int(round(c.red * 255))
    g = int(round(c.green * 255))
    b = int(round(c.blue * 255))
    return f"#{r:02x}{g:02x}{b:02x}"


# ---------------------------------------------------------------------------
# Styles
# ---------------------------------------------------------------------------
def build_styles() -> Dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "title", parent=base["Title"],
            fontName="Helvetica-Bold", fontSize=30, leading=34,
            textColor=NAVY, alignment=TA_CENTER, spaceAfter=4,
        ),
        "subtitle": ParagraphStyle(
            "subtitle", parent=base["Normal"],
            fontName="Helvetica", fontSize=13, leading=16,
            textColor=MUTED, alignment=TA_CENTER, spaceAfter=18,
        ),
        "h1": ParagraphStyle(
            "h1", parent=base["Heading1"],
            fontName="Helvetica-Bold", fontSize=22, leading=26,
            textColor=NAVY, spaceBefore=6, spaceAfter=8,
        ),
        "h2": ParagraphStyle(
            "h2", parent=base["Heading2"],
            fontName="Helvetica-Bold", fontSize=15, leading=18,
            textColor=NAVY, spaceBefore=10, spaceAfter=6,
        ),
        "h3": ParagraphStyle(
            "h3", parent=base["Heading3"],
            fontName="Helvetica-Bold", fontSize=12, leading=15,
            textColor=GREEN, spaceBefore=6, spaceAfter=4,
        ),
        "body": ParagraphStyle(
            "body", parent=base["BodyText"],
            fontName="Helvetica", fontSize=10.5, leading=14.5,
            textColor=INK, alignment=TA_LEFT, spaceAfter=6,
        ),
        "body_just": ParagraphStyle(
            "body_just", parent=base["BodyText"],
            fontName="Helvetica", fontSize=10.5, leading=14.5,
            textColor=INK, alignment=TA_JUSTIFY, spaceAfter=6,
        ),
        "small": ParagraphStyle(
            "small", parent=base["Normal"],
            fontName="Helvetica", fontSize=8.5, leading=11,
            textColor=MUTED, alignment=TA_LEFT,
        ),
        "kicker": ParagraphStyle(
            "kicker", parent=base["Normal"],
            fontName="Helvetica-Bold", fontSize=9.5, leading=12,
            textColor=GOLD, alignment=TA_LEFT, spaceAfter=2,
        ),
        "callout": ParagraphStyle(
            "callout", parent=base["Normal"],
            fontName="Helvetica", fontSize=10, leading=14,
            textColor=INK, alignment=TA_LEFT,
        ),
        "footer": ParagraphStyle(
            "footer", parent=base["Normal"],
            fontName="Helvetica-Oblique", fontSize=7.5, leading=10,
            textColor=MUTED, alignment=TA_CENTER,
        ),
    }


# ---------------------------------------------------------------------------
# Page frame + footer
# ---------------------------------------------------------------------------
PAGE_W, PAGE_H = LETTER
MARGIN_L = MARGIN_R = 0.7 * inch
MARGIN_T = 0.7 * inch
MARGIN_B = 0.85 * inch
DISCLAIMER_TEXT = (
    "This report is for informational purposes only and is NOT financial, "
    "investment, tax, or legal advice. Consult a licensed financial advisor "
    "before making decisions. Projections are estimates and not guarantees."
)


def _draw_footer(canvas: Canvas, doc: BaseDocTemplate) -> None:
    canvas.saveState()
    # Footer bar
    canvas.setFillColor(SOFT)
    canvas.rect(0, 0, PAGE_W, 0.55 * inch, stroke=0, fill=1)
    canvas.setStrokeColor(RULE)
    canvas.setLineWidth(0.5)
    canvas.line(MARGIN_L, 0.55 * inch, PAGE_W - MARGIN_R, 0.55 * inch)

    # Disclaimer (left two-thirds)
    canvas.setFillColor(MUTED)
    canvas.setFont("Helvetica-Oblique", 7.5)
    canvas.drawString(MARGIN_L, 0.36 * inch, DISCLAIMER_TEXT[:115])
    canvas.drawString(MARGIN_L, 0.24 * inch, DISCLAIMER_TEXT[115:])

    # Page number (right)
    canvas.setFont("Helvetica-Bold", 8)
    canvas.setFillColor(NAVY)
    canvas.drawRightString(PAGE_W - MARGIN_R, 0.30 * inch, f"Page {doc.page}")

    # Brand strip top-right
    canvas.setFillColor(GOLD)
    canvas.rect(PAGE_W - MARGIN_R - 1.2 * inch, PAGE_H - 0.35 * inch, 1.2 * inch, 0.06 * inch, stroke=0, fill=1)
    canvas.setFillColor(NAVY)
    canvas.setFont("Helvetica-Bold", 7)
    canvas.drawRightString(
        PAGE_W - MARGIN_R, PAGE_H - 0.20 * inch, "AI PERSONAL FINANCE ADVISOR"
    )

    canvas.restoreState()
