#!/usr/bin/env python3
"""
Enhance CMT graded files with type information and generate detailed reports.

This script:
1. Adds 'type' field to graded CMT files from the manifest
2. Re-runs analyze_results.py to get per-type statistics
3. Generates a detailed CMT report with answer comparisons
"""

import json
import sys
from pathlib import Path
from typing import Dict, Any, List
from collections import defaultdict


def load_jsonl(path: Path) -> List[Dict[str, Any]]:
    """Load JSONL file."""
    records = []
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def write_jsonl(path: Path, records: List[Dict[str, Any]]) -> None:
    """Write JSONL file."""
    with open(path, 'w', encoding='utf-8') as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + '\n')


def add_type_to_graded_files(run_dir: Path) -> None:
    """Add type field from manifest to graded files."""
    manifest_path = run_dir / "manifest.jsonl"
    if not manifest_path.exists():
        print(f"Manifest not found: {manifest_path}")
        return

    # Load manifest to get types
    manifest_records = load_jsonl(manifest_path)
    type_map = {r['item_id']: r.get('type', 'Unknown') for r in manifest_records}

    # Update graded files
    graded_files = list(run_dir.glob("graded.cmt.*.jsonl"))
    for graded_file in graded_files:
        print(f"Adding types to: {graded_file}")
        records = load_jsonl(graded_file)
        updated = 0
        for record in records:
            item_id = record.get('item_id')
            if item_id in type_map:
                record['type'] = type_map[item_id]
                updated += 1
        write_jsonl(graded_file, records)
        print(f"  Updated {updated} records")


def generate_cmt_report(run_dir: Path, stats_json: Path) -> None:
    """Generate enhanced CMT report with examples."""
    with open(stats_json, 'r') as f:
        stats = json.load(f)

    # Load graded files for examples
    syntra_path = run_dir / "graded.cmt.syntra.jsonl"
    baseline_path = run_dir / "graded.cmt.baseline.jsonl"

    syntra_records = load_jsonl(syntra_path) if syntra_path.exists() else []
    baseline_records = load_jsonl(baseline_path) if baseline_path.exists() else []

    # Group by type
    by_type = defaultdict(lambda: {'correct': 0, 'total': 0, 'examples': []})
    for record in syntra_records:
        typ = record.get('type', 'Unknown')
        by_type[typ]['total'] += 1
        if record.get('is_correct'):
            by_type[typ]['correct'] += 1
        # Keep examples of incorrect answers
        if not record.get('is_correct') and len(by_type[typ]['examples']) < 2:
            by_type[typ]['examples'].append({
                'item_id': record.get('item_id'),
                'parsed': record.get('parsed_answer'),
                'gold': record.get('gold'),
                'response_preview': record.get('response', '')[:200]
            })

    # Generate report
    report_lines = []
    report_lines.append(f"# CMT Detailed Report - {run_dir.name}\n")

    # Overall stats from stats.json
    cmt_stats = stats.get('suites', {}).get('cmt', {})
    variants = cmt_stats.get('variants', {})

    report_lines.append("## Overall Performance\n")
    for variant, data in sorted(variants.items()):
        acc = data.get('accuracy', 0.0)
        n = data.get('n', 0)
        ci = data.get('ci_wilson', [0, 0])
        report_lines.append(f"**{variant.capitalize()}**: {acc:.1%} ({n} items, 95% CI: {ci[0]:.1%}–{ci[1]:.1%})")

    # Per-type breakdown
    if by_type:
        report_lines.append("\n## Per-Type Performance (Syntra)\n")
        report_lines.append("| Type | Accuracy | Correct | Total |")
        report_lines.append("|------|----------|---------|-------|")
        for typ in sorted(by_type.keys()):
            data = by_type[typ]
            acc = data['correct'] / data['total'] if data['total'] > 0 else 0.0
            report_lines.append(f"| {typ} | {acc:.1%} | {data['correct']} | {data['total']} |")

    # Example incorrect answers
    report_lines.append("\n## Example Incorrect Answers\n")
    for typ in sorted(by_type.keys()):
        examples = by_type[typ]['examples']
        if examples:
            report_lines.append(f"\n### {typ}\n")
            for ex in examples:
                report_lines.append(f"**Item**: `{ex['item_id']}`")
                report_lines.append(f"- **Parsed**: {ex['parsed']}")
                report_lines.append(f"- **Gold**: {ex['gold']}")
                report_lines.append(f"- **Response**: {ex['response_preview']}...")
                report_lines.append("")

    # Write report
    report_path = run_dir / "cmt_detailed_report.md"
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(report_lines))

    print(f"Generated detailed report: {report_path}")


def main():
    if len(sys.argv) < 2:
        print("Usage: python enhance_cmt_reports.py <run_dir>")
        print("Example: python enhance_cmt_reports.py runs/cmt/20251030_080445")
        return 1

    run_dir = Path(sys.argv[1])
    if not run_dir.exists():
        print(f"Run directory not found: {run_dir}")
        return 1

    # Step 1: Add type field to graded files
    print("Step 1: Adding type information to graded files...")
    add_type_to_graded_files(run_dir)

    # Step 2: Generate enhanced report
    print("\nStep 2: Generating enhanced CMT report...")
    # Try multiple locations for stats_summary.json
    possible_stats_locations = [
        run_dir / "stats_summary.json",
        run_dir.parent.parent / run_dir.name / "stats_summary.json",  # runs/<timestamp>/stats_summary.json
    ]
    stats_json = None
    for loc in possible_stats_locations:
        if loc.exists():
            stats_json = loc
            print(f"Found stats at: {stats_json}")
            break

    if stats_json:
        generate_cmt_report(run_dir, stats_json)
    else:
        print(f"Stats summary not found in: {[str(p) for p in possible_stats_locations]}")
        print("Run analyze_results.py first to generate statistics")

    print("\n✓ Done!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
