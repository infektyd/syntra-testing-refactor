#!/usr/bin/env python3
"""
Quick comparison between multiple model runs on the same suite.

CLI:
  python Tools/CMTExtractor/quick_compare.py \
    --syn runs/hf_cmt_syntra.pass2.jsonl \
    --base runs/hf_cmt_baseline.pass2.jsonl

Loads pre-graded JSONL files and prints side-by-side accuracy.
Also lists items where both models gave same normalized answer but differ from gold.
"""
import argparse
import json
import sys


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--syn", required=True, help="Syntra graded JSONL")
    ap.add_argument("--base", required=True, help="Baseline graded JSONL")
    args = ap.parse_args()

    # Load graded records: {id: rec}
    def load_grades(path):
        grades = {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    obj = json.loads(line)
                    pid = obj.get("id")
                    if isinstance(pid, str):
                        grades[pid] = obj
        except FileNotFoundError:
            print(f"ERROR: file not found: {path}", file=sys.stderr)
            sys.exit(1)
        return grades

    syn_grades = load_grades(args.syn)
    base_grades = load_grades(args.base)

    all_ids = set(syn_grades) | set(base_grades)

    syn_pass = 0
    syn_total = 0
    base_pass = 0
    base_total = 0
    same_norm_diff_gold = []

    for pid in all_ids:
        srec = syn_grades.get(pid)
        brec = base_grades.get(pid)

        if srec and srec.get("pass") is not None:
            syn_total += 1
            if srec["pass"]:
                syn_pass += 1
        if brec and brec.get("pass") is not None:
            base_total += 1
            if brec["pass"]:
                base_pass += 1

        # Check if both have same normalized pred/gold that don't match pass
        if srec and brec:
            snorm = srec.get("normalized_pred") or srec.get("pred", "")
            bnorm = brec.get("normalized_pred") or brec.get("pred", "")
            gold_normalized = srec.get("normalized_gold") or srec.get("gold", "")
            if snorm and snorm == bnorm:
                # Check if gold matches this or not
                if gold_normalized and snorm != gold_normalized:
                    same_norm_diff_gold.append({
                        "id": pid,
                        "norm": snorm,
                        "gold": gold_normalized,
                        "syn_pass": srec.get("pass", False),
                        "base_pass": brec.get("pass", False),
                        "reason_syn": srec.get("reason", ""),
                        "reason_base": brec.get("reason", "")
                    })

    syn_pct = (syn_pass / syn_total * 100) if syn_total else 0
    base_pct = (base_pass / base_total * 100) if base_total else 0

    print("Accuracy Comparison:")
    print(f"Syntra: {syn_pass}/{syn_total} ({syn_pct:.1f}%)")
    print(f"Baseline: {base_pass}/{base_total} ({base_pct:.1f}%)")

    if same_norm_diff_gold:
        print(f"\nItems with same normalized answer but different from gold ({len(same_norm_diff_gold)}):")
        for item in same_norm_diff_gold[:10]:  # Limit to 10
            print(f"- {item['id']}: norm='{item['norm']}', gold='{item['gold']}' (syn:{item['syn_pass']}, base:{item['base_pass']}, syn_reason:{item['reason_syn']}, base_reason:{item['reason_base']})")


if __name__ == "__main__":
    main()
