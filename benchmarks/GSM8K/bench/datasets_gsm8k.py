#!/usr/bin/env python3
"""
GSM8K Dataset Loader
Fetches openai/gsm8k via HuggingFace datasets and normalizes to typed schema.

Schema:
{
    "id": str,
    "question": str,
    "answer": str,  # Full answer with reasoning and #### final_number
    "split": "train"|"test"
}

Usage:
    from Benchmarks.GSM8K.bench.datasets_gsm8k import load_gsm8k

    records = load_gsm8k(split="test", limit=20)
    for rec in records:
        print(rec["id"], rec["question"], rec["answer"])
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
CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..", "runs", "_cache", "gsm8k")
STUB_DIR = os.path.join(os.path.dirname(__file__), "..", "stubs")

SplitType = Literal["train", "test"]


def normalize_gsm8k_record(
    raw: Dict[str, Any],
    split: SplitType
) -> Dict[str, Any]:
    """
    Normalize raw GSM8K record to typed schema.
    """
    return {
        "id": f"gsm8k_{split}_{hash(raw['question']) % 1000000:06d}",
        "question": raw.get("question", ""),
        "answer": raw.get("answer", ""),
        "split": split
    }


def load_gsm8k_from_stub(
    split: SplitType,
    limit: Optional[int] = None
) -> List[Dict[str, Any]]:
    """
    Load GSM8K data from local stub JSONL (for SYNTRA_TEST_MODE=1).
    """
    stub_filename = f"gsm8k_{split}_{limit or 'all'}.jsonl"
    stub_path = os.path.join(STUB_DIR, stub_filename)

    if not os.path.exists(stub_path):
        import glob
        pattern = os.path.join(STUB_DIR, f"gsm8k_{split}_*.jsonl")
        candidates = glob.glob(pattern)

        if candidates:
            stub_path = candidates[0]
            logger.info(f"Using available stub: {stub_path}")
        else:
            logger.warning(f"No stub file found matching: {pattern}")
            return []

    logger.info(f"Loading GSM8K from stub: {stub_path}")
    records = []

    with open(stub_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                raw_record = json.loads(line)
                normalized = normalize_gsm8k_record(raw_record, split)
                records.append(normalized)
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse JSONL line: {e}")
                continue

    if limit and len(records) > limit:
        records = records[:limit]

    logger.info(f"Loaded {len(records)} records from stub")
    return records


def load_gsm8k_from_hf(
    split: SplitType,
    limit: Optional[int] = None
) -> List[Dict[str, Any]]:
    """
    Load GSM8K data from HuggingFace datasets with caching.
    """
    try:
        from datasets import load_dataset
    except ImportError:
        logger.error("HuggingFace datasets library not installed. Run: pip install datasets")
        return []

    os.makedirs(CACHE_DIR, exist_ok=True)

    logger.info(f"Loading GSM8K ({split}) from HuggingFace...")

    try:
        dataset = load_dataset(
            "openai/gsm8k",
            "main",
            split=split,
            cache_dir=CACHE_DIR
        )

        records = []
        for idx, raw in enumerate(dataset):
            if limit and idx >= limit:
                break
            normalized = normalize_gsm8k_record(raw, split)
            records.append(normalized)

        logger.info(f"Loaded {len(records)} records from HuggingFace")
        return records

    except Exception as e:
        logger.error(f"Failed to load from HuggingFace: {e}")
        return []


def load_gsm8k(
    split: SplitType = "test",
    limit: Optional[int] = None,
    force_stub: bool = False
) -> List[Dict[str, Any]]:
    """
    Load GSM8K dataset records with automatic stub fallback.
    """
    test_mode = os.getenv("SYNTRA_TEST_MODE", "0") == "1" or force_stub
    run_syntra_live = os.getenv("RUN_SYNTRA", "0") == "1"

    if test_mode and run_syntra_live:
        logger.error(
            "RUN_SYNTRA=1 detected while SYNTRA_TEST_MODE=1 or force_stub=True. "
            "LIVE mode cannot proceed with GSM8K stubs."
        )
        raise RuntimeError("GSM8K loader refused to serve stubs during LIVE execution")

    if test_mode:
        logger.info("SYNTRA_TEST_MODE=1: Using stub data")
        return load_gsm8k_from_stub(split, limit)
    else:
        logger.info("Loading from HuggingFace datasets")
        return load_gsm8k_from_hf(split, limit)


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
        description="Load GSM8K dataset from HuggingFace"
    )
    parser.add_argument(
        "--split",
        choices=["train", "test"],
        default="test",
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

    records = load_gsm8k(
        split=args.split,
        limit=args.limit,
        force_stub=args.force_stub
    )

    if not records:
        logger.error("No records loaded")
        sys.exit(1)

    print(f"\nLoaded {len(records)} records from GSM8K ({args.split})")
    print(f"\nFirst record:")
    print(json.dumps(records[0], indent=2, ensure_ascii=False))

    if args.output:
        save_as_jsonl(records, args.output)

    print(f"\nSchema validation:")
    for rec in records[:3]:
        assert isinstance(rec["id"], str), "id must be str"
        assert isinstance(rec["question"], str), "question must be str"
        assert isinstance(rec["answer"], str), "answer must be str"
        assert rec["split"] in ["train", "test"], "split must be train|test"
    print("Schema validation passed!")


if __name__ == "__main__":
    main()
