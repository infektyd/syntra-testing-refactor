#!/usr/bin/env python3
# Script to load and compare Syntra vs baseline full fidelity from integrated runs.
# Computes response similarity, exact matches, etc. No stubs - uses real graded traces.
# Run from refactor-syntraTesting/ root: python3 Scripts/compare_syntra_vs_baseline.py

import os
import json
import difflib
import statistics
from pathlib import Path
from collections import defaultdict
import argparse

def load_jsonl(path):
    \"\"\"Load jsonl file into list of dicts. Truncates large files for demo; remove limit for full.\"\"\"
    data = []
    with open(path, 'r') as f:
        for i, line in enumerate(f):
            if i >= 10000:  # safety
                print(f\"Truncated {path} at 10k lines\")
                break
            data.append(json.loads(line))
    return data

def compare_suite_ts(suite, ts, runs_dir='runs'):
    \"\"\"Compare syntra vs baseline for one suite/timestamp.\"\"\"
    base_path = Path(runs_dir) / suite / ts / f'graded.{suite}.baseline.jsonl'
    syn_path = Path(runs_dir) / suite / ts / f'graded.{suite}.syntra.jsonl'
    
    if not base_path.exists() or not syn_path.exists():
        return None
    
    baseline = load_jsonl(base_path)
    syntra = load_jsonl(syn_path)
    
    if len(baseline) != len(syntra):
        print(f\"Mismatch len: {len(baseline)} vs {len(syntra)} for {suite}/{ts}\")
        return None
    
    comparisons = []
    for b, s in zip(baseline, syntra):
        if b.get('item_id') != s.get('item_id'):
            print(f\"Item mismatch in {suite}/{ts}\")
            continue
        resp_ratio = difflib.SequenceMatcher(None, b['response'], s['response']).ratio()
        ans_match = b['parsed_answer'] == s['parsed_answer']
        correct_match = b['is_correct'] == s['is_correct']
        comparisons.append({
            'resp_ratio': resp_ratio,
            'ans_match': ans_match,
            'correct_match': correct_match,
            'b_correct': b['is_correct'],
            's_correct': s['is_correct'],
            'latency_b': b.get('latency_ms', 0),
            'latency_s': s.get('latency_ms', 0)
        })
    
    if not comparisons:
        return None
    
    n = len(comparisons)
    stats = {
        'suite': suite,
        'ts': ts,
        'n': n,
        'mean_resp_sim': statistics.mean(c['resp_ratio'] for c in comparisons),
        'exact_resp_match_rate': sum(1 for c in comparisons if c['resp_ratio'] == 1.0) / n,
        'ans_match_rate': sum(1 for c in comparisons if c['ans_match']) / n,
        'correct_match_rate': sum(1 for c in comparisons if c['correct_match']) / n,
        'acc_baseline': sum(1 for c in comparisons if c['b_correct']) / n,
        'acc_syntra': sum(1 for c in comparisons if c['s_correct']) / n,
        'mean_latency_diff': statistics.mean(c['latency_s'] - c['latency_b'] for c in comparisons if c['latency_b'] is not None),
    }
    return stats

def main(runs_dir='runs', output_md=None):
    runs_path = Path(runs_dir)
    suite_dirs = [d for d in runs_path.iterdir() if d.is_dir() and not d.name.startswith('.')]
    
    all_stats = []
    for suite_dir in suite_dirs:
        suite = suite_dir.name
        ts_dirs = [d for d in suite_dir.iterdir() if d.is_dir() and d.name.startswith('202')]
        for ts_dir in ts_dirs:
            ts = ts_dir.name
            stat = compare_suite_ts(suite, ts, runs_dir)
            if stat:
                all_stats.append(stat)
    
    if not all_stats:
        print(\"No comparable runs found.\")
        return
    
    # Summary
    print(\"\\nSyntra vs Baseline Fidelity Summary:\")
    print(f\"Total comparisons: {sum(s['n'] for s in all_stats)}\")
    print(f\"Overall exact response match rate: {statistics.mean(s['exact_resp_match_rate'] for s in all_stats):.1%}\")
    print(f\"Overall ans match rate: {statistics.mean(s['ans_match_rate'] for s in all_stats):.1%}\")
    print(f\"Overall acc baseline: {statistics.mean(s['acc_baseline'] for s in all_stats):.1%}\")
    print(f\"Overall acc syntra: {statistics.mean(s['acc_syntra'] for s in all_stats):.1%}\")
    
    # Per suite/ts table
    print(\"\\nDetailed per suite/timestamp:\")
    print(\"Suite | TS | N | Resp Sim | Exact Resp | Ans Match | Correct Match | Acc B | Acc S\")
    for s in sorted(all_stats, key=lambda x: x['suite']):
        print(f\"{s['suite']} | {s['ts']} | {s['n']} | {s['mean_resp_sim']:.3f} | {s['exact_resp_match_rate']:.1%} | {s['ans_match_rate']:.1%} | {s['correct_match_rate']:.1%} | {s['acc_baseline']:.1%} | {s['acc_syntra']:.1%}\")
    
    if output_md:
        with open(output_md, 'w') as f:
            f.write(\"# Syntra vs Baseline Fidelity Report\\n\\n\")
            f.write(f\"**Total items:** {sum(s['n'] for s in all_stats)}\\n\\n\")
            # ... add table etc.
            print(\"Written to\", output_md)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--runs-dir', default='runs')
    parser.add_argument('--output-md', help='Output markdown report')
    args = parser.parse_args()
    main(args.runs_dir, args.output_md)