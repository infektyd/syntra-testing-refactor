#!/usr/bin/env python3
"""
GSM8K Prompt Formatter
Converts GSM8K dataset records to SYNTRA-compatible JSONL prompts.

Outputs:
  1. Runner format (Swift-compatible):
     {"id": "...", "content": "Solve the problem. Return only the final number.\n\nQuestion: <q>\nAnswer:", "metadata": {...}}

  2. Reference format (grading):
     {"id": "...", "type": "GSM8K_FREE", "input": "...", "gold": "<number>", "meta": {...}}

Usage:
    python format_gsm8k.py --split test --output-runner prompts.jsonl --output-reference answers.jsonl
"""

import os
import sys
import json
import argparse
import re
from typing import List, Dict, Any, Optional

# Add parent directories to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from Benchmarks.GSM8K.bench.datasets_gsm8k import load_gsm8k

try:
    from Tools.common.logger import get_logger
    logger = get_logger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)
    logging.basicConfig(level=logging.INFO)


def extract_final_answer(answer_text: str) -> str:
    """
    Extract the final numeric answer from GSM8K answer text.

    GSM8K answers have format: "reasoning... #### final_number"

    Args:
        answer_text: Full answer text with reasoning

    Returns:
        Final numeric string (e.g., "72", "30")
    """
    # Look for #### followed by number
    match = re.search(r'####\s*([^\n]+)', answer_text)
    if match:
        return match.group(1).strip()

    # Fallback: look for final number at the end
    lines = answer_text.strip().split('\n')
    if lines:
        last_line = lines[-1].strip()
        # Try to extract number from last line
        match = re.search(r'(\d+(?:\.\d+)?)', last_line)
        if match:
            return match.group(1)

    # Last resort: return the whole answer (shouldn't happen with proper GSM8K data)
    return answer_text.strip()


def format_question_text(record: Dict[str, Any], include_fewshot: bool = False) -> str:
    """
    Format GSM8K record as a structured question with optional few-shot examples.

    Example output:
        Solve the problem. Return only the final number.

        Question: Natalia sold clips to 48 of her friends in April...
        Answer: 72

        Question: [current question]
        Answer:

    Args:
        record: GSM8K record with question and answer
        include_fewshot: Whether to include few-shot examples

    Returns:
        Formatted question text
    """
    base_prompt = "Solve the problem. Return only the final number.\n\n"

    if include_fewshot:
        # Load few-shot examples
        fewshot_path = os.path.join(os.path.dirname(__file__), "..", "stubs", "fewshot.txt")
        try:
            with open(fewshot_path, "r", encoding="utf-8") as f:
                fewshot_text = f.read().strip()
            base_prompt += fewshot_text + "\n\n"
        except FileNotFoundError:
            logger.warning(f"Few-shot file not found: {fewshot_path}")
        except Exception as e:
            logger.warning(f"Error loading few-shot examples: {e}")

    # Add current question
    base_prompt += f"Question: {record['question']}\nAnswer:"

    return base_prompt


def format_gsm8k_for_runner(record: Dict[str, Any], include_fewshot: bool = False) -> Dict[str, Any]:
    """
    Format GSM8K record for SYNTRA Swift runner.

    Swift runner expects: {"id": str, "content": str, "metadata": dict}

    Args:
        record: Normalized GSM8K record
        include_fewshot: Whether to include few-shot examples

    Returns:
        Runner-compatible format
    """
    # Extract final answer for metadata
    final_answer = extract_final_answer(record["answer"])

    return {
        "id": record["id"],
        "content": format_question_text(record, include_fewshot),
        "metadata": {
            "type": "GSM8K_FREE",
            "gold": final_answer,
            "split": record["split"],
            "source": "openai/gsm8k"
        }
    }


def format_gsm8k_for_reference(record: Dict[str, Any]) -> Dict[str, Any]:
    """
    Format GSM8K record as reference answers for grading.

    Grading tools expect explicit fields for validation.

    Args:
        record: Normalized GSM8K record

    Returns:
        Reference format with explicit gold answer
    """
    final_answer = extract_final_answer(record["answer"])

    return {
        "id": record["id"],
        "type": "GSM8K_FREE",
        "input": format_question_text(record, include_fewshot=False),
        "gold": final_answer,
        "meta": {
            "split": record["split"],
            "source": "openai/gsm8k",
            "question": record["question"],
            "full_answer": record["answer"]
        }
    }


def save_jsonl(records: List[Dict[str, Any]], output_path: str) -> None:
    """Save records as JSONL file."""
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    logger.info(f"Saved {len(records)} records to {output_path}")


def format_gsm8k_dataset(
    split: str = "test",
    limit: Optional[int] = None,
    output_runner: Optional[str] = None,
    output_reference: Optional[str] = None,
    include_fewshot: bool = False
) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Load and format GSM8K dataset for SYNTRA.

    Args:
        split: "train" or "test"
        limit: Maximum number of records to process
        output_runner: Path to save runner JSONL (optional)
        output_reference: Path to save reference JSONL (optional)
        include_fewshot: Whether to include few-shot examples in prompts

    Returns:
        Tuple of (runner_records, reference_records)
    """
    # Load GSM8K records
    logger.info(f"Loading GSM8K ({split})...")
    gsm8k_records = load_gsm8k(split=split, limit=limit)

    if not gsm8k_records:
        logger.error(f"No GSM8K records loaded for {split}")
        return [], []

    logger.info(f"Loaded {len(gsm8k_records)} GSM8K records")

    # Format for runner and reference
    runner_records = []
    reference_records = []

    for record in gsm8k_records:
        runner_records.append(format_gsm8k_for_runner(record, include_fewshot))
        reference_records.append(format_gsm8k_for_reference(record))

    logger.info(f"Formatted {len(runner_records)} records")

    # Save if output paths specified
    if output_runner:
        save_jsonl(runner_records, output_runner)

    if output_reference:
        save_jsonl(reference_records, output_reference)

    return runner_records, reference_records


def main():
    """CLI interface for GSM8K formatter."""
    parser = argparse.ArgumentParser(
        description="Format GSM8K dataset for SYNTRA runner and grading"
    )
    parser.add_argument(
        "--split",
        choices=["train", "test"],
        default="test",
        help="Dataset split to format"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of records to format"
    )
    parser.add_argument(
        "--output-runner",
        type=str,
        required=True,
        help="Output path for runner-compatible JSONL"
    )
    parser.add_argument(
        "--output-reference",
        type=str,
        default=None,
        help="Output path for reference answers JSONL (optional)"
    )
    parser.add_argument(
        "--include-fewshot",
        action="store_true",
        help="Include few-shot examples in prompts"
    )

    args = parser.parse_args()

    # Format dataset
    runner_recs, ref_recs = format_gsm8k_dataset(
        split=args.split,
        limit=args.limit,
        output_runner=args.output_runner,
        output_reference=args.output_reference,
        include_fewshot=args.include_fewshot
    )

    if not runner_recs:
        logger.error("No records formatted")
        sys.exit(1)

    # Print summary and sample
    print(f"\n=== Formatted {len(runner_recs)} GSM8K records ===")
    print(f"Split: {args.split}")
    print(f"Runner output: {args.output_runner}")
    if args.output_reference:
        print(f"Reference output: {args.output_reference}")
    print(f"Few-shot included: {args.include_fewshot}")

    print(f"\n=== Sample Runner Record ===")
    print(json.dumps(runner_recs[0], indent=2, ensure_ascii=False))

    if ref_recs and args.output_reference:
        print(f"\n=== Sample Reference Record ===")
        print(json.dumps(ref_recs[0], indent=2, ensure_ascii=False))

    # Validation
    print(f"\n=== Validation ===")
    errors = []

    for i, rec in enumerate(runner_recs):
        # Check required fields
        if "id" not in rec or "content" not in rec or "metadata" not in rec:
            errors.append(f"Record {i}: Missing required fields")
            continue

        # Check metadata
        meta = rec["metadata"]
        if meta.get("type") != "GSM8K_FREE":
            errors.append(f"Record {i}: type != GSM8K_FREE")

        if "gold" not in meta:
            errors.append(f"Record {i}: Missing gold answer")

        # Check content structure
        content = rec["content"]
        if not content.startswith("Solve the problem."):
            errors.append(f"Record {i}: Content doesn't start with expected prompt")

        if "Question:" not in content or "Answer:" not in content:
            errors.append(f"Record {i}: Missing Question/Answer markers")

    if errors:
        print(f"Found {len(errors)} validation errors:")
        for err in errors[:10]:  # Show first 10
            print(f"  - {err}")
        sys.exit(1)
    else:
        print("✓ All records valid")
        print(f"✓ {len(runner_recs)} runner records")
        print(f"✓ {len(ref_recs)} reference records")


if __name__ == "__main__":
    main()
