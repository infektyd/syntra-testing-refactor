#!/usr/bin/env python3
"""
AuditAgent: Validate dataset and grading health for suites (v2.1+).

Purpose: Audit gold validity, model predictions, normalization, and identity between SYNTRA/baseline. Computes metrics like valid_gold, identical_model_predictions, false_negatives. Supports multi-suite via --suite.

Inputs:
- --suite: Suite name (default: hf_cmt).
- --answers: Gold answers JSONL (default: prompts/suites/{suite}.fixed.jsonl).
- --syn: SYNTRA responses JSONL (optional, auto-discovers runs/{suite}/syntra/{suite}_syntra.pass*.jsonl).
- --base: Baseline responses JSONL (optional, auto-discovers runs/{suite}/baseline/{suite}_baseline.pass*.jsonl).
- --out: Output summary JSON (default: runs/{suite}/{suite}_audit_summary.json).
- --ident-metric: Identity mode (normalized/raw/legacy, default: normalized).
- --version: Show version and exit.

Outputs:
- runs/{suite}/{suite}_audit_summary.json: Metrics (valid_gold, identical, etc.).
- runs/{suite}/{suite}_audit.jsonl: Per-index details (gold_valid, comparisons).

Example CLI:
    python hf_cmt_audit.py --suite hf_cmt --answers prompts/suites/hf_cmt.fixed.jsonl --syn runs/hf_cmt/syntra/hf_cmt_syntra.pass2.jsonl --base runs/hf_cmt/baseline/hf_cmt_baseline.pass2.jsonl --out runs/hf_cmt/hf_cmt_audit_summary.json --ident-metric normalized
"""
import argparse
import json
import glob
import os
import re
import sys
from pathlib import Path
from typing import Union

from grader_utils import (
    allowed_choice_set_from_prompt,
    canon_symbol,
    extract_last_boxed,
    gold_valid_against_allowed,
    looks_multichoice,
    normalize_multichoice,
    numeric_equal,
    parse_numeric_list,
    strip_math_wrappers,
)

try:
    from ..common import logger, get_version
except ImportError:  # pragma: no cover - allow running as standalone script
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
from common import logger, get_version  # type: ignore

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

FLOAT_TOL = 0.02


def load_by_index(filepath, id_pattern=r'_(\d+)$'):
    """Loads a JSONL file into a dictionary keyed by an index extracted from a prompt ID.

    Args:
        filepath: The path to the JSONL file.
        id_pattern: The regex pattern to extract the index from the prompt ID.

    Returns:
        A dictionary mapping the extracted index to the corresponding JSON object.
    """
    data = {}
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                obj = json.loads(line)
                pid = obj.get("prompt_id") or obj.get("id", "")
                match = re.search(id_pattern, pid)
                if match:
                    idx = int(match.group(1))
                    data[idx] = obj
    except FileNotFoundError:
        logger.error(f"File not found: {filepath}")
    return data


def extract_boxed(answer_text):
    """Extracts the last boxed answer from a string.

    Args:
        answer_text: The string to extract the answer from.

    Returns:
        The extracted answer, or an empty string if not found.
    """
    return extract_last_boxed(answer_text) or ""


def normalize_answer(text, is_multichoice=None):
    """Normalizes an answer by stripping, lowercasing, and sorting multi-choice options.

    Args:
        text: The answer text to normalize.
        is_multichoice: A boolean indicating if the answer is multiple choice.

    Returns:
        The normalized answer string.
    """
    if not text:
        return ""
    stripped = strip_math_wrappers(text).strip()
    if is_multichoice or looks_multichoice(stripped):
        return normalize_multichoice(stripped)
    return canon_symbol(stripped)


def legacy_identity_normalize(text: str) -> str:
    """Applies legacy normalization for identical-model bookkeeping.

    This preserves spacing semantics.

    Args:
        text: The text to normalize.

    Returns:
        The normalized text.
    """
    if not text:
        return ""
    if looks_multichoice(text):
        return normalize_multichoice(text)
    return text.lower()


def to_identity_key(answer: str) -> Union[tuple[str, str], None]:
    """Converts an answer to a key for identity comparison.

    Args:
        answer: The answer string.

    Returns:
        A tuple of (mode, key), where mode is 'mc' or 'raw', or None.
    """
    # returns (mode, key) where mode is "mc" or "raw"; None if no usable answer
    if not isinstance(answer, str): 
        return None
    content = extract_last_boxed(answer)
    if not content:
        return None
    if looks_multichoice(content):
        key = normalize_multichoice(content)  # lowercase; split ';'; strip; sort; join with ';'
        return ("mc", key) if key else None
    # non-mc: use raw boxed content exactly
    return ("raw", content.strip())


def get_pred(row: dict) -> str:
    """Gets the prediction from a data row.

    It checks for 'pred' and falls back to 'response'.

    Args:
        row: A dictionary representing a row of data.

    Returns:
        The prediction string.
    """
    # Pass2 stores extracted answer in `pred`; fall back to `response` only if `pred` absent.
    return (row.get("pred") or row.get("response") or "").strip()


def to_identity_key_from_pred(pred: str):
    """Converts a prediction to a key for identity comparison.

    Args:
        pred: The prediction string.

    Returns:
        A tuple of (mode, key), where mode is 'mc' or 'raw', or None.
    """
    if not isinstance(pred, str) or not pred.strip():
        return None
    if looks_multichoice(pred):
        key = normalize_multichoice(pred)  # lower, split ';', strip, sort, join with ';'
        return ("mc", key) if key else None
    return ("raw", pred.strip())


def check_gold_valid(gold_text, prompt_text):
    """Checks if a gold answer is valid against the options in a prompt.

    Args:
        gold_text: The gold answer text.
        prompt_text: The prompt text.

    Returns:
        True if the gold answer is valid, False otherwise.
    """
    gold_letters = set(gold_text.replace(";", "").strip().lower())
    visible_letters = re.findall(r'\([a-z]\)', prompt_text)
    allowed = {letter.strip("()").lower() for letter in visible_letters}
    if not allowed:
        return True  # No options to check against
    return gold_letters.issubset(allowed)


def compare_predictions(gold_norm, pred_norm, gold_parsed, pred_parsed):
    """Compares a prediction to a gold standard using multiple methods.

    Args:
        gold_norm: The normalized gold answer.
        pred_norm: The normalized prediction.
        gold_parsed: The parsed numeric gold answer.
        pred_parsed: The parsed numeric prediction.

    Returns:
        A dictionary of comparison results.
    """
    string_equal = gold_norm == pred_norm
    mc_equal = False
    if looks_multichoice(gold_norm) and looks_multichoice(pred_norm):
        mc_equal = normalize_multichoice(gold_norm) == normalize_multichoice(pred_norm)

    numeric_equal_flag = False
    if gold_parsed is not None and pred_parsed is not None:
        numeric_equal_flag = numeric_equal(gold_parsed, pred_parsed, FLOAT_TOL)

    symbol_equal = canon_symbol(gold_norm) == canon_symbol(pred_norm)

    overall_equal = string_equal or mc_equal or numeric_equal_flag or symbol_equal
    return {
        "string_equal": string_equal,
        "mc_equal": mc_equal,
        "numeric_equal": numeric_equal_flag,
        "symbol_equal": symbol_equal,
        "overall": overall_equal,
    }


def load_gold(answers_path):
    """Loads gold standard answers from a JSONL file, keyed by index.

    Args:
        answers_path: The path to the answers JSONL file.

    Returns:
        A dictionary mapping index to the gold answer object.
    """
    data = {}
    try:
        with open(answers_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                obj = json.loads(line)
                idx = obj.get("index")
                if isinstance(idx, int):
                    data[idx] = obj
    except FileNotFoundError:
        logger.error(f"Gold file not found: {answers_path}")
    return data


def find_latest(defaults: list[str]) -> Union[str, None]:
    """Finds the most recently modified file from a list of glob patterns.

    Args:
        defaults: A list of glob patterns.

    Returns:
        The path to the latest file, or None if no files are found.
    """
    candidates = []
    for pat in defaults:
        matches = glob.glob(pat)
        for m in matches:
            try:
                candidates.append((os.path.getmtime(m), m))
            except FileNotFoundError:
                pass
    if not candidates:
        return None
    candidates.sort(reverse=True)
    return candidates[0][1]




def main():
    """The main entry point for the audit script."""
    parser = argparse.ArgumentParser(description="Suite audit utility (v2.1+)")
    parser.add_argument("--version", action="version", version=get_version())
    parser.add_argument(
        "--suite",
        default="hf_cmt",
        help="Suite name (default: hf_cmt)"
    )
    parser.add_argument(
        "--answers",
        type=str,
        help="Path to gold answers JSONL file (default: prompts/suites/{suite}.fixed.jsonl)"
    )
    parser.add_argument(
        "--out",
        type=str,
        help="Path to output summary JSON (default: runs/{suite}/{suite}_audit_summary.json)"
    )

    parser.add_argument("--syn", type=str, help="Path to SYNTRA responses JSONL")
    parser.add_argument("--base", type=str, help="Path to BASELINE responses JSONL")
    parser.add_argument(
      "--ident-metric",
      choices=["normalized","raw","legacy"],
      default="normalized",
      help="How to compute identical_model_predictions (default: normalized)"
    )

    args = parser.parse_args()
    suite = args.suite
    answers_path = args.answers or f"prompts/suites/{suite}.fixed.jsonl"
    output_path = args.out or f"runs/{suite}/{suite}_audit_summary.json"

    if not os.path.exists(answers_path):
        logger.warn(f"Provided answers file not found: {answers_path}")
        logger.info(f"Falling back to default prompts/suites/{suite}.fixed.jsonl")
        answers_path = f"prompts/suites/{suite}.fixed.jsonl"

    syn_path = args.syn or find_latest([
        f"runs/{suite}/syntra/{suite}_syntra.pass*.jsonl",
        f"runs/syntra/{suite}_syntra.pass*.jsonl",
        f"runs/{suite}_syntra.jsonl",
    ])
    base_path = args.base or find_latest([
        f"runs/{suite}/baseline/{suite}_baseline.pass*.jsonl",
        f"runs/baseline/{suite}_baseline.pass*.jsonl",
        f"runs/{suite}_baseline.jsonl",
    ])

    if not syn_path:
        logger.warn("No SYNTRA responses found. Set --syn to a file path.")
    if not base_path:
        logger.warn("No BASELINE responses found. Set --base to a file path.")

    logger.info(f"Using gold dataset: {answers_path}")
    logger.info(f"SYNTRA responses: {syn_path or 'NONE'}")
    logger.info(f"BASELINE responses: {base_path or 'NONE'}")
    logger.info(f"Writing audit summary to: {output_path}")
    gold = load_gold(answers_path)
    syntra = load_by_index(syn_path) if syn_path else {}
    baseline = load_by_index(base_path) if base_path else {}

    syn_data = list(syntra.values())
    base_data = list(baseline.values())
    unmapped = sum(1 for row in syn_data + base_data if get_type(row) == "OTHER")

    syn_raw = {}
    syn_norm = {}
    syn_legacy = {}
    base_raw = {}
    base_norm = {}
    base_legacy = {}

    syn_id = {}
    base_id = {}

    if not gold:
        logger.error("No gold data loaded.")
        return

    audit_records = []
    summary = {
        "total_items": len(gold),
        "valid_gold": 0,
        "gold_invalid": 0,
        "syntra_responses": len(syntra),
        "baseline_responses": len(baseline),
        "identical_model_predictions": 0,
        "false_positives": 0,  # pred != gold but comparison passes due to neutralization
        "false_negatives": 0,  # pred == gold after norm but fails without
        "ambiguous": 0  # no box or multiple issues
    }

    for idx in sorted(gold.keys()):
        rec = {"index": idx}

        gold_obj = gold[idx]
        gold_solution = gold_obj.get("solution", "")
        gold_prompt = gold_obj.get("prompt", "")

        rec["gold"] = extract_boxed(gold_solution)
        rec["gold_normalized"] = normalize_answer(rec["gold"])

        # Parse numeric if possible
        rec["gold_parsed"] = parse_numeric_list(rec["gold_normalized"])

        # Gold validity
        allowed_choices = allowed_choice_set_from_prompt(gold_prompt)
        if not allowed_choices:
            params = gold_obj.get("parameters", "")
            allowed_choices = allowed_choice_set_from_prompt(params)
        if not allowed_choices:
            # Default fallback for multi-choice problems
            allowed_choices = {"a", "b", "c", "d", "e", "f", "g", "h", "i", "j"}

        rec["gold_valid"] = gold_valid_against_allowed(rec["gold_normalized"], allowed_choices)
        if rec["gold_valid"]:
            summary["valid_gold"] += 1
        else:
            summary["gold_invalid"] += 1

        # Check for issues in gold
        issues = []
        if not rec["gold"]:
            issues.append("missing_box")
        if not rec["gold_valid"]:
            issues.append("gold_invalid_options")

        # Process syntra
        syntra_obj = syntra.get(idx)
        if syntra_obj:
            pred_str = get_pred(syntra_obj)
            if pred_str:
                rec["syntra"] = pred_str
                rec["syntra_normalized"] = normalize_answer(pred_str)
                rec["syntra_parsed"] = parse_numeric_list(rec["syntra_normalized"])
                syn_raw[idx] = pred_str
                syn_norm[idx] = rec["syntra_normalized"]
                syn_legacy[idx] = legacy_identity_normalize(pred_str)
                k = to_identity_key_from_pred(pred_str)
                if k is not None:
                    syn_id[idx] = k
            else:
                rec["syntra"] = rec["syntra_normalized"] = ""
                rec["syntra_parsed"] = None
                issues.append("syntra_empty_pred")
        else:
            rec["syntra"] = rec["syntra_normalized"] = ""
            rec["syntra_parsed"] = None
            issues.append("syntra_missing_response")

        # Process baseline
        baseline_obj = baseline.get(idx)
        if baseline_obj:
            pred_str = get_pred(baseline_obj)
            if pred_str:
                rec["baseline"] = pred_str
                rec["baseline_normalized"] = normalize_answer(pred_str)
                rec["baseline_parsed"] = parse_numeric_list(rec["baseline_normalized"])
                base_raw[idx] = pred_str
                base_norm[idx] = rec["baseline_normalized"]
                base_legacy[idx] = legacy_identity_normalize(pred_str)
                k = to_identity_key_from_pred(pred_str)
                if k is not None:
                    base_id[idx] = k
            else:
                rec["baseline"] = rec["baseline_normalized"] = ""
                rec["baseline_parsed"] = None
                issues.append("baseline_empty_pred")
        else:
            rec["baseline"] = rec["baseline_normalized"] = ""
            rec["baseline_parsed"] = None
            issues.append("baseline_missing_response")

        # Compare syntra to gold
        if rec["syntra_normalized"] and rec["gold_normalized"]:
            syn_eq = compare_predictions(rec["gold_normalized"], rec["syntra_normalized"], rec["gold_parsed"], rec["syntra_parsed"])
            rec["syntra_comparison"] = syn_eq
            if syn_eq["overall"] and not syn_eq.get("numeric_equal") and rec["gold_normalized"] != rec["syntra_normalized"]:
                summary["false_negatives"] += 1
        else:
            rec["syntra_comparison"] = {"overall": False}

        # Compare baseline
        if rec["baseline_normalized"] and rec["gold_normalized"]:
            base_eq = compare_predictions(rec["gold_normalized"], rec["baseline_normalized"], rec["gold_parsed"], rec["baseline_parsed"])
            rec["baseline_comparison"] = base_eq
        else:
            rec["baseline_comparison"] = {"overall": False}

        if issues:
            rec["issue"] = "; ".join(issues)
            if any(i in issues for i in ["missing_box", "malformed_latex"]):
                summary["ambiguous"] += 1
        else:
            rec["issue"] = "none"

        audit_records.append(rec)

    # Log skipped indices for identity
    skipped = []
    for idx in range(50):
        syn_obj = syntra.get(idx, {})
        base_obj = baseline.get(idx, {})
        if not get_pred(syn_obj) or not get_pred(base_obj):
            skipped.append(idx)
    if skipped:
        head = skipped[:10]
        logger.info(f"Skipped indices (empty_pred): {head}{'...' if len(skipped) > 10 else ''}")

    # Compute identical_model_predictions
    ident = 0
    if args.ident_metric == "normalized":
        shared = sorted(set(syn_id) & set(base_id))
        mc_compared = 0
        raw_compared = 0
        for i in shared:
            mode_syn, key_syn = syn_id[i]
            mode_base, key_base = base_id[i]
            if mode_syn == mode_base:
                if mode_syn == "mc":
                    mc_compared += 1
                else:
                    raw_compared += 1
                if key_syn == key_base:
                    ident += 1
        summary["shared_identity_indices"] = len(shared)
        summary["mc_identity_compared"] = mc_compared
        summary["raw_identity_compared"] = raw_compared
        summary["identity_by_mode"] = {"mc": mc_compared, "raw": raw_compared}

        summary["cross_mode_skipped"] = summary["shared_identity_indices"] - (
            summary["mc_identity_compared"] + summary["raw_identity_compared"]
        )

        logger.info(f"Identity metric: shared={len(shared)}, identical={ident}, mc_compared={mc_compared}, raw_compared={raw_compared}")
        logger.info(f"Cross-mode skipped: {summary['cross_mode_skipped']}")

        # Optional debug sample
        if shared:
            sample = shared[:5]
            logger.debug(f"sample identity pairs: {[(i, syn_id[i], base_id[i]) for i in sample]}")

        # Debug: if all identical and full shared, sample diffs to confirm logic
        if ident == len(shared) and len(shared) == 50:
            logger.debug("All identical in normalized mode. Sampling 5 potential diffs:")
            diff_samples = []
            for i in range(50):
                syn_obj = syntra.get(i, {})
                base_obj = baseline.get(i, {})
                pred_syn = get_pred(syn_obj)
                pred_base = get_pred(base_obj)
                if pred_syn and pred_base:
                    k_syn = to_identity_key_from_pred(pred_syn)
                    k_base = to_identity_key_from_pred(pred_base)
                    if k_syn != k_base and k_syn is not None and k_base is not None:
                        diff_samples.append(f"idx {i}: syn=({k_syn[0]}){k_syn[1]}, base=({k_base[0]}){k_base[1]}")
                if len(diff_samples) >= 5:
                    break
            if diff_samples:
                for d in diff_samples:
                    logger.debug(d)
            else:
                logger.debug("No differences found (models made identical normalized predictions).")
    else:
        shared = sorted(set(syn_raw.keys()) & set(base_raw.keys()))
        for i in shared:
            if args.ident_metric == "raw":
                if syn_raw[i] and base_raw[i] and syn_raw[i] == base_raw[i]:
                    ident += 1
            else:  # legacy
                if syn_legacy[i] and base_legacy[i] and syn_legacy[i] == base_legacy[i]:
                    ident += 1
        logger.info(f"Shared indices: {len(shared)}, ident_metric={args.ident_metric}, identical={ident}")
    summary["identical_model_predictions"] = ident
    summary["unmapped_items"] = unmapped

    # Write audit JSONL
    audit_detail_path = os.path.join("runs", suite, f"{suite}_audit.jsonl")
    os.makedirs(os.path.dirname(audit_detail_path), exist_ok=True)
    with open(audit_detail_path, "w", encoding="utf-8") as f:
        for rec in audit_records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    # Write summary
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    if summary["unmapped_items"] > 0:
        logger.info(f"[WARN] Unmapped items: {summary['unmapped_items']}")

    logger.info(f"Audit summary: {json.dumps(summary, indent=2)}")
    logger.info(f"Detailed audit written to: {audit_detail_path}")


if __name__ == "__main__":
    main()
