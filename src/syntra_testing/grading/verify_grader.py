#!/usr/bin/env python3
"""
Post-implementation verification script for the robust Hf-CMT grader.
Sanity-checks known problematic indices (12, 17, 20) and normalization/tolerance logic.
"""

import json
import re
from grader_utils import (
    extract_last_boxed, strip_math_wrappers, looks_multichoice, normalize_multichoice,
    parse_numeric_list, numeric_equal, allowed_choice_set_from_prompt, gold_valid_against_allowed
)


def load_suite():
    """Load hf_cmt.jsonl by index."""
    suite = {}
    with open("prompts/suites/hf_cmt.jsonl", "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            idx = obj.get("index")
            if idx is not None:
                suite[idx] = obj
    return suite


def verify_gold_errors(suite):
    """Check gold error detection for known indices."""
    print("=== Gold Error Verification ===")
    checks = {
        12: ("e in gold but only a-d allowed", True),  # Known bug
    }
    for idx, (desc, expect_error) in checks.items():
        item = suite.get(idx)
        if not item:
            print(f"SKIP: Index {idx} not found")
            continue
        gold_raw = item.get("solution", "")
        gold = strip_math_wrappers(extract_last_boxed(gold_raw) or "")
        prompt = item.get("prompt", "")
        allowed = allowed_choice_set_from_prompt(prompt)
        error = not gold_valid_against_allowed(gold, allowed)
        status = "PASS" if error == expect_error else "FAIL"
        print(f"{status}: Index {idx} ({desc}): error={error}, expected={expect_error}")


def verify_normalization_and_tolerance(suite):
    """Verify multichoice normalization and numeric tolerance."""
    print("\n=== Normalization & Tolerance Verification ===")
    # MC example: assume index 5 is "a; b; d", can normalize "b; a; d" to same
    mc_idx = 5  # a;b;d
    item = suite.get(mc_idx)
    if item:
        gold_raw = item.get("solution", "")
        gold = strip_math_wrappers(extract_last_boxed(gold_raw) or "")
        variants = ["a;b;d", "d; b; a", "b;a;d"]
        for var in variants:
            norm_gold = normalize_multichoice(gold) if looks_multichoice(gold) else gold
            norm_var = normalize_multichoice(var) if looks_multichoice(var) else var
            match = norm_gold == norm_var
            print(f"MC Norm: '{gold}' vs '{var}' -> '{norm_gold}' == '{norm_var}': {match}")

    # Numeric tolerance
    num_gold = [(2.09, 1.21), (0.00, 2.41), (-2.09, 1.21), (-2.09, -1.21), (0.00, -2.41), (2.09, -1.21)]
    variants = [
        [(2.091, 1.211), (0.0, 2.411), (-2.091, 1.211), (-2.091, -1.211), (0.0, -2.411), (2.091, -1.211)],  # Small diff
        [(2.09, 1.21), (0.0, 2.41), (-2.09, 1.21), (-2.09, -1.21), (0.0, -2.41), (2.09, -1.21)],  # Exact
    ]
    for i, var in enumerate(variants):
        parsed_gold = parse_numeric_list(str(num_gold))
        parsed_var = parse_numeric_list(str(var))
        eq = numeric_equal(parsed_var, parsed_gold, 0.02) if parsed_var and parsed_gold else False
        print(f"Numeric Tol {i+1}: diff max={max(abs(x-y) if isinstance(x, tuple) and isinstance(y, tuple) else abs(float(x)-float(y)) for x, y in zip(var, num_gold) if x and y) if len(var) == len(num_gold) else 'len_mismatch':.3f}, equal at tol=0.02: {eq}")


def main():
    suite = load_suite()
    verify_gold_errors(suite)
    verify_normalization_and_tolerance(suite)
    print("\nVerification complete.")


if __name__ == "__main__":
    main()
