#!/usr/bin/env python3
"""
GraderAgent: Deterministic grading for HF-CMT v2.0.

Purpose: Grade model responses against gold answers with extraction, normalization (MC, numeric tol), and reporting. Handles gold errors gracefully.

Inputs:
- --responses: Input responses JSONL (required).
- --answers: Gold answers JSONL (required).
- --suite: Suite prompts for allowed choices (optional).
- --out: Output graded JSONL (required).
- --report: Markdown report path (optional).
- --normalize-choices: Enable MC normalization (flag).
- --float-tol: Numeric tolerance (default 0.02).
- --strict: Penalize gold errors (flag).
- --version: Show version and exit.

Outputs:
- pass2.jsonl: Graded records (pass, reason, normalized_pred/gold).
- fixed.report.md: Accuracy breakdown, gold errors, near-misses, disagreements.

Example CLI:
    python grade_official_cmt.py --responses runs/hf_cmt/syntra/hf_cmt_syntra.jsonl --answers prompts/suites/hf_cmt.fixed.jsonl --suite prompts/suites/hf_cmt.fixed.jsonl --out runs/hf_cmt/syntra/hf_cmt_syntra.pass2.jsonl --report runs/hf_cmt/syntra/hf_cmt_syntra.fixed.report.md --normalize-choices --float-tol 0.02
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import os
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

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
except ImportError:  # pragma: no cover - fallback when executed as standalone script
    CURRENT_DIR = Path(__file__).resolve().parent
    PARENT_DIR = CURRENT_DIR.parent
    for candidate in (PARENT_DIR, CURRENT_DIR):
        candidate_str = str(candidate)
        if candidate_str not in sys.path:
            sys.path.insert(0, candidate_str)
    from common import logger, get_version  # type: ignore

VERSION_PATH = Path(__file__).resolve().parent / "VERSION"


ACRONYM_LEGEND_MD = """\
---
### Legend of Acronyms
- **HF** — Hartree-Fock / Mean-Field Theory
- **ED** — Exact Diagonalization / Band-Structure / Finite-Cluster Analysis
- **DMRG** — Density Matrix Renormalization Group
- **PEPS** — Projected Entangled Pair States
- **QMC** — Quantum Monte Carlo
- **VMC** — Variational Monte Carlo
- **SM** — Statistical Mechanics / Field Theory / Classical or Continuum Systems
"""


def _ensure_legend(md_text: str) -> str:
    """Ensures the acronym legend is present in the markdown text.

    Args:
        md_text: The markdown text to check.

    Returns:
        The markdown text with the legend appended if it was missing.
    """
    if "### Legend of Acronyms" in md_text:
        return md_text
    return md_text.rstrip() + "\n\n" + ACRONYM_LEGEND_MD + "\n"


# Removed duplicate; use from logger


def iso_now() -> str:
    """Returns the current UTC date and time in ISO 8601 format.

    Returns:
        The current UTC date and time as a string.
    """
    return datetime.now(timezone.utc).isoformat()


def load_answers(path: str) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, str]]:
    """Loads answers and prompts from a JSONL file.

    Args:
        path: The path to the JSONL file.

    Returns:
        A tuple containing two dictionaries:
        - A dictionary mapping prompt IDs to answer details.
        - A dictionary mapping prompt IDs to prompt text.
    """
    answers: Dict[str, Dict[str, Any]] = {}
    prompts: Dict[str, str] = {}
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            idx = obj.get("index", 0)
            typ = (obj.get("type") or "hf").lower()
            pid = f"hf_{typ}_{idx:03d}"
            answers[pid] = {
                "solution": obj.get("solution", ""),
                "type": obj.get("type"),
                "prompt": obj.get("prompt", ""),
                "parameters": obj.get("parameters", ""),
            }
            if isinstance(obj.get("prompt"), str):
                prompts[pid] = obj["prompt"]
    return answers, prompts


def load_suite_prompts(path: str) -> Dict[str, str]:
    """Loads prompts from a suite's JSONL file.

    Args:
        path: The path to the JSONL file.

    Returns:
        A dictionary mapping prompt IDs to prompt text.
    """
    prompts: Dict[str, str] = {}
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            idx = obj.get("index", 0)
            typ = (obj.get("type") or "hf").lower()
            pid = f"hf_{typ}_{idx:03d}"
            prompt = obj.get("prompt")
            if isinstance(prompt, str):
                prompts[pid] = prompt
    return prompts


def load_latest_responses(path: str) -> Dict[str, Dict[str, Any]]:
    """Loads the latest response for each prompt ID from a JSONL file.

    Args:
        path: The path to the JSONL file containing responses.

    Returns:
        A dictionary mapping each prompt ID to its latest response object.
    """
    grouped: Dict[str, List[Tuple[str, Dict[str, Any]]]] = defaultdict(list)
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            pid = obj.get("prompt_id") or obj.get("id")
            if not isinstance(pid, str):
                continue
            timestamp = obj.get("timestamp_iso") or obj.get("timestamp") or ""
            grouped[pid].append((timestamp, obj))
    latest: Dict[str, Dict[str, Any]] = {}
    for pid, entries in grouped.items():
        entries.sort(key=lambda item: item[0], reverse=True)
        latest[pid] = entries[0][1]
    return latest


def extract_idx(pid: str) -> int | None:
    """Extracts the index number from a prompt ID string.

    Args:
        pid: The prompt ID string (e.g., "hf_type_001").

    Returns:
        The extracted index as an integer, or None if not found.
    """
    match = re.search(r"_(\d+)$", pid or "")
    return int(match.group(1)) if match else None


def generate_report(
    path: str,
    overall_pass: int,
    overall_total: int,
    type_totals: Dict[str, int],
    type_passes: Dict[str, int],
    gold_error_items: List[Dict[str, Any]],
    near_miss_items: List[Dict[str, Any]],
    disagreements: List[Dict[str, Any]],
) -> None:
    """Generates a markdown report summarizing the grading results.

    Args:
        path: The path to the output markdown file.
        overall_pass: The total number of passed responses.
        overall_total: The total number of graded responses.
        type_totals: A dictionary mapping problem types to their total counts.
        type_passes: A dictionary mapping problem types to their pass counts.
        gold_error_items: A list of items with gold standard errors.
        near_miss_items: A list of items that were numeric near-misses.
        disagreements: A list of items where the prediction and gold standard differed.
    """
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("# Hf-CMT Grader Report\n\n")
        if overall_total:
            pct = overall_pass / overall_total * 100.0
            fh.write(f"Overall accuracy: {overall_pass}/{overall_total} ({pct:.1f}%)\n\n")
        else:
            fh.write("Overall accuracy: n/a\n\n")

        fh.write("## Breakdown by type\n\n")
        fh.write("| Type | Pass | Total | Pct |\n")
        fh.write("|---|---|---|---|\n")
        for atype in sorted(type_totals):
            total = type_totals[atype]
            passed = type_passes.get(atype, 0)
            pct = (passed / total * 100.0) if total else 0.0
            fh.write(f"| {atype} | {passed} | {total} | {pct:.1f}% |\n")
        fh.write("\n")

        fh.write(f"## Gold errors ({len(gold_error_items)})\n\n")
        for item in gold_error_items:
            allowed = sorted(item.get("allowed") or [])
            fh.write(
                f"- {item['id']} (idx {item.get('idx', 'n/a')}): gold='{item['gold']}', allowed={allowed}\n"
            )
        fh.write("\n")

        fh.write(f"## Near-miss numerics ({len(near_miss_items)})\n\n")
        for item in near_miss_items:
            fh.write(
                f"- {item['id']}: pred={item['pred']}, gold={item['gold']}, max_diff={item['max_diff']:.6f}\n"
            )
        fh.write("\n")

        failing = [d for d in disagreements if not d.get("pass", False)]
        top = failing[:5] if failing else disagreements[:5]
        fh.write(f"## Top {len(top)} disagreements\n\n")
        for idx, diss in enumerate(top, 1):
            fh.write(
                f"{idx}. {diss['id']}: pred='{diss['pred']}', gold='{diss['gold']}', reason={diss['reason']}\n"
            )
        fh.write(ACRONYM_LEGEND_MD)


def main() -> None:
    """The main entry point for the HF-CMT grader script."""
    parser = argparse.ArgumentParser(description="HF-CMT Grader")
    parser.add_argument("--version", action="version", version=get_version())
    parser.add_argument(
        "--responses",
        required=True,
        help="Run results JSONL (e.g., runs/hf_cmt_syntra.jsonl)",
    )
    parser.add_argument(
        "--answers",
        required=True,
        help="Answer key JSONL (prompt_id, solution, etc.)",
    )
    parser.add_argument(
        "--suite",
        help="Suite prompts JSONL for allowed choices sanity check",
    )
    parser.add_argument("--out", required=True, help="Output JSONL with graded records")
    parser.add_argument("--report", help="Markdown report file")
    parser.add_argument(
        "--normalize-choices",
        action="store_true",
        help="Enable multi-choice normalization",
    )
    parser.add_argument(
        "--float-tol",
        type=float,
        default=0.02,
        help="Numeric tolerance (default 0.02)",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Penalize even if gold_error",
    )
    args = parser.parse_args()

    type_map = None
    if args.suite:
        tmap_path = "prompts/suites/hf_cmt.type_map.json"
        if os.path.exists(tmap_path):
            with open(tmap_path,"r",encoding="utf-8") as f:
                type_map = {int(k):v for k,v in json.load(f).items()}

    try:
        answers, answers_prompts = load_answers(args.answers)
    except FileNotFoundError:
        logger.error(f"answers file not found: {args.answers}")
        sys.exit(1)

    suite_prompts = {}
    if args.suite:
        try:
            suite_prompts = load_suite_prompts(args.suite)
        except FileNotFoundError:
            logger.error(f"suite file not found: {args.suite}")
            sys.exit(1)

    try:
        responses = load_latest_responses(args.responses)
    except FileNotFoundError:
        logger.error(f"responses file not found: {args.responses}")
        sys.exit(1)

    records: List[Dict[str, Any]] = []
    gold_error_items: List[Dict[str, Any]] = []
    near_miss_items: List[Dict[str, Any]] = []
    disagreements: List[Dict[str, Any]] = []

    overall_total = 0
    overall_pass = 0
    type_totals: Dict[str, int] = {}
    type_passes: Dict[str, int] = {}

    with open(args.out, "w", encoding="utf-8") as out_fh:
        for pid, ans_entry in answers.items():
            solution_text = ans_entry.get("solution", "")
            atype = ans_entry.get("type")
            prompt_text = suite_prompts.get(pid) or answers_prompts.get(pid) or ""
            parameters_text = ans_entry.get("parameters", "")

            idx = extract_idx(pid)
            if type_map and idx is not None:
                resolved = type_map.get(idx, atype)
                if resolved != "OTHER":
                    atype = resolved

            if isinstance(atype, str):
                type_totals[atype] = type_totals.get(atype, 0) + 1
            response_obj = responses.get(pid)
            if response_obj is None:
                record = {
                    "id": pid,
                    "idx": idx,
                    "pred": None,
                    "gold": strip_math_wrappers(extract_last_boxed(solution_text) or ""),
                    "pass": False,
                    "gold_error": False,
                    "reason": "no-response",
                    "normalized_pred": None,
                    "normalized_gold": None,
                    "model": None,
                    "timestamp_iso": iso_now(),
                }
                record["type"] = "OTHER"
                out_fh.write(json.dumps(record, ensure_ascii=False) + "\n")
                records.append(record)
                overall_total += 1
                disagreements.append(
                    {
                        "id": pid,
                        "pred": None,
                        "gold": record["gold"],
                        "reason": "no-response",
                        "pass": False,
                    }
                )
                continue

            response_text = response_obj.get("response") or response_obj.get("content") or ""
            model = response_obj.get("model")

            gold_raw = extract_last_boxed(solution_text) or ""
            gold = strip_math_wrappers(gold_raw)

            pred_raw = extract_last_boxed(response_text) or ""
            pred = strip_math_wrappers(pred_raw)

            normalized_pred = None
            normalized_gold = None
            passed = False
            reason = "UNKNOWN"
            gold_error = False

            allowed = allowed_choice_set_from_prompt(prompt_text)
            if allowed is None and parameters_text:
                allowed = allowed_choice_set_from_prompt(parameters_text)

            if allowed:
                normalized_gold_for_check = gold
                if looks_multichoice(normalized_gold_for_check):
                    normalized_gold_for_check = normalize_multichoice(normalized_gold_for_check)
                gold_valid = gold_valid_against_allowed(normalized_gold_for_check, allowed)
                if not gold_valid:
                    gold_error = True
                    if args.strict:
                        reason = "GOLD_INVALID_OPTIONS"
                    else:
                        passed = True
                        reason = "GOLD_INVALID_OPTIONS"

            if not gold_error:
                if args.normalize_choices and looks_multichoice(pred) and looks_multichoice(gold):
                    normalized_pred = normalize_multichoice(pred)
                    normalized_gold = normalize_multichoice(gold)
                    passed = normalized_pred == normalized_gold
                    reason = "MC_ORDER_ONLY" if passed else "MC_DIFF"
                else:
                    pred_parsed = parse_numeric_list(pred)
                    gold_parsed = parse_numeric_list(gold)
                    if pred_parsed is not None and gold_parsed is not None:
                        passed = numeric_equal(pred_parsed, gold_parsed, args.float_tol)
                        reason = (
                            f"NUMERIC_TOL={args.float_tol}"
                            if passed
                            else f"NUMERIC_DIFF tol={args.float_tol}"
                        )
                        if not passed:
                            diffs: List[float] = []
                            for x, y in zip(pred_parsed, gold_parsed):
                                if isinstance(x, (int, float)) and isinstance(y, (int, float)):
                                    diffs.append(abs(float(x) - float(y)))
                                elif isinstance(x, tuple) and isinstance(y, tuple) and len(x) == len(y):
                                    diffs.extend(abs(float(a) - float(b)) for a, b in zip(x, y))
                            if diffs:
                                max_diff = max(diffs)
                                if 0 < max_diff <= args.float_tol * 10:
                                    near_miss_items.append(
                                        {
                                            "id": pid,
                                            "pred": str(pred_parsed),
                                            "gold": str(gold_parsed),
                                            "max_diff": max_diff,
                                        }
                                    )
                    else:
                        pred_canon = canon_symbol(pred)
                        gold_canon = canon_symbol(gold)
                        if pred_canon and gold_canon and pred_canon == gold_canon:
                            passed = True
                            reason = "CANON_SYMBOL"
                        else:
                            passed = pred.strip().lower() == gold.strip().lower()
                            reason = "EXACT_STRING" if passed else "STR_DIFF"

            if gold_error:
                gold_error_items.append(
                    {"id": pid, "gold": gold, "allowed": allowed, "idx": idx}
                )

            counted = (not gold_error) or args.strict
            if counted:
                overall_total += 1
                if passed:
                    overall_pass += 1
                    if isinstance(atype, str):
                        type_passes[atype] = type_passes.get(atype, 0) + 1
                disagreements.append(
                    {
                        "id": pid,
                        "pred": pred,
                        "gold": gold,
                        "reason": reason,
                        "pass": passed,
                    }
                )

            record = {
                "id": pid,
                "idx": idx,
                "pred": pred if pred else None,
                "gold": gold if gold else None,
                "pass": passed,
                "gold_error": gold_error,
                "reason": reason,
                "normalized_pred": normalized_pred,
                "normalized_gold": normalized_gold,
                "model": model,
                "timestamp_iso": iso_now(),
            }
            record["type"] = atype if isinstance(atype, str) else (type_map.get(idx, "OTHER") if type_map and idx is not None else "OTHER")
            out_fh.write(json.dumps(record, ensure_ascii=False) + "\n")
            records.append(record)

        # (Emission of stray records without answer key has been removed.)

    logger.info(f"Wrote {len(records)} graded records → {args.out}")
    if overall_total:
        overall_pct = (overall_pass / overall_total) * 100.0
        summary = f"Overall Pass@1 {overall_pass}/{overall_total} {overall_pct:.1f}%"
    else:
        summary = "Overall Pass@1 n/a"

    segments = []
    for tname in sorted(type_totals):
        total = type_totals[tname]
        passed = type_passes.get(tname, 0)
        pct = (passed / total) * 100.0 if total else 0.0
        segments.append(f"{tname} {passed}/{total} {pct:.1f}%")
    if segments:
        summary = f"{summary} | " + " | ".join(segments)
    logger.info(summary)

    if args.report:
        generate_report(
            args.report,
            overall_pass,
            overall_total,
            type_totals,
            type_passes,
            gold_error_items,
            near_miss_items,
            disagreements,
        )
        logger.info(f"Report generated: {args.report}")


if __name__ == "__main__":
    main()
