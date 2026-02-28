#!/usr/bin/env python3
"""
ARC Response Evaluator
Parses model responses to extract letter choices (A-D) and computes pass@1 accuracy.

Usage:
    python eval_arc.py \
        --responses runs/arc_challenge/arc_challenge_validation_responses.jsonl \
        --reference runs/arc_challenge/arc_challenge_validation_reference.jsonl \
        --out runs/arc_challenge/arc_challenge_validation_pass1.jsonl \
        --report runs/arc_challenge/arc_challenge_validation_eval.report.md
"""

import os
import sys
import argparse
import json
import re
from typing import Optional, Dict, Any, List
from decimal import Decimal
from statistics import mean, stdev

# Add parent directories to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

try:
    from Tools.common.logger import get_logger
    logger = get_logger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)
    logging.basicConfig(level=logging.INFO)

from Benchmarks.jsonl_utils import iter_jsonl

def parse_letter(text: str) -> Optional[str]:
    """
    Extract letter choice (A-E) from model response.

    Handles various formats:
    - Simple: "C", "A", "D"
    - With context: "Answer: C", "The answer is C"
    - With explanation: "C) moon is correct because..."
    - With punctuation: "C.", "(C)", "c"
    - In sentence: "I choose C as the answer"

    Args:
        text: Model response text

    Returns:
        Single letter A-E, or None if no valid letter found
    """
    if not text or not isinstance(text, str):
        return None

    # Normalize
    text = text.strip()

    # Pattern 1: Standalone letter (possibly with punctuation)
    # Match: "C", "C.", "(C)", "[C]", "C)"
    match = re.search(r'^[\(\[]?([A-E])[\)\]\.,:;]?\s*$', text, re.IGNORECASE)
    if match:
        return match.group(1).upper()

    # Pattern 2: "Answer: C" or "The answer is C"
    match = re.search(r'\banswer\s*(?:is\s*|:|=\s*)?([A-E])\b', text, re.IGNORECASE)
    if match:
        return match.group(1).upper()

    # Pattern 3: Letter at start with optional ")" (choice format)
    # Match: "C) moon orbits a planet", "C - moon"
    match = re.search(r'^([A-E])[\)\-\:\.]', text, re.IGNORECASE)
    if match:
        return match.group(1).upper()

    # Pattern 4: "I choose C", "select C", "pick C"
    match = re.search(r'\b(?:choose|select|pick)\s+([A-E])\b', text, re.IGNORECASE)
    if match:
        return match.group(1).upper()

    # Pattern 5: Letter in common answer phrases
    # Match: "C is correct", "C is the answer", "option C"
    match = re.search(r'\b([A-E])\s+is\s+(?:correct|the\s+answer)', text, re.IGNORECASE)
    if match:
        return match.group(1).upper()

    match = re.search(r'\boption\s+([A-E])\b', text, re.IGNORECASE)
    if match:
        return match.group(1).upper()

    # Pattern 6: First standalone capital letter A-E in text
    match = re.search(r'\b([A-E])\b', text)
    if match:
        return match.group(1).upper()

    # Pattern 7: Case-insensitive fallback - any A-E letter
    match = re.search(r'([A-E])', text, re.IGNORECASE)
    if match:
        return match.group(1).upper()

    return None


def evaluate_arc(
    responses_path: str,
    reference_path: str,
    output_path: Optional[str] = None,
    report_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Evaluate ARC responses against reference answers.

    Args:
        responses_path: Path to model responses JSONL
        reference_path: Path to reference answers JSONL (from format_arc.py)
        output_path: Optional path to save pass1.jsonl
        report_path: Optional path to save evaluation report

    Returns:
        Dictionary with metrics:
        {
            "pass1": float (0.0-1.0),
            "n": int,
            "n_correct": int,
            "n_invalid": int,
            "latency_ms_mean": float,
            "latency_ms_std": float
        }
    """
    # Load reference answers
    logger.info(f"Loading reference answers from {reference_path}")
    reference = {}
    for rec in iter_jsonl(reference_path):
        reference[rec["id"]] = rec

    logger.info(f"Loaded {len(reference)} reference answers")

    # Load responses
    logger.info(f"Loading responses from {responses_path}")
    responses = list(iter_jsonl(responses_path))

    logger.info(f"Loaded {len(responses)} responses")

    # Evaluate each response
    results = []
    n_correct = 0
    n_invalid = 0
    latencies = []

    for resp in responses:
        prompt_id = resp.get("prompt_id") or resp.get("id")
        response_text = resp.get("response", "")
        latency_ms = resp.get("latency_ms", 0)

        # Get reference
        ref = reference.get(prompt_id)
        if not ref:
            logger.warning(f"No reference found for {prompt_id}")
            continue

        gold = ref["gold"]

        # Parse model response
        pred = parse_letter(response_text)

        # Determine pass/fail
        is_correct = False
        reason = ""

        if pred is None:
            reason = "invalid_parse"
            n_invalid += 1
        elif pred == gold:
            is_correct = True
            n_correct += 1
            reason = "correct"
        else:
            reason = f"incorrect (got {pred}, expected {gold})"

        # Store result
        result = {
            "id": prompt_id,
            "pred_letter": pred,
            "gold": gold,
            "pass": is_correct,
            "reason": reason,
            "latency_ms": latency_ms,
            "response_text": response_text[:200]  # First 200 chars for debugging
        }
        results.append(result)

        if latency_ms > 0:
            latencies.append(latency_ms)

    # Compute metrics
    n_total = len(results)
    pass1 = n_correct / n_total if n_total > 0 else 0.0
    latency_mean = mean(latencies) if latencies else 0.0
    latency_std = stdev(latencies) if len(latencies) > 1 else 0.0

    metrics = {
        "pass1": pass1,
        "n": n_total,
        "n_correct": n_correct,
        "n_invalid": n_invalid,
        "latency_ms_mean": latency_mean,
        "latency_ms_std": latency_std
    }

    logger.info(f"Evaluation complete: {n_correct}/{n_total} correct ({pass1*100:.1f}%), {n_invalid} invalid")

    # Save pass1.jsonl
    if output_path:
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            for result in results:
                f.write(json.dumps(result, ensure_ascii=False) + "\n")
        logger.info(f"Saved pass1 results to {output_path}")

    # Save report
    if report_path:
        generate_report(metrics, results, report_path)

    return metrics


def generate_report(metrics: Dict[str, Any], results: List[Dict[str, Any]], report_path: str):
    """Generate markdown evaluation report."""
    os.makedirs(os.path.dirname(report_path) or ".", exist_ok=True)

    with open(report_path, "w", encoding="utf-8") as f:
        f.write("# ARC Evaluation Report\n\n")

        # Summary
        f.write("## Summary\n\n")
        f.write(f"- **Pass@1 Accuracy**: {metrics['pass1']*100:.2f}%\n")
        f.write(f"- **Total Questions**: {metrics['n']}\n")
        f.write(f"- **Correct**: {metrics['n_correct']}\n")
        f.write(f"- **Incorrect**: {metrics['n'] - metrics['n_correct'] - metrics['n_invalid']}\n")
        f.write(f"- **Invalid Parse**: {metrics['n_invalid']}\n")
        f.write(f"- **Latency (mean)**: {metrics['latency_ms_mean']:.1f} ms\n")
        f.write(f"- **Latency (std)**: {metrics['latency_ms_std']:.1f} ms\n\n")

        # Errors
        f.write("## Errors\n\n")
        errors = [r for r in results if not r["pass"]]
        if errors:
            f.write(f"Found {len(errors)} errors:\n\n")
            for err in errors[:20]:  # Show first 20
                f.write(f"### {err['id']}\n")
                f.write(f"- **Gold**: {err['gold']}\n")
                f.write(f"- **Predicted**: {err['pred_letter'] or 'N/A'}\n")
                f.write(f"- **Reason**: {err['reason']}\n")
                f.write(f"- **Response**: {err['response_text']}\n\n")
        else:
            f.write("No errors!\n\n")

        # Invalid parses
        if metrics['n_invalid'] > 0:
            f.write("## Invalid Parses\n\n")
            invalid = [r for r in results if r["pred_letter"] is None]
            for inv in invalid[:10]:  # Show first 10
                f.write(f"### {inv['id']}\n")
                f.write(f"- **Gold**: {inv['gold']}\n")
                f.write(f"- **Response**: {inv['response_text']}\n\n")

    logger.info(f"Saved evaluation report to {report_path}")


def main():
    """CLI interface for ARC evaluator."""
    parser = argparse.ArgumentParser(
        description="Evaluate ARC model responses and compute pass@1 accuracy"
    )
    parser.add_argument(
        "--responses",
        required=True,
        help="Path to model responses JSONL"
    )
    parser.add_argument(
        "--reference",
        required=True,
        help="Path to reference answers JSONL (from format_arc.py)"
    )
    parser.add_argument(
        "--out",
        required=True,
        help="Output path for pass1.jsonl"
    )
    parser.add_argument(
        "--report",
        default=None,
        help="Output path for evaluation report (markdown)"
    )

    args = parser.parse_args()

    # Run evaluation
    metrics = evaluate_arc(
        responses_path=args.responses,
        reference_path=args.reference,
        output_path=args.out,
        report_path=args.report
    )

    # Print summary
    print(f"\n=== ARC Evaluation Results ===")
    print(f"Pass@1 Accuracy: {metrics['pass1']*100:.2f}%")
    print(f"Correct: {metrics['n_correct']}/{metrics['n']}")
    print(f"Invalid: {metrics['n_invalid']}")
    print(f"Latency: {metrics['latency_ms_mean']:.1f} ± {metrics['latency_ms_std']:.1f} ms")

    if args.out:
        print(f"\nPass1 results: {args.out}")
    if args.report:
        print(f"Report: {args.report}")


if __name__ == "__main__":
    main()
