#!/usr/bin/env python3
"""
GSM8K Response Evaluator
Parses model responses to extract final numeric answers and computes pass@1 accuracy.

Usage:
    python eval_gsm8k.py \
        --responses runs/gsm8k_test/gsm8k_test_responses.jsonl \
        --reference runs/gsm8k_test/gsm8k_test_reference.jsonl \
        --out runs/gsm8k_test/gsm8k_test_pass1.jsonl \
        --report runs/gsm8k_test/gsm8k_test_eval.report.md
"""

import os
import sys
import argparse
import json
import re
from typing import Optional, Dict, Any, List
from decimal import Decimal, InvalidOperation
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

def extract_numeric_answer(text: str) -> Optional[Decimal]:
    """
    Extract the final numeric answer from model response text.

    Handles various formats:
    - Simple numbers: "42", "3.14", "100"
    - With commas: "1,200", "1,000,000"
    - With currency: "$1200", "€50"
    - With units: "12 meters", "5 kg"
    - With punctuation: "42.", "(42)", "[42]"
    - In text: "The answer is 42", "Result: 42"
    - Fractions: "1/2", "3.5"
    - Scientific: "1.23e4"

    Args:
        text: Model response text

    Returns:
        Decimal number, or None if no valid number found
    """
    if not text or not isinstance(text, str):
        return None

    # Normalize
    text = text.strip()

    # Pattern 1: Look for boxed answers (LaTeX style)
    boxed_match = re.search(r'\\boxed\{([^}]+)\}', text)
    if boxed_match:
        boxed_content = boxed_match.group(1).strip()
        # Try to extract number from boxed content
        num_match = re.search(r'(\d+(?:,\d{3})*(?:\.\d+)?)', boxed_content.replace(',', ''))
        if num_match:
            try:
                return Decimal(num_match.group(1).replace(',', ''))
            except InvalidOperation:
                pass

    # Pattern 2: Look for final answer markers
    # "Final Answer: 42", "#### 42", "Answer: 42"
    final_patterns = [
        r'(?:final answer|####|answer)\s*[:=]?\s*([^\n]+)',
        r'So[^\n]*?(\d+(?:,\d{3})*(?:\.\d+)?)',
        r'Therefore[^\n]*?(\d+(?:,\d{3})*(?:\.\d+)?)',
        r'Total[^\n]*?(\d+(?:,\d{3})*(?:\.\d+)?)',
    ]

    for pattern in final_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            candidate = match.group(1).strip()
            # Clean up the candidate
            candidate = re.sub(r'[^\d.,]', '', candidate)
            try:
                return Decimal(candidate.replace(',', ''))
            except InvalidOperation:
                continue

    # Pattern 3: Last standalone number in the text (fallback)
    # Find numbers that are standalone (word boundaries or at end)
    numbers = re.findall(r'\b(\d+(?:,\d{3})*(?:\.\d+)?)\b', text)
    if numbers:
        try:
            return Decimal(numbers[-1].replace(',', ''))
        except InvalidOperation:
            pass

    # Pattern 4: Simple number at the end (if no standalone numbers found)
    # Only match if the number is at the end of the line with no following letters
    lines = text.split('\n')
    if lines:
        last_line = lines[-1].strip()
        num_match = re.search(r'(\d+(?:,\d{3})*(?:\.\d+)?)(?:\s|$)', last_line)
        if num_match and not re.search(r'\d+\w', last_line):  # No digits followed by letters
            try:
                return Decimal(num_match.group(1).replace(',', ''))
            except InvalidOperation:
                pass

    return None


def evaluate_gsm8k(
    responses_path: str,
    reference_path: str,
    output_path: Optional[str] = None,
    report_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Evaluate GSM8K responses against reference answers.

    Args:
        responses_path: Path to model responses JSONL
        reference_path: Path to reference answers JSONL (from format_gsm8k.py)
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

        gold_str = ref["gold"]
        try:
            gold = Decimal(gold_str.replace(',', ''))
        except (InvalidOperation, AttributeError):
            logger.warning(f"Invalid gold answer for {prompt_id}: {gold_str}")
            continue

        # Parse model response
        pred = extract_numeric_answer(response_text)

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
            "pred": str(pred) if pred is not None else None,
            "gold": str(gold),
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
        f.write("# GSM8K Evaluation Report\n\n")

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
                f.write(f"- **Predicted**: {err['pred'] or 'N/A'}\n")
                f.write(f"- **Reason**: {err['reason']}\n")
                f.write(f"- **Response**: {err['response_text']}\n\n")
        else:
            f.write("No errors!\n\n")

        # Invalid parses
        if metrics['n_invalid'] > 0:
            f.write("## Invalid Parses\n\n")
            invalid = [r for r in results if r["pred"] is None]
            for inv in invalid[:10]:  # Show first 10
                f.write(f"### {inv['id']}\n")
                f.write(f"- **Gold**: {inv['gold']}\n")
                f.write(f"- **Response**: {inv['response_text']}\n\n")

    logger.info(f"Saved evaluation report to {report_path}")


def main():
    """CLI interface for GSM8K evaluator."""
    parser = argparse.ArgumentParser(
        description="Evaluate GSM8K model responses and compute pass@1 accuracy"
    )
    parser.add_argument(
        "--responses",
        required=True,
        help="Path to model responses JSONL"
    )
    parser.add_argument(
        "--reference",
        required=True,
        help="Path to reference answers JSONL (from format_gsm8k.py)"
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
    metrics = evaluate_gsm8k(
        responses_path=args.responses,
        reference_path=args.reference,
        output_path=args.out,
        report_path=args.report
    )

    # Print summary
    print(f"\n=== GSM8K Evaluation Results ===")
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
