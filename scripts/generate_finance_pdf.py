#!/usr/bin/env python3
"""
AI Personal Finance Advisor — PDF Report Generator CLI
======================================================

Thin CLI entrypoint and compatibility shim for the modular `scripts/pdf/` package.

Inputs:
  --data PATH       Path to a JSON file containing the financial plan data.
                    See `pdf.demo_data._demo_data()` for the schema.
  --output PATH     Output PDF path. Defaults to FINANCE-PLAN.pdf.
  --demo            Generate a sample report with built-in demo data.

This is NOT financial advice.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from scoring import score_grade, score_signal
from pdf.demo_data import _demo_data

try:
    from pdf.pages import build_pdf
except ImportError as exc:  # pragma: no cover
    sys.stderr.write(
        "ERROR: ReportLab is required.\n"
        "Install with:  pip3 install 'reportlab>=4.0.0'\n"
        f"Underlying error: {exc}\n"
    )
    sys.exit(1)

__all__ = ["build_pdf", "_demo_data", "score_grade", "score_signal", "main"]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate a Personal Financial Plan PDF (AI Personal Finance Advisor)."
    )
    parser.add_argument("--data", help="Path to a JSON file containing plan data.")
    parser.add_argument(
        "--output",
        default=None,
        help="Output PDF path (default: FINANCE-PLAN.pdf, or FINANCE-PLAN-sample.pdf for --demo).",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Generate a sample report with built-in demo data.",
    )
    args = parser.parse_args()

    if not args.demo and not args.data:
        parser.error("Provide --data <path-to-json> or use --demo for a sample report.")

    if args.demo:
        data = _demo_data()
        output_path = args.output or "FINANCE-PLAN-sample.pdf"
    else:
        output_path = args.output or "FINANCE-PLAN.pdf"
        try:
            with open(args.data, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, json.JSONDecodeError) as exc:
            sys.stderr.write(f"ERROR reading --data file: {exc}\n")
            return 1
        if not isinstance(data, dict):
            sys.stderr.write("ERROR: --data JSON root must be an object.\n")
            return 1

    out_dir = os.path.dirname(os.path.abspath(output_path))
    if out_dir and not os.path.exists(out_dir):
        os.makedirs(out_dir, exist_ok=True)

    try:
        build_pdf(data, output_path)
    except Exception as exc:  # pragma: no cover
        sys.stderr.write(f"ERROR generating PDF: {exc}\n")
        return 2

    print(f"✓ Generated: {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
