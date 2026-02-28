#!/usr/bin/env python3
"""
VizAgent: Generate figures from graded outputs for suites (v2.1+).

Purpose: Create bar charts for per-type pass rates and donut charts for model prediction identity using Matplotlib. Supports multi-suite via --suite.

Inputs:
- --suite: Suite name (default: hf_cmt).
- --syn: Path to SYNTRA pass2 JSONL (default: runs/{suite}/syntra/{suite}_syntra.pass2.jsonl).
- --base: Path to Baseline pass2 JSONL (default: runs/{suite}/baseline/{suite}_baseline.pass2.jsonl).
- --audit: Path to audit summary JSON (default: runs/{suite}/{suite}_audit_summary.json).
- --outdir: Output directory for PNG figures (default: runs/{suite}/figs).

Outputs:
- {suite}_per_type_pass_rates.png: Bar chart of pass rates by type.
- {suite}_identity_donut.png: Donut chart showing identical vs. non-identical predictions.

Example CLI:
    python viz_hf_cmt.py --suite hf_cmt --syn runs/hf_cmt/syntra/hf_cmt_syntra.pass2.jsonl --base runs/hf_cmt/baseline/hf_cmt_baseline.pass2.jsonl --audit runs/hf_cmt/hf_cmt_audit_summary.json --outdir runs/hf_cmt/figs
"""
import argparse
import json
import os
import sys
from collections import defaultdict
import matplotlib.pyplot as plt
from pathlib import Path

try:
    from ..common import logger, get_version
except ImportError:  # pragma: no cover - allow standalone execution
    CURRENT_DIR = Path(__file__).resolve().parent
    PARENT_DIR = CURRENT_DIR.parent
    for candidate in (PARENT_DIR, CURRENT_DIR):
        candidate_str = str(candidate)
        if candidate_str not in sys.path:
            sys.path.insert(0, candidate_str)
    from common import logger, get_version  # type: ignore

try:
    from ..common.type_utils import type_from_id
except ImportError:
    from common.type_utils import type_from_id  # type: ignore

def load_jsonl(path):
    """Loads a JSONL file.

    Args:
        path: The path to the JSONL file.

    Returns:
        A list of dictionaries, where each dictionary represents a line in the file.
    """
    data = []
    with open(path, 'r') as f:
        for line in f:
            line = line.strip()
            if line:
                data.append(json.loads(line))
    return data

def first_existing(paths):
    """Finds the first existing file from a list of paths.

    Args:
        paths: A list of file paths.

    Returns:
        The first path that exists, or the first path in the list if none exist.
    """
    for path in paths:
        if path and os.path.exists(path):
            return path
    return paths[0] if paths else None

def get_type(row):
    """Gets the problem type from a data row.

    Args:
        row: A dictionary representing a row of data.

    Returns:
        The problem type as a string.
    """
    typ = row.get("type")
    if typ and typ != "OTHER":
        return typ
    return type_from_id(row.get("id", "")) or "OTHER"

def compute_pass_rates(data):
    """Computes pass rates by problem type.

    Args:
        data: A list of dictionaries, where each dictionary represents a graded response.

    Returns:
        A tuple containing:
        - A dictionary of pass rates by type.
        - A sorted list of types.
        - The number of unmapped items.
    """
    type_stats = defaultdict(lambda: {'passes': 0, 'total': 0})
    unmapped = 0
    for row in data:
        typ = get_type(row)
        if typ == "OTHER":
            unmapped += 1
        else:
            type_stats[typ]['total'] += 1
            if row.get('pass', False):
                type_stats[typ]['passes'] += 1
    rates = {}
    for typ in type_stats:
        total = type_stats[typ]['total']
        passes = type_stats[typ]['passes']
        rates[typ] = (passes / total * 100) if total > 0 else 0
    return rates, sorted(type_stats.keys()), unmapped

def main():
    """The main entry point for the visualization script."""
    parser = argparse.ArgumentParser(description='Generate visualization for suite results (v2.1+)')
    parser.add_argument('--version', action='version', version=get_version())
    parser.add_argument('--suite', default='hf_cmt', help='Suite name (default: hf_cmt)')
    parser.add_argument('--syn', help='Path to SYNTRA pass2 JSONL (default: runs/{suite}/syntra/{suite}_syntra.pass2.jsonl)')
    parser.add_argument('--base', help='Path to Baseline pass2 JSONL (default: runs/{suite}/baseline/{suite}_baseline.pass2.jsonl)')
    parser.add_argument('--audit', help='Path to audit summary JSON (default: runs/{suite}/{suite}_audit_summary.json)')
    parser.add_argument('--outdir', help='Output directory for figures (default: runs/{suite}/figs)')
    args = parser.parse_args()

    suite = args.suite
    syn_path = args.syn or first_existing([
        os.path.join("runs", suite, "syntra", f"{suite}_syntra.pass2.jsonl"),
        f"runs/syntra/{suite}_syntra.pass2.jsonl",
        f"runs/{suite}_syntra.pass2.jsonl",
    ])
    base_path = args.base or first_existing([
        os.path.join("runs", suite, "baseline", f"{suite}_baseline.pass2.jsonl"),
        f"runs/baseline/{suite}_baseline.pass2.jsonl",
        f"runs/{suite}_baseline.pass2.jsonl",
    ])
    audit_path = args.audit or first_existing([
        os.path.join("runs", suite, f"{suite}_audit_summary.json"),
        f"runs/{suite}_audit_summary.json",
    ])
    outdir = args.outdir or os.path.join("runs", suite, "figs")

    # Load data
    syn_data = load_jsonl(syn_path)
    base_data = load_jsonl(base_path)

    # Compute pass rates
    syn_rates, syn_types, unmapped_syn = compute_pass_rates(syn_data)
    base_rates, base_types, unmapped_base = compute_pass_rates(base_data)
    unmapped = unmapped_syn + unmapped_base
    if unmapped > 0:
        logger.warn(f"[WARN] Unmapped items: {unmapped}")

    # All types
    all_types = sorted(set(syn_types + base_types))

    # Ensure all types present (0 if missing)
    for typ in all_types:
        syn_rates.setdefault(typ, 0)
        base_rates.setdefault(typ, 0)

    # Load audit
    with open(audit_path, 'r') as f:
        audit = json.load(f)
    identical = audit.get('identical_model_predictions', 0)
    shared = audit.get('shared_identity_indices', len(set(row['id'] for row in syn_data)))  # Fallback
    non_identical = shared - identical

    # Create output dir
    os.makedirs(outdir, exist_ok=True)

    # Bar chart
    fig, ax = plt.subplots(figsize=(12, 6))
    x = range(len(all_types))
    width = 0.35
    ax.bar([i - width/2 for i in x], [syn_rates[typ] for typ in all_types], width, label='SYNTRA', color='skyblue')
    ax.bar([i + width/2 for i in x], [base_rates[typ] for typ in all_types], width, label='Baseline', color='lightcoral')

    ax.set_xlabel('Type')
    ax.set_ylabel('Pass Rate (%)')
    ax.set_title(f'{suite.upper()} Per-Type Pass Rates (v2.1)')
    ax.set_xticks(x)
    ax.set_xticklabels(all_types, rotation=45, ha='right')
    ax.set_ylim(0, 100)
    ax.legend()

    # Add value labels
    for i, typ in enumerate(all_types):
        syn_rate = syn_rates[typ]
        base_rate = base_rates[typ]
        ax.text(i - width/2, syn_rate + 1, f'{syn_rate:.1f}%', ha='center', va='bottom')
        ax.text(i + width/2, base_rate + 1, f'{base_rate:.1f}%', ha='center', va='bottom')

    plt.tight_layout()
    plt.savefig(os.path.join(outdir, f'{suite}_per_type_pass_rates.png'), dpi=300, bbox_inches='tight')
    plt.close()

    # Donut chart
    fig, ax = plt.subplots()
    sizes = [identical, non_identical]
    labels = [f'Identical ({identical})', f'Non-Identical ({non_identical})']
    colors = ['lightblue', 'lightcoral']
    wedges, texts, autotexts = ax.pie(sizes, labels=labels, colors=colors, autopct='%1.1f%%',
                                      startangle=90, wedgeprops=dict(width=0.5))

    centre_circle = plt.Circle((0,0), 0.70, fc='white')
    fig.gca().add_artist(centre_circle)
    ax.set_title(f'{suite.upper()} Model Prediction Identity (v2.1)')

    plt.tight_layout()
    plt.savefig(os.path.join(outdir, f'{suite}_identity_donut.png'), dpi=300, bbox_inches='tight')
    plt.close()

    logger.info(f"Figures saved to {outdir}/")

if __name__ == '__main__':
    main()
