import argparse
import json
import sys
import numpy as np
from pathlib import Path
from collections import defaultdict
from typing import Dict, Any, List
from datetime import datetime

def print_usage():
    usage = '''
Usage: python syntra_cmt_aggregate.py --input &lt;input.jsonl&gt; --output &lt;output.jsonl&gt; [--metrics length,stddev,unique_ratio_std] [--group-by prompt_id]

Supported metrics:
  - stddev: compute stddev of response lengths, set metrics.drift_deviation
  - unique_ratio_std: compute stddev of unique_word_ratio per prompt_id, set metrics.unique_word_ratio_std

Grouping only supports prompt_id (default).
    '''
    print(usage)

def standard_deviation(values: List[float]) -> float:
    if len(values) &lt; 2:
        return 0.0
    return float(np.std(values, ddof=0))  # population stddev like Swift

def run_aggregation(input_path: str, output_path: str, metrics_set: set, group_by_set: set):
    records: List[Dict[str, Any]] = []
    groups: Dict[str, List[int]] = defaultdict(list)
    stats = {
        'decodedRecords': 0,
        'skippedErrorLines': 0,
        'decodeFailures': 0
    }

    try:
        with open(input_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                try:
                    rec = json.loads(line)
                    if 'error' in rec:
                        stats['skippedErrorLines'] += 1
                        continue
                    groups[rec['prompt_id']].append(len(records))
                    records.append(rec)
                    stats['decodedRecords'] += 1
                except json.JSONDecodeError:
                    stats['decodeFailures'] += 1
    except FileNotFoundError:
        raise ValueError(f"Input file not found: {input_path}")
    except Exception as e:
        raise ValueError(f"Error reading input: {e}")

    # Compute metrics
    compute_drift = 'stddev' in metrics_set
    compute_unique_std = 'unique_ratio_std' in metrics_set

    for prompt_id, indices in groups.items():
        if not indices:
            continue
        lengths = [len(records[i]['response']) for i in indices]
        length_std = standard_deviation(lengths) if compute_drift else 0.0
        unique_ratios = [records[i]['metrics']['unique_word_ratio'] for i in indices]
        unique_std = standard_deviation(unique_ratios) if compute_unique_std else None

        for idx in indices:
            if compute_drift:
                records[idx]['metrics']['drift_deviation'] = length_std
            if compute_unique_std and unique_std is not None:
                records[idx]['metrics']['unique_word_ratio_std'] = unique_std

    # Write to output
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    file_exists = Path(output_path).exists()
    with open(output_path, 'a' if file_exists else 'w', encoding='utf-8') as out_f:
        if not file_exists:
            out_f.write(f"# SYNTRA CMT aggregation started {datetime.now()}\\n")
        else:
            sep = f"\\n# --- NEW AGGREGATION {datetime.now()} ---\\n"
            out_f.write(sep)
        for rec in records:
            json.dump(rec, out_f, separators=(',', ':'))
            out_f.write('\\n')
    print(f"aggregator: wrote {len(records)} records, skipped {stats['skippedErrorLines']} error lines, {stats['decodeFailures']} decode failures", file=sys.stderr)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Syntra CMT Aggregator - Python port', add_help=False)
    parser.add_argument('--input')
    parser.add_argument('--output')
    parser.add_argument('--metrics', default='length,stddev')
    parser.add_argument('--group-by', default='prompt_id')
    parser.add_argument('--help', '-h', action='store_true')
    args = parser.parse_args()

    if args.help:
        print_usage()
        sys.exit(0)

    if not args.input or not args.output:
        print_usage()
        sys.exit(1)

    metrics_list = [m.strip().lower() for m in args.metrics.split(',') if m.strip()]
    metrics_set = set(metrics_list)
    group_by_list = [g.strip().lower() for g in args.group_by.split(',') if g.strip()]
    if 'prompt_id' not in group_by_list:
        print("Warning: only prompt_id grouping supported; using it.", file=sys.stderr)
        group_by_list = ['prompt_id']

    try:
        run_aggregation(args.input, args.output, metrics_set, set(group_by_list))
    except Exception as e:
        print(f"aggregator: {e}", file=sys.stderr)
        sys.exit(1)