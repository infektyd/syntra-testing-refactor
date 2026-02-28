#!/usr/bin/env python3
"""
SYNTRA Benchmark Aggregator
Scans runs/ directory for benchmark results and creates unified overview.

Usage:
    python tools/aggregate_benchmarks.py

Outputs:
    runs/summary/benchmarks_overview.csv
    runs/summary/benchmarks_overview.md
    runs/summary/overview.png (if matplotlib available)
"""

import os
import sys
import json
import csv
import glob
import re
import time
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

try:
    from Tools.common.logger import get_logger
    logger = get_logger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)
    logging.basicConfig(level=logging.INFO)


# Known benchmark suites and their patterns
SUITE_PATTERNS = {
    'cmt': {
        'pattern': 'cmt*.pass1.jsonl',
        'benchmark': 'CMT',
        'split': 'test'
    },
    'hf_cmt': {
        'pattern': 'hf_cmt*pass1.jsonl',
        'benchmark': 'CMT',
        'split': 'test'
    },
    'arc_challenge': {
        'pattern': 'arc_challenge*pass1.jsonl',
        'benchmark': 'ARC-Challenge',
        'split': 'validation'
    },
    'arc_easy': {
        'pattern': 'arc_easy*pass1.jsonl',
        'benchmark': 'ARC-Easy',
        'split': 'validation'
    },
    'gsm8k_test': {
        'pattern': 'gsm8k_test*pass1.jsonl',
        'benchmark': 'GSM8K',
        'split': 'test'
    },
    'gsm8k_train': {
        'pattern': 'gsm8k_train*pass1.jsonl',
        'benchmark': 'GSM8K',
        'split': 'train'
    },
    'gsm8k': {
        'pattern': 'gsm8k*.pass1.jsonl',
        'benchmark': 'GSM8K',
        'split': 'test'
    },
    'arc_challenge_new': {
        'pattern': 'arc_challenge*.pass1.jsonl',
        'benchmark': 'ARC-Challenge',
        'split': 'validation'
    }
}


def extract_metrics_from_pass1(pass1_path: str) -> Dict[str, Any]:
    """
    Extract metrics from a pass1.jsonl file.

    Args:
        pass1_path: Path to pass1.jsonl file

    Returns:
        Dict with pass1, n, latency_mean_ms (if available)
    """
    records = []
    latencies = []

    try:
        with open(pass1_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                    records.append(record)

                    # Extract latency if available
                    latency = record.get('latency_ms')
                    if latency and isinstance(latency, (int, float)):
                        latencies.append(float(latency))

                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse JSONL line in {pass1_path}: {e}")
                    continue

    except Exception as e:
        logger.error(f"Failed to read {pass1_path}: {e}")
        return {}

    if not records:
        return {}

    # Calculate metrics
    n_total = len(records)
    n_correct = sum(1 for r in records if r.get('pass', False))
    pass1 = n_correct / n_total if n_total > 0 else 0.0

    metrics = {
        'pass1': pass1,
        'n': n_total,
        'n_correct': n_correct
    }

    if latencies:
        metrics['latency_mean_ms'] = sum(latencies) / len(latencies)

    return metrics


def extract_metrics_from_report(report_path: str) -> Dict[str, Any]:
    """
    Extract additional metrics from eval.report.md file.

    Args:
        report_path: Path to eval.report.md file

    Returns:
        Dict with additional metrics like latency
    """
    metrics = {}

    try:
        with open(report_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Look for latency information
        # Pattern: "**Latency (mean)**: 1250.3 ms" or "Latency (mean): 1250.3 ms"
        latency_match = re.search(r'\*\*Latency \(mean\)\*\*:\s*([\d.]+)\s*ms', content)
        if not latency_match:
            latency_match = re.search(r'Latency \(mean\):\s*([\d.]+)\s*ms', content)
        if latency_match:
            metrics['latency_mean_ms'] = float(latency_match.group(1))

        # Look for pass@1 accuracy
        # Pattern: "**Pass@1 Accuracy**: 85.00%" or "Pass@1 Accuracy: 85.00%"
        pass1_match = re.search(r'\*\*Pass@1 Accuracy\*\*:\s*([\d.]+)%', content)
        if not pass1_match:
            pass1_match = re.search(r'Pass@1 Accuracy:\s*([\d.]+)%', content)
        if pass1_match:
            metrics['pass1'] = float(pass1_match.group(1)) / 100.0

        # Alternative pattern: "Overall accuracy: 10/49 (20.4%)"
        overall_match = re.search(r'Overall accuracy:\s*(\d+)/(\d+)\s*\(([\d.]+)%\)', content)
        if overall_match:
            n_correct = int(overall_match.group(1))
            n_total = int(overall_match.group(2))
            pass1_pct = float(overall_match.group(3))
            metrics['pass1'] = pass1_pct / 100.0
            metrics['n'] = n_total
            metrics['n_correct'] = n_correct

        # Look for total count (if not found above)
        # Pattern: "**Total Questions**: 20" or "Total Questions: 20"
        if 'n' not in metrics:
            n_match = re.search(r'\*\*Total Questions\*\*:\s*(\d+)', content)
            if not n_match:
                n_match = re.search(r'Total Questions:\s*(\d+)', content)
            if n_match:
                metrics['n'] = int(n_match.group(1))

    except Exception as e:
        logger.warning(f"Failed to parse report {report_path}: {e}")

    return metrics


def find_benchmark_files(runs_dir: str) -> List[Dict[str, Any]]:
    """
    Scan runs directory for benchmark result files.

    Args:
        runs_dir: Path to runs directory

    Returns:
        List of benchmark file info dicts
    """
    benchmark_files = []

    for suite_key, suite_info in SUITE_PATTERNS.items():
        pattern = suite_info['pattern']
    
        # Find pass1.jsonl files
        pass1_pattern = os.path.join(runs_dir, "**", pattern)
        logger.info(f"Searching for pass1 candidates with glob: {pass1_pattern}")
        pass1_files = glob.glob(pass1_pattern, recursive=True)
        logger.info(f"Found {len(pass1_files)} candidate files for suite {suite_key}")
        for p in pass1_files:
            logger.info(f"  candidate: {p}")
    
        for pass1_file in pass1_files:
            # Determine system (baseline/syntra) from path
            path_parts = Path(pass1_file).parts
            system = 'unknown'
    
            if 'baseline' in path_parts:
                system = 'baseline'
            elif 'syntra' in path_parts:
                system = 'syntra'
            else:
                # Check filename for system indicator
                filename = os.path.basename(pass1_file)
                if 'baseline' in filename:
                    system = 'baseline'
                elif 'syntra' in filename:
                    system = 'syntra'
    
            # Find corresponding report file
            report_file = pass1_file.replace('pass1.jsonl', 'eval.report.md')
            if not os.path.exists(report_file):
                # Try other patterns
                report_file = pass1_file.replace('.pass1.jsonl', '.report.md')
                if not os.path.exists(report_file):
                    report_file = None
                else:
                    logger.info(f"Using alternate report file for {pass1_file}: {report_file}")
            else:
                logger.info(f"Matched report file for {pass1_file}: {report_file}")
    
            benchmark_files.append({
                'suite': suite_key,
                'benchmark': suite_info['benchmark'],
                'split': suite_info['split'],
                'system': system,
                'pass1_file': pass1_file,
                'report_file': report_file
            })
    
    logger.info(f"Total benchmark file candidates discovered: {len(benchmark_files)}")
    return benchmark_files


def aggregate_benchmarks(runs_dir: str = 'runs') -> List[Dict[str, Any]]:
    """
    Aggregate benchmark results from runs directory.

    Args:
        runs_dir: Path to runs directory

    Returns:
        List of aggregated benchmark results
    """
    # Detect mode from environment for safety checks and reporting
    mode = "LIVE" if os.environ.get('RUN_SYNTRA', '0') == '1' else "TEST"
    logger.info(f"Scanning {runs_dir} for benchmark results... Mode: {mode}")

    benchmark_files = find_benchmark_files(runs_dir)

    if mode == "LIVE" and not benchmark_files:
        logger.error(
            "RUN_SYNTRA=1 but no pass1.jsonl artifacts were discovered. "
            "Confirm SYNTRA_TEST_MODE=0 and rerun the suites so LIVE generations are captured."
        )
    logger.info(f"Found {len(benchmark_files)} benchmark result files")

    results = []

    for bf in benchmark_files:
        logger.info(f"Processing {bf['benchmark']} ({bf['system']})...")

        # Extract metrics from pass1 file
        metrics = extract_metrics_from_pass1(bf['pass1_file'])

        # Extract additional metrics from report file
        if bf['report_file']:
            report_metrics = extract_metrics_from_report(bf['report_file'])
            metrics.update(report_metrics)

        if metrics:
            # Attach mode information for downstream reporting
            result = {
                'benchmark': bf['benchmark'],
                'split': bf['split'],
                'system': bf['system'],
                'mode': mode,
                **metrics
            }
            results.append(result)
        else:
            logger.warning(f"No metrics extracted from {bf['pass1_file']}")

    # Sort results
    results.sort(key=lambda x: (x['benchmark'], x['split'], x['system']))

    return results


def merge_baseline_syntra(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Merge baseline and syntra results and compute deltas.

    Args:
        results: List of individual results

    Returns:
        List with merged results including deltas
    """
    merged = []

    # Group by benchmark and split
    groups = {}
    for r in results:
        key = (r['benchmark'], r['split'])
        if key not in groups:
            groups[key] = {}
        groups[key][r['system']] = r

    # Merge and compute deltas
    for (benchmark, split), systems in groups.items():
        baseline = systems.get('baseline')
        syntra = systems.get('syntra')

        # Add individual results
        if baseline:
            merged.append(baseline)
        if syntra:
            merged.append(syntra)

        # Add delta row if both exist
        if baseline and syntra:
            delta = {
                'benchmark': benchmark,
                'split': split,
                'system': 'delta',
                'pass1': syntra.get('pass1', 0) - baseline.get('pass1', 0),
                'n': syntra.get('n', 0),  # Use syntra count
            }

            # Add latency delta if both have latency
            if 'latency_mean_ms' in syntra and 'latency_mean_ms' in baseline:
                delta['latency_mean_ms'] = syntra['latency_mean_ms'] - baseline['latency_mean_ms']

            merged.append(delta)

    return merged


def write_csv(results: List[Dict[str, Any]], output_path: str):
    """Write results to CSV file."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    if not results:
        logger.warning("No results to write")
        return

    fieldnames = ['benchmark', 'split', 'system', 'pass1', 'n', 'latency_mean_ms']

    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for result in results:
            # Format values
            row = {}
            for field in fieldnames:
                value = result.get(field, '')
                if isinstance(value, float):
                    if field == 'pass1':
                        row[field] = f'{value:.3f}'
                    elif field == 'latency_mean_ms':
                        row[field] = f'{value:.1f}'
                    else:
                        row[field] = str(value)
                else:
                    row[field] = str(value)
            writer.writerow(row)

    logger.info(f"Wrote {len(results)} results to {output_path}")


def write_markdown(results: List[Dict[str, Any]], output_path: str):
    """Write results to Markdown table."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("# Benchmark Results Overview\n\n")
        f.write("Aggregated results from all benchmark suites.\n\n")

        if not results:
            f.write("No results found.\n")
            return

        # Write table (including Mode)
        f.write("| Benchmark | Split | System | Mode | Pass@1 | N | Latency (ms) |\n")
        f.write("|-----------|-------|--------|------|--------|---|--------------|\n")

        for result in results:
            benchmark = result.get('benchmark', '')
            split = result.get('split', '')
            system = result.get('system', '')
            mode_val = result.get('mode', '')
            pass1 = result.get('pass1', '')
            n = result.get('n', '')
            latency = result.get('latency_mean_ms', '')

            # Format values
            if isinstance(pass1, float):
                if system == 'delta':
                    pass1_str = f'{pass1:+.3f}'
                else:
                    pass1_str = f'{pass1:.3f}'
            else:
                pass1_str = str(pass1)

            if isinstance(latency, float):
                if system == 'delta':
                    latency_str = f'{latency:+.1f}'
                else:
                    latency_str = f'{latency:.1f}'
            else:
                latency_str = str(latency)

            f.write(f"| {benchmark} | {split} | {system} | {mode_val} | {pass1_str} | {n} | {latency_str} |\n")

        f.write("\n")
        f.write("**Notes:**\n")
        f.write("- Pass@1: Accuracy (0.0-1.0 for baseline/syntra, delta for difference)\n")
        f.write("- N: Number of questions\n")
        f.write("- Latency: Mean response time in milliseconds\n")

    logger.info(f"Wrote markdown table to {output_path}")


def create_chart(results: List[Dict[str, Any]], output_path: str):
    """Create bar chart of pass@1 by benchmark (if matplotlib available)."""
    try:
        import matplotlib.pyplot as plt
        import numpy as np
    except ImportError:
        logger.info("Matplotlib not available, skipping chart generation")
        return

    # Filter to baseline/syntra results only
    chart_data = [r for r in results if r.get('system') in ['baseline', 'syntra']]

    if not chart_data:
        logger.info("No baseline/syntra data for chart")
        return

    # Group by benchmark
    benchmarks = {}
    for r in chart_data:
        key = r['benchmark']
        if key not in benchmarks:
            benchmarks[key] = {}
        benchmarks[key][r['system']] = r.get('pass1', 0)

    # Prepare data for plotting
    bench_names = list(benchmarks.keys())
    baseline_scores = [benchmarks[b].get('baseline', 0) for b in bench_names]
    syntra_scores = [benchmarks[b].get('syntra', 0) for b in bench_names]

    x = np.arange(len(bench_names))
    width = 0.35

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.bar(x - width/2, baseline_scores, width, label='Baseline', alpha=0.8)
    ax.bar(x + width/2, syntra_scores, width, label='SYNTRA', alpha=0.8)

    ax.set_xlabel('Benchmark')
    ax.set_ylabel('Pass@1 Accuracy')
    ax.set_title('Benchmark Performance Comparison')
    ax.set_xticks(x)
    ax.set_xticklabels(bench_names, rotation=45, ha='right')
    ax.legend()
    ax.grid(True, alpha=0.3)

    # Add value labels
    for i, (b, s) in enumerate(zip(baseline_scores, syntra_scores)):
        ax.text(i - width/2, b + 0.01, '.2f', ha='center', va='bottom', fontsize=8)
        ax.text(i + width/2, s + 0.01, '.2f', ha='center', va='bottom', fontsize=8)

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()

    logger.info(f"Created chart at {output_path}")


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Aggregate SYNTRA benchmark results into overview"
    )
    parser.add_argument(
        '--runs-dir',
        default='runs',
        help='Path to runs directory (default: runs)'
    )
    parser.add_argument(
        '--output-dir',
        default='runs/summary',
        help='Output directory (default: runs/summary)'
    )

    args = parser.parse_args()

    # Aggregate results
    results = aggregate_benchmarks(args.runs_dir)

    if not results:
        logger.warning("No benchmark results found")
        return

    # Merge baseline/syntra and compute deltas
    merged_results = merge_baseline_syntra(results)

    # Write outputs
    os.makedirs(args.output_dir, exist_ok=True)

    csv_path = os.path.join(args.output_dir, 'benchmarks_overview.csv')
    md_path = os.path.join(args.output_dir, 'benchmarks_overview.md')
    png_path = os.path.join(args.output_dir, 'overview.png')

    write_csv(merged_results, csv_path)
    write_markdown(merged_results, md_path)
    create_chart(merged_results, png_path)

    # Print summary
    print(f"\n=== Benchmark Aggregation Complete ===")
    print(f"Processed {len(results)} result files")
    print(f"Output files:")
    print(f"  CSV: {csv_path}")
    print(f"  Markdown: {md_path}")
    if os.path.exists(png_path):
        print(f"  Chart: {png_path}")

    # Show sample of results
    print(f"\nSample results:")
    for result in merged_results[:5]:
        print(f"  {result['benchmark']} {result['split']} {result['system']}: pass1={result.get('pass1', 'N/A')}")



if __name__ == "__main__":
    main()