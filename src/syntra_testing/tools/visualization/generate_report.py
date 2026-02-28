#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict

try:
    import importlib.util as _importlib_util
    _spec = _importlib_util.find_spec("reportlab")
    PDF_AVAILABLE = _spec is not None
except Exception:
    PDF_AVAILABLE = False


def load_audit(path: str) -> Dict[str, Any]:
    """Load an audit JSON file into a dictionary."""
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def generate_md_report(suite: str, audit: Dict[str, Any], figs_dir: str, out_path: str) -> None:
    """Generate a simple markdown executive report."""
    suite_title = f"{suite.upper()} Executive Report"
    total_items = audit.get("total_items", "n/a")
    valid_gold = audit.get("valid_gold", audit.get("valid", "n/a"))

    lines: list[str] = []
    lines.append(f"# {suite_title}")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|---|---|")
    lines.append(f"| Total Items | {total_items} |")
    lines.append(f"| Valid Gold | {valid_gold} |")
    lines.append("")
    lines.append("## Visualizations")
    lines.append("")

    img_name = f"{suite}_per_type_pass_rates.png"
    img_path = os.path.join(figs_dir, img_name) if figs_dir else img_name
    if os.path.exists(img_path):
        lines.append(f"![Per-Type Pass Rates]({img_path})")
        lines.append("")

    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))


def generate_pdf_report(suite: str, audit: Dict[str, Any], figs_dir: str, out_path: str) -> None:
    """Generate a minimal PDF executive report if reportlab is available."""
    if not PDF_AVAILABLE:
        return
    # Lazy import so the module loads without reportlab present
    from reportlab.lib.pagesizes import LETTER
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

    styles = getSampleStyleSheet()
    story = [
        Paragraph(f"{suite.upper()} Executive Report", styles["Title"]),
        Spacer(1, 12),
        Paragraph(f"Total Items: {audit.get('total_items', 'n/a')}", styles["BodyText"]),
    ]
    doc = SimpleDocTemplate(out_path, pagesize=LETTER)
    doc.build(story)


def _argv_for_parse(argv: list[str] | None = None) -> list[str]:
    """Return an argv slice suitable for argparse.parse_args()."""
    if argv is None:
        argv = sys.argv
    if not argv:
        return []
    first = argv[0]
    if isinstance(first, str) and first.startswith("-"):
        return argv  # tests may patch sys.argv without a program name
    return argv[1:]


def main() -> int:
    """CLI entrypoint that returns an integer status code for tests."""
    parser = argparse.ArgumentParser(description="Generate an executive report for a suite")
    parser.add_argument("--suite", help="Suite name", default=None)
    parser.add_argument("--audit", help="Audit JSON path")
    parser.add_argument("--out", help="Output markdown path")
    parser.add_argument("--figs-dir", help="Figures directory", default=".")
    args = parser.parse_args(_argv_for_parse())

    if not args.audit:
        return 1

    suite = args.suite or "report"
    out_path = args.out or f"{suite}.report.md"
    try:
        audit = load_audit(args.audit)
    except FileNotFoundError:
        return 1
    generate_md_report(suite, audit, args.figs_dir, out_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
