#!/usr/bin/env python3
"""
ARC Dataset Loader (Challenge/Easy)
Fetches allenai/ai2_arc via HuggingFace datasets and normalizes to typed schema.

Schema:
{
    "id": str,
    "question": str,
    "choices": [{"label":"A"|"B"|"C"|"D","text":str}, ...],  # 4 choices
    "answerKey": "A"|"B"|"C"|"D",
    "subset": "challenge"|"easy",
    "split": "train"|"validation"|"test"
}

Usage:
    from Benchmarks.ARC.bench.datasets_arc import load_arc

    records = load_arc(subset="challenge", split="validation", limit=20)
    for rec in records:
        print(rec["id"], rec["question"], rec["answerKey"])
"""

import os
import sys
import json
from typing import List, Dict, Any, Optional, Literal

# Add parent directories to path for common utilities
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "Tools"))

try:
    from common.logger import get_logger
    logger = get_logger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)
    logging.basicConfig(level=logging.INFO)

# Constants
CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..", "runs", "_cache", "arc")
STUB_DIR = os.path.join(os.path.dirname(__file__), "..", "stubs")

SubsetType = Literal["challenge", "easy"]
SplitType = Literal["train", "validation", "test"]
ChoiceLabelType = Literal["A", "B", "C", "D", "E"]


def normalize_arc_record(
    raw: Dict[str, Any],
    subset: SubsetType,
    split: SplitType
) -> Dict[str, Any]:
    """
    Normalize raw ARC record to typed schema.
    """
    # Extract choices
    choices_raw = raw.get("choices", {})
    texts = choices_raw.get("text", [])
    labels = choices_raw.get("label", [])

    # Normalize choices to list of dicts
    choices = [
        {"label": label, "text": text}
        for label, text in zip(labels, texts)
    ]

    # Normalize labels to A, B, C, D if they are digits
    for choice in choices:
        if choice['label'].isdigit():
            choice['label'] = chr(ord('A') + int(choice['label']) - 1)

    # Ensure we have 4 choices (pad if necessary)
    while len(choices) < 4:
        next_label = chr(ord('A') + len(choices))
        choices.append({"label": next_label, "text": ""})

    # Normalize answerKey
    answer_key = raw.get("answerKey", "")
    if answer_key.isdigit():
        answer_key = chr(ord('A') + int(answer_key) - 1)

    return {
        "id": raw.get("id", ""),
        "question": raw.get("question", ""),
        "choices": choices,
        "answerKey": answer_key,
        "subset": subset,
        "split": split
    }


def load_arc_from_stub(
    subset: SubsetType,
    split: SplitType,
    limit: Optional[int] = None
) -> List[Dict[str, Any]]:
    """
    Load ARC data from local stub JSONL (for SYNTRA_TEST_MODE=1).
    """
    # Try to find an exact match first
    stub_filename = f"arc_{subset}_{split}_{limit or 'all'}.jsonl"
    stub_path = os.path.join(STUB_DIR, stub_filename)

    if not os.path.exists(stub_path):
        import glob
        pattern = os.path.join(STUB_DIR, f"arc_{subset}_{split}_*.jsonl")
        candidates = glob.glob(pattern)

        if candidates:
            stub_path = candidates[0]
            logger.info(f"Using available stub: {stub_path}")
        else:
            logger.warning(f"No stub file found matching: {pattern}")
            return []

    logger.info(f"Loading ARC from stub: {stub_path}")
    records = []

    with open(stub_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                record = json.loads(line)
                records.append(record)
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse JSONL line: {e}")
                continue

    if limit and len(records) > limit:
        records = records[:limit]

    logger.info(f"Loaded {len(records)} records from stub")
    return records


def load_arc_from_hf(
    subset: SubsetType,
    split: SplitType,
    limit: Optional[int] = None
) -> List[Dict[str, Any]]:
    """
    Load ARC data from HuggingFace datasets with caching.
    """
    try:
        from datasets import load_dataset
    except ImportError:
        logger.error("HuggingFace datasets library not installed. Run: pip install datasets")
        return []

    os.makedirs(CACHE_DIR, exist_ok=True)

    hf_subset = f"ARC-{subset.capitalize()}"

    logger.info(f"Loading ARC-{subset} ({split}) from HuggingFace...")

    try:
        dataset = load_dataset(
            "allenai/ai2_arc",
            hf_subset,
            split=split,
            cache_dir=CACHE_DIR
        )

        records = []
        for idx, raw in enumerate(dataset):
            if limit and idx >= limit:
                break
            normalized = normalize_arc_record(raw, subset, split)
            records.append(normalized)

        logger.info(f"Loaded {len(records)} records from HuggingFace")
        return records

    except Exception as e:
        logger.error(f"Failed to load from HuggingFace: {e}")
        return []


def load_arc(
    subset: SubsetType = "challenge",
    split: SplitType = "validation",
    limit: Optional[int] = None,
    force_stub: bool = False
) -> List[Dict[str, Any]]:
    """
    Load ARC dataset records with automatic stub fallback.
    """
    test_mode = os.getenv("SYNTRA_TEST_MODE", "0") == "1" or force_stub
    run_syntra_live = os.getenv("RUN_SYNTRA", "0") == "1"

    if test_mode and run_syntra_live:
        logger.error(
            "RUN_SYNTRA=1 detected while SYNTRA_TEST_MODE=1 or force_stub=True. "
            "LIVE mode cannot proceed with ARC stubs."
        )
        raise RuntimeError("ARC loader refused to serve stubs during LIVE execution")

    if test_mode:
        logger.info("SYNTRA_TEST_MODE=1: Using stub data")
        return load_arc_from_stub(subset, split, limit)
    else:
        logger.info("Loading from HuggingFace datasets")
        return load_arc_from_hf(subset, split, limit)


def save_as_jsonl(records: List[Dict[str, Any]], output_path: str) -> None:
    """Save records as JSONL file."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    logger.info(f"Saved {len(records)} records to {output_path}")


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Load ARC dataset (Challenge/Easy) from HuggingFace"
    )
    parser.add_argument(
        "--subset",
        choices=["challenge", "easy"],
        default="challenge",
        help="ARC subset to load"
    )
    parser.add_argument(
        "--split",
        choices=["train", "validation", "test"],
        default="validation",
        help="Dataset split to load"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of records to load"
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output JSONL file path (optional)"
    )
    parser.add_argument(
        "--force-stub",
        action="store_true",
        help="Force loading from stub data"
    )

    args = parser.parse_args()

    records = load_arc(
        subset=args.subset,
        split=args.split,
        limit=args.limit,
        force_stub=args.force_stub
    )

    if not records:
        logger.error("No records loaded")
        sys.exit(1)

    print(f"\nLoaded {len(records)} records from ARC-{args.subset} ({args.split})")
    print(f"\nFirst record:")
    print(json.dumps(records[0], indent=2, ensure_ascii=False))

    if args.output:
        save_as_jsonl(records, args.output)

    print(f"\nSchema validation:")
    for rec in records[:3]:
        assert isinstance(rec["id"], str), "id must be str"
        assert isinstance(rec["question"], str), "question must be str"
        assert isinstance(rec["choices"], list), "choices must be list"
        assert len(rec["choices"]) >= 4, "must have at least 4 choices"
        for choice in rec["choices"]:
            assert "label" in choice, "choice must have label"
            assert "text" in choice, "choice must have text"
        assert rec["answerKey"] in ["A", "B", "C", "D", "E"], "answerKey must be A-E"
        assert rec["subset"] in ["challenge", "easy"], "subset must be challenge|easy"
        assert rec["split"] in ["train", "validation", "test"], "split must be train|validation|test"
    print("Schema validation passed!")


if __name__ == "__main__":
    main()
