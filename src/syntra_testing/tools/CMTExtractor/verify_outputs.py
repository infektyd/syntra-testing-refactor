#!/usr/bin/env python3
"""
VerifierAgent: Auto-verify outputs for suites (v2.1+).

Purpose: Confirm JSONL schema, numerical coherence in audit summary, and baseline diffs (<1% tolerance).

Inputs:
- --audit: Audit summary JSON (required).
- --expected: Expected baseline JSON (default: runs/expected/{suite}_audit_summary.json).
- --suite: Suite name (default: hf_cmt).
- --version: Show version and exit.

Outputs: ✅ "Verification PASSED" or [ERR] diff summary.

Example:
    python verify_outputs.py --audit runs/hf_cmt/hf_cmt_audit_summary.json --expected runs/expected/hf_cmt_audit_summary.json --suite hf_cmt
"""
import argparse
import json
import sys
from pathlib import Path
from typing import Dict, Any

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

def validate_schema(audit_path: str) -> bool:
    """Validates the schema of an audit JSON file.

    This function checks for the presence of required keys and ensures that
    numeric keys have numeric values.

    Args:
        audit_path: The path to the audit JSON file.

    Returns:
        True if the schema is valid, False otherwise.
    """
    required_keys = {'total_items', 'valid_gold', 'gold_invalid', 'identical_model_predictions', 'shared_identity_indices', 'mc_identity_compared', 'raw_identity_compared', 'cross_mode_skipped'}
    numeric_keys = {'total_items', 'valid_gold', 'gold_invalid', 'identical_model_predictions', 'shared_identity_indices', 'mc_identity_compared', 'raw_identity_compared', 'cross_mode_skipped'}
    
    try:
        with open(audit_path, 'r') as f:
            audit = json.load(f)
        
        missing = required_keys - set(audit.keys())
        if missing:
            logger.error(f"Missing keys: {missing}")
            return False
        
        for key in numeric_keys:
            if key in audit and not isinstance(audit[key], (int, float)):
                logger.error(f"Key {key} not numeric: {type(audit[key])}")
                return False
        
        return True
    except Exception as e:
        logger.error(f"Schema validation failed: {e}")
        return False

def check_numerical_coherence(audit: Dict[str, Any]) -> bool:
    """Checks the numerical coherence of an audit summary.

    This function verifies that 'shared' is equal to the sum of 'mc', 'raw',
    and 'skipped'.

    Args:
        audit: The audit summary dictionary.

    Returns:
        True if the numbers are coherent, False otherwise.
    """
    shared = audit.get('shared_identity_indices', 0)
    mc = audit.get('mc_identity_compared', 0)
    raw = audit.get('raw_identity_compared', 0)
    skipped = audit.get('cross_mode_skipped', 0)
    
    if shared != mc + raw + skipped:
        logger.error(f"Numerical incoherence: shared={shared}, mc+raw+skipped={mc + raw + skipped}")
        return False
    return True

def diff_baseline(audit: Dict[str, Any], expected_path: str, tolerance: float = 0.01) -> bool:
    """Compares key metrics in an audit summary against a baseline.

    This function checks if the relative difference between the current and
    expected values for key metrics is within a given tolerance.

    Args:
        audit: The current audit summary dictionary.
        expected_path: The path to the expected baseline JSON file.
        tolerance: The tolerance for the relative difference.

    Returns:
        True if the differences are within the tolerance, False otherwise.
    """
    try:
        with open(expected_path, 'r') as f:
            expected = json.load(f)
        
        key_metrics = ['identical_model_predictions', 'valid_gold']
        diffs = []
        for key in key_metrics:
            current = audit.get(key, 0)
            exp = expected.get(key, 0)
            if exp != 0:
                rel_diff = abs(current - exp) / exp
                if rel_diff > tolerance:
                    diffs.append(f"{key}: {current} vs {exp} (diff {rel_diff*100:.1f}%)")
        
        if diffs:
            logger.error(f"Baseline diffs exceed 1%: {', '.join(diffs)}")
            return False
        return True
    except FileNotFoundError:
        logger.warn(f"Expected baseline not found: {expected_path}. Skipping diff.")
        return True
    except Exception as e:
        logger.error(f"Baseline diff failed: {e}")
        return False

def main():
    """The main entry point for the output verification script."""
    parser = argparse.ArgumentParser(description="Verify outputs (v2.1)")
    parser.add_argument("--version", action="version", version=get_version())
    parser.add_argument("--audit", required=True, help="Audit summary JSON")
    parser.add_argument("--expected", help="Expected baseline JSON")
    parser.add_argument("--suite", default="hf_cmt", help="Suite name (default: hf_cmt)")
    # Robust parsing for pytest-patched sys.argv where argv[0] may be an option
    argv = sys.argv
    parse_list = argv if (argv and isinstance(argv[0], str) and argv[0].startswith("-")) else argv[1:]
    args = parser.parse_args(parse_list)

    suite = args.suite
    expected_path = args.expected or f"runs/expected/{suite}_audit_summary.json"

    # Load audit
    try:
        with open(args.audit, 'r') as f:
            audit = json.load(f)
    except Exception as e:
        logger.error(f"Failed to load audit: {e}")
        return 1

    passed = True
    passed = validate_schema(args.audit) and passed
    passed = check_numerical_coherence(audit) and passed
    passed = diff_baseline(audit, expected_path) and passed

    if passed:
        logger.info("✅ Verification PASSED")
    else:
        logger.error("[ERR] Verification FAILED")
        return 1
    return 0

if __name__ == "__main__":
    exit(main())
