#!/usr/bin/env python3
"""
type_analysis.py — Analyze benchmark performance by problem type.

Generates visualizations and statistics for how baseline vs SYNTRA performs
across different problem types (e.g., HF, ED, DMRG, VMC, QMC, PEPS, SM for CMT).

Usage:
  python3 Tools/visualization/type_analysis.py \
    --summary runs/stats/stats_summary.json \
    --out-dir runs/stats \
    [--format csv,json,html]
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional
from collections import defaultdict


def load_summary(path: str) -> Dict[str, Any]:
    """Load stats_summary.json from analyze_results.py."""
    with open(path, "r") as f:
        return json.load(f)


def extract_type_stats(summary: Dict[str, Any]) -> Dict[str, Dict[str, Dict[str, Any]]]:
    """
    Extract type-level statistics from summary.

    Returns:
    {
        "suite_name": {
            "type_name": {
                "baseline": {"n": ..., "accuracy": ...},
                "syntra": {"n": ..., "accuracy": ...},
                "delta": ...,
                ...
            }
        }
    }
    """
    result: Dict[str, Dict[str, Dict[str, Any]]] = defaultdict(dict)

    for suite_name, suite_data in summary.get("suites", {}).items():
        for variant_name, variant_data in suite_data.get("variants", {}).items():
            if "by_type" in variant_data:
                for type_name, type_stats in variant_data["by_type"].items():
                    if type_name not in result[suite_name]:
                        result[suite_name][type_name] = {}

                    result[suite_name][type_name][variant_name] = {
                        "n": type_stats.get("n", 0),
                        "successes": type_stats.get("successes", 0),
                        "accuracy": type_stats.get("accuracy", 0.0),
                        "ci": type_stats.get("ci_wilson", [0.0, 1.0]),
                    }

    # Compute deltas for paired variants
    for suite_name in result:
        for type_name in result[suite_name]:
            if "baseline" in result[suite_name][type_name] and "syntra" in result[suite_name][type_name]:
                base_acc = result[suite_name][type_name]["baseline"]["accuracy"]
                syn_acc = result[suite_name][type_name]["syntra"]["accuracy"]
                result[suite_name][type_name]["delta"] = syn_acc - base_acc

    return dict(result)


def generate_type_csv(type_stats: Dict[str, Dict[str, Dict[str, Any]]], out_path: str) -> None:
    """Generate per-type CSV file."""
    import csv

    with open(out_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "Suite", "Type", "Variant", "N", "Successes", "Accuracy", "CI_Low", "CI_High"
        ])

        for suite_name in sorted(type_stats.keys()):
            for type_name in sorted(type_stats[suite_name].keys()):
                for variant_name in sorted(type_stats[suite_name][type_name].keys()):
                    if variant_name == "delta":
                        continue
                    data = type_stats[suite_name][type_name][variant_name]
                    writer.writerow([
                        suite_name,
                        type_name,
                        variant_name,
                        data.get("n", ""),
                        data.get("successes", ""),
                        f"{data.get('accuracy', 0.0):.4f}",
                        f"{data['ci'][0]:.4f}",
                        f"{data['ci'][1]:.4f}",
                    ])

    print(f"Wrote type analysis CSV: {out_path}")


def generate_type_json(type_stats: Dict[str, Dict[str, Dict[str, Any]]], out_path: str) -> None:
    """Generate per-type JSON file."""
    with open(out_path, "w") as f:
        json.dump(type_stats, f, indent=2)

    print(f"Wrote type analysis JSON: {out_path}")


def generate_type_markdown(type_stats: Dict[str, Dict[str, Dict[str, Any]]], out_path: str) -> None:
    """Generate per-type Markdown report."""
    lines = ["# Type-Level Analysis\n"]

    for suite_name in sorted(type_stats.keys()):
        lines.append(f"## {suite_name}\n")

        # Create comparison table
        lines.append("| Type | Baseline Acc | Syntra Acc | Δ | N (B) | N (S) |")
        lines.append("|------|--------------|-----------|---|-------|-------|")

        for type_name in sorted(type_stats[suite_name].keys()):
            type_data = type_stats[suite_name][type_name]

            baseline = type_data.get("baseline")
            syntra = type_data.get("syntra")
            delta = type_data.get("delta")

            if baseline and syntra:
                base_acc = baseline.get("accuracy", 0.0)
                syn_acc = syntra.get("accuracy", 0.0)
                base_n = baseline.get("n", 0)
                syn_n = syntra.get("n", 0)

                delta_str = f"{delta:+.3f}" if delta is not None else "n/a"
                lines.append(
                    f"| {type_name} | {base_acc:.3f} | {syn_acc:.3f} | {delta_str} | {base_n} | {syn_n} |"
                )

        lines.append("")

    with open(out_path, "w") as f:
        f.write("\n".join(lines))

    print(f"Wrote type analysis Markdown: {out_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Analyze benchmark performance by problem type"
    )
    parser.add_argument(
        "--summary",
        required=True,
        help="Path to stats_summary.json from analyze_results.py",
    )
    parser.add_argument(
        "--out-dir",
        default=".",
        help="Output directory for type analysis files",
    )
    parser.add_argument(
        "--format",
        default="csv,json,md",
        help="Output formats: csv, json, md (comma-separated)",
    )
    args = parser.parse_args()

    # Load summary
    try:
        summary = load_summary(args.summary)
    except Exception as e:
        print(f"ERROR: Failed to load summary: {e}", file=sys.stderr)
        return 1

    # Extract type stats
    type_stats = extract_type_stats(summary)

    if not type_stats:
        print("No type-level statistics found in summary")
        return 0

    # Create output directory
    Path(args.out_dir).mkdir(parents=True, exist_ok=True)

    # Generate outputs
    formats = [f.strip().lower() for f in args.format.split(",")]

    if "csv" in formats:
        generate_type_csv(type_stats, str(Path(args.out_dir) / "type_analysis.csv"))

    if "json" in formats:
        generate_type_json(type_stats, str(Path(args.out_dir) / "type_analysis.json"))

    if "md" in formats:
        generate_type_markdown(type_stats, str(Path(args.out_dir) / "type_analysis.md"))

    return 0


if __name__ == "__main__":
    sys.exit(main())
