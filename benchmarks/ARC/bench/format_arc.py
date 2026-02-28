#!/usr/bin/env python3
"""
ARC Prompt Formatter
Converts ARC dataset records to SYNTRA-compatible JSONL prompts.

Outputs:
  1. Runner format (Swift-compatible):
     {"id": "...", "content": "Q: ...\nA) ...\nB) ...", "metadata": {...}}

  2. Reference format (grading):
     {"id": "...", "type": "MCQ_ARC", "input": "...", "gold": "A", "meta": {...}}

Usage:
    python format_arc.py --subset challenge --split validation \
        --output-runner prompts.jsonl --output-reference answers.jsonl
"""

import os
import sys
import json
import argparse
from typing import List, Dict, Any, Optional

# Add parent directories to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from Benchmarks.ARC.bench.datasets_arc import load_arc

try:
    from Tools.common.logger import get_logger
    logger = get_logger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)
    logging.basicConfig(level=logging.INFO)


def format_question_text(record: Dict[str, Any]) -> str:
    """
    Format ARC record as a structured question with multiple choices.

    Example output:
        Q: Which celestial object orbits a planet?
        A) asteroid
        B) comet
        C) moon
        D) meteor

        Answer with a single letter (A-D).

    Args:
        record: ARC record with question and choices

    Returns:
        Formatted question text
    """
    question = record["question"]
    choices = record["choices"]

    # Build choices text (A) ... B) ... C) ... D) ...)
    choices_text = "\n".join(
        f"{choice['label']}) {choice['text']}"
        for choice in choices[:4]  # Use first 4 choices
    )

    # Determine max choice label for instruction
    max_label = choices[min(3, len(choices)-1)]["label"] if choices else "D"
    instruction = f"Answer with a single letter (A-{max_label})."

    return f"Q: {question}\n{choices_text}\n\n{instruction}"


def format_arc_for_runner(record: Dict[str, Any]) -> Dict[str, Any]:
    """
    Format ARC record for SYNTRA Swift runner.

    Swift runner expects: {"id": str, "content": str, "metadata": dict}

    Args:
        record: Normalized ARC record

    Returns:
        Runner-compatible format
    """
    # Generate unique ID: arc_{subset}_{original_id}
    arc_id = f"arc_{record['subset']}_{record['id']}"

    return {
        "id": arc_id,
        "content": format_question_text(record),
        "metadata": {
            "type": "MCQ_ARC",
            "gold": record["answerKey"],
            "subset": record["subset"],
            "split": record["split"],
            "original_id": record["id"]
        }
    }


def format_arc_for_reference(record: Dict[str, Any]) -> Dict[str, Any]:
    """
    Format ARC record as reference answers for grading.

    Grading tools expect explicit fields for validation.

    Args:
        record: Normalized ARC record

    Returns:
        Reference format with explicit gold answer
    """
    arc_id = f"arc_{record['subset']}_{record['id']}"

    return {
        "id": arc_id,
        "type": "MCQ_ARC",
        "input": format_question_text(record),
        "gold": record["answerKey"],
        "meta": {
            "subset": record["subset"],
            "split": record["split"],
            "original_id": record["id"],
            "question": record["question"],
            "choices": record["choices"]
        }
    }


def save_jsonl(records: List[Dict[str, Any]], output_path: str) -> None:
    """Save records as JSONL file."""
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    logger.info(f"Saved {len(records)} records to {output_path}")


def format_arc_dataset(
    subset: str = "challenge",
    split: str = "validation",
    limit: Optional[int] = None,
    output_runner: Optional[str] = None,
    output_reference: Optional[str] = None
) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Load and format ARC dataset for SYNTRA.

    Args:
        subset: "challenge" or "easy"
        split: "train", "validation", or "test"
        limit: Maximum number of records to process
        output_runner: Path to save runner JSONL (optional)
        output_reference: Path to save reference JSONL (optional)

    Returns:
        Tuple of (runner_records, reference_records)
    """
    # Load ARC records
    logger.info(f"Loading ARC-{subset} ({split})...")
    arc_records = load_arc(subset=subset, split=split, limit=limit)

    if not arc_records:
        logger.error(f"No ARC records loaded for {subset}/{split}")
        return [], []

    logger.info(f"Loaded {len(arc_records)} ARC records")

    # Format for runner and reference
    runner_records = []
    reference_records = []

    for record in arc_records:
        # Validate that the record has the required structure
        choices = record.get("choices", {})
        labels = choices.get("label", [])
        if len(labels) < 4:
            logger.warning(f"Skipping record {record.get('id')} due to insufficient choices: found {len(labels)} but need at least 4.")
            continue

        runner_records.append(format_arc_for_runner(record))
        reference_records.append(format_arc_for_reference(record))

    logger.info(f"Formatted {len(runner_records)} records")

    # Save if output paths specified
    if output_runner:
        save_jsonl(runner_records, output_runner)

    if output_reference:
        save_jsonl(reference_records, output_reference)

    return runner_records, reference_records


def main():
    """CLI interface for ARC formatter."""
    parser = argparse.ArgumentParser(
        description="Format ARC dataset for SYNTRA runner and grading"
    )
    parser.add_argument(
        "--subset",
        choices=["challenge", "easy"],
        default="challenge",
        help="ARC subset to format"
    )
    parser.add_argument(
        "--split",
        choices=["train", "validation", "test"],
        default="validation",
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

    args = parser.parse_args()

    # Format dataset
    runner_recs, ref_recs = format_arc_dataset(
        subset=args.subset,
        split=args.split,
        limit=args.limit,
        output_runner=args.output_runner,
        output_reference=args.output_reference
    )

    if not runner_recs:
        logger.error("No records formatted")
        sys.exit(1)

    # Print summary and sample
    print(f"\n=== Formatted {len(runner_recs)} ARC records ===")
    print(f"Subset: {args.subset}")
    print(f"Split: {args.split}")
    print(f"Runner output: {args.output_runner}")
    if args.output_reference:
        print(f"Reference output: {args.output_reference}")

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
        if meta.get("type") != "MCQ_ARC":
            errors.append(f"Record {i}: type != MCQ_ARC")

        if meta.get("gold") not in ["A", "B", "C", "D", "E"]:
            errors.append(f"Record {i}: Invalid gold answer '{meta.get('gold')}'")

        # Check content structure
        content = rec["content"]
        if not content.startswith("Q: "):
            errors.append(f"Record {i}: Content doesn't start with 'Q: '")

        if "A)" not in content or "B)" not in content:
            errors.append(f"Record {i}: Missing choice markers A) B)")

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
