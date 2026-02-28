#!/usr/bin/env python3
"""
Fix invalid gold answer entries in HF-CMT dataset.

Detects and corrects gold solutions that contain invalid choice letters
not present in the prompt's allowed options.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

from grader_utils import (
    allowed_choice_set_from_prompt,
    extract_last_boxed,
    looks_multichoice,
)

try:
    from ..common import get_version
except ImportError:  # pragma: no cover - fallback for standalone execution
    CURRENT_DIR = Path(__file__).resolve().parent
    PARENT_DIR = CURRENT_DIR.parent
    for candidate in (PARENT_DIR, CURRENT_DIR):
        candidate_str = str(candidate)
        if candidate_str not in sys.path:
            sys.path.insert(0, candidate_str)
    from common import get_version  # type: ignore


def validate_and_fix_gold(
    record: Dict[str, Any]
) -> Tuple[bool, Dict[str, Any] | None]:
    """Validates a gold record and returns information for patching if needed.

    Args:
        record: A dictionary representing a record from the dataset.

    Returns:
        A tuple containing:
        - A boolean indicating whether a fix is needed.
        - A dictionary with patch information if a fix is needed, otherwise None.
    """
    solution = record.get("solution", "")
    prompt = record.get("prompt", "")
    idx = record.get("index")

    if not solution or not prompt:
        return False, None

    # Extract boxed content
    boxed_content = extract_last_boxed(solution)
    if not boxed_content:
        return False, None

    # Check if it's multi-choice
    stripped = boxed_content.strip()
    if not looks_multichoice(stripped):
        return False, None

    # Parse allowed choices from prompt
    allowed = allowed_choice_set_from_prompt(prompt)
    if not allowed:
        # No explicit choices found, cannot validate
        return False, None

    # Tokenize the gold answer
    tokens = [t.strip().lower() for t in stripped.split(';') if t.strip()]
    if not tokens:
        return False, None

    # Filter to only valid tokens
    valid_tokens = [t for t in tokens if t in allowed]
    invalid_tokens = [t for t in tokens if t not in allowed]

    if not invalid_tokens:
        # All tokens are valid
        return False, None

    # Need to fix
    if not valid_tokens:
        # No valid tokens remain - needs manual review
        patch = {
            "index": idx,
            "old_solution": solution,
            "new_solution": solution,  # Keep unchanged
            "needs_manual_review": True,
            "reason": f"All options {sorted(tokens)} are invalid against allowed {sorted(allowed)}",
            "validated_against_allowed": sorted(allowed),
            "invalid_options": sorted(invalid_tokens),
        }
        return True, patch

    # Rebuild with only valid tokens
    new_boxed_content = ';'.join(sorted(valid_tokens))
    new_solution = f"$\\boxed{{{new_boxed_content}}}$"

    patch = {
        "index": idx,
        "old_solution": solution,
        "new_solution": new_solution,
        "needs_manual_review": False,
        "reason": f"Removed invalid option(s) {sorted(invalid_tokens)} not present in prompt choices.",
        "validated_against_allowed": sorted(allowed),
        "invalid_options": sorted(invalid_tokens),
        "kept_options": sorted(valid_tokens),
    }
    return True, patch


def main():
    """The main entry point for the gold entry fixing script."""
    ap = argparse.ArgumentParser(
        description="Fix invalid gold entries in HF-CMT dataset",
        add_help=False  # Temporarily to avoid conflict, but actually no need
    )
    ap.add_argument(
        "--version",
        action="version",
        version="unknown",
        help="Show program's version number and exit."
    )
    ap.add_argument("--version", action="version", version=get_version())
    ap.add_argument(
        "--input",
        default="prompts/suites/hf_cmt.jsonl",
        help="Input JSONL file (default: prompts/suites/hf_cmt.jsonl)",
    )
    ap.add_argument(
        "--output",
        default="prompts/suites/hf_cmt.fixed.jsonl",
        help="Output fixed JSONL file (default: prompts/suites/hf_cmt.fixed.jsonl)",
    )
    ap.add_argument(
        "--patch-log",
        default="prompts/suites/hf_cmt_gold_patch.jsonl",
        help="Patch log file (default: prompts/suites/hf_cmt_gold_patch.jsonl)",
    )
    args = ap.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)
    patch_log_path = Path(args.patch_log)

    if not input_path.exists():
        print(f"ERROR: Input file not found: {input_path}", file=sys.stderr)
        return 1

    # Load records
    records: List[Dict[str, Any]] = []
    with input_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as e:
                print(f"WARNING: Skipping invalid JSON line: {e}", file=sys.stderr)
                continue

    print(f"Loaded {len(records)} records from {input_path}")

    # Process records
    patches: List[Dict[str, Any]] = []
    fixed_records: List[Dict[str, Any]] = []

    for record in records:
        needs_fix, patch = validate_and_fix_gold(record)

        if needs_fix and patch:
            patches.append(patch)
            # Apply fix to record
            fixed_record = record.copy()
            if not patch.get("needs_manual_review", False):
                fixed_record["solution"] = patch["new_solution"]
            fixed_records.append(fixed_record)
        else:
            # Keep record as-is
            fixed_records.append(record)

    # Write output
    with output_path.open("w", encoding="utf-8") as f:
        for record in fixed_records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    print(f"✓ Wrote {len(fixed_records)} records to {output_path}")

    # Write patch log
    if patches:
        with patch_log_path.open("w", encoding="utf-8") as f:
            for patch in patches:
                f.write(json.dumps(patch, ensure_ascii=False, indent=2) + "\n")

        print(f"✓ Wrote {len(patches)} patch(es) to {patch_log_path}")
        print("\nPatches applied:")
        for patch in patches:
            idx = patch.get("index")
            manual = patch.get("needs_manual_review", False)
            reason = patch.get("reason", "")
            print(f"  - Index {idx}: {reason}")
            if manual:
                print(f"    ⚠️  NEEDS MANUAL REVIEW")
            else:
                print(f"    Old: {patch.get('old_solution', '')}")
                print(f"    New: {patch.get('new_solution', '')}")
    else:
        print("✓ No invalid gold entries found - dataset is clean!")

    return 0


if __name__ == "__main__":
    sys.exit(main())
