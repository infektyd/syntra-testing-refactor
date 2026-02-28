#!/usr/bin/env python3
"""
Quick validation script to check gold entries against prompt allowed choices.
"""
import argparse
import json
import sys
from pathlib import Path

from grader_utils import (
    allowed_choice_set_from_prompt,
    extract_last_boxed,
    gold_valid_against_allowed,
    looks_multichoice,
)


def main():
    ap = argparse.ArgumentParser(description="Validate gold entries in HF-CMT dataset")
    ap.add_argument(
        "--answers",
        default="prompts/suites/hf_cmt.jsonl",
        help="Input JSONL file with gold answers",
    )
    args = ap.parse_args()

    input_path = Path(args.answers)
    if not input_path.exists():
        print(f"ERROR: File not found: {input_path}", file=sys.stderr)
        return 1

    # Load records
    records = []
    with input_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    print(f"Validating {len(records)} records from {input_path}\n")

    # Validate each record
    valid_count = 0
    invalid_count = 0
    invalid_records = []

    for record in records:
        idx = record.get("index")
        solution = record.get("solution", "")
        prompt = record.get("prompt", "")
        parameters = record.get("parameters", "")

        # Extract boxed content
        boxed = extract_last_boxed(solution)
        if not boxed:
            continue

        # Get allowed choices
        allowed = allowed_choice_set_from_prompt(prompt)
        if not allowed:
            allowed = allowed_choice_set_from_prompt(parameters)

        if not allowed:
            # No explicit choices - skip validation
            continue

        # Validate
        is_valid = gold_valid_against_allowed(boxed, allowed)

        if is_valid:
            valid_count += 1
        else:
            invalid_count += 1
            # Extract what's in the gold
            if looks_multichoice(boxed):
                tokens = [t.strip().lower() for t in boxed.split(';') if t.strip()]
                invalid_tokens = [t for t in tokens if t not in allowed]
                invalid_records.append({
                    "index": idx,
                    "solution": solution,
                    "boxed_content": boxed,
                    "allowed_choices": sorted(allowed),
                    "invalid_options": invalid_tokens,
                })

    # Print results
    print("=" * 70)
    print("VALIDATION SUMMARY")
    print("=" * 70)
    print(f"Total records validated:  {valid_count + invalid_count}")
    print(f"Valid gold entries:       {valid_count}")
    print(f"Invalid gold entries:     {invalid_count}")
    print()

    if invalid_records:
        print("INVALID ENTRIES:")
        print("-" * 70)
        for inv in invalid_records:
            print(f"Index {inv['index']}:")
            print(f"  Solution:        {inv['solution']}")
            print(f"  Boxed content:   {inv['boxed_content']}")
            print(f"  Allowed choices: {inv['allowed_choices']}")
            print(f"  Invalid options: {inv['invalid_options']}")
            print()
    else:
        print("✓ All gold entries are valid!")

    return 0 if invalid_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
