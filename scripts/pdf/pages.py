"""Page builders and document assembly for the Financial Plan PDF."""

from __future__ import annotations

from typing import Any, Dict, List

from reportlab.lib.pagesizes import LETTER
from reportlab.platypus import BaseDocTemplate, Frame, PageTemplate

from .pages_core import build_cash_flow, build_cover, build_debt_summary, build_score_dashboard
from .pages_plan import build_90_day_plan, build_action_items, build_investments, build_protection, build_retirement
from .theme import MARGIN_B, MARGIN_L, MARGIN_R, MARGIN_T, PAGE_H, PAGE_W, _draw_footer, build_styles

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


__all__ = [
    "build_cover",
    "build_score_dashboard",
    "build_cash_flow",
    "build_debt_summary",
    "build_investments",
    "build_retirement",
    "build_protection",
    "build_action_items",
    "build_90_day_plan",
    "build_pdf",
]
