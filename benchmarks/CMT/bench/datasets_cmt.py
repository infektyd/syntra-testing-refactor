"""CMT dataset loader with type-aware filtering and metadata enrichment.

This module loads condensed matter theory physics problems from hf_cmt_prompts.json
and supports filtering by problem type (HF, ED, DMRG, VMC, QMC, PEPS, SM, Other).
"""

import json
import os
import random
from pathlib import Path
from typing import List, Optional, Dict, Any


# Type mappings: index ranges in hf_cmt_prompts.json
CMT_TYPE_RANGES = {
    "HF": [0, 1, 2, 3, 4],                      # 5 problems
    "ED": [5, 6, 14, 15, 16, 20, 22, 25, 26],   # 9 problems
    "DMRG": [7, 11, 12, 13, 28],                # 5 problems
    "VMC": [6, 13],                             # 2 problems (overlaps: shared indices)
    "QMC": [8, 9, 10, 18, 24, 27],              # 6 problems
    "PEPS": [21, 36, 48],                       # 3 problems
    "SM": [29, 30, 31, 32, 33, 34, 35, 42, 43, 44, 45, 46, 49],  # 13 problems
    "Other": [17, 19, 23, 37, 38, 39, 40, 41, 47],  # 9 problems
}

# Type display names
TYPE_NAMES = {
    "HF": "Hartree-Fock",
    "ED": "Exact Diagonalization",
    "DMRG": "Density Matrix Renormalization Group",
    "VMC": "Variational Monte Carlo",
    "QMC": "Quantum Monte Carlo",
    "PEPS": "Projected Entangled Pair States",
    "SM": "Statistical Mechanics / Spin Models",
    "Other": "Other / Specialized",
}


def normalize_cmt_record(record: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize a CMT record to standard schema.

    Args:
        record: Raw CMT problem record from hf_cmt_prompts.json

    Returns:
        Normalized record with standard fields and metadata
    """
    # Extract type from record
    prob_type = record.get("type", "Other")
    if prob_type not in TYPE_NAMES:
        prob_type = "Other"

    index = record.get("index", -1)

    # Build normalized record
    normalized = {
        "id": f"cmt_{prob_type.lower()}_{index}",
        "item_id": f"cmt_{prob_type.lower()}_{index}",
        "suite": "cmt",
        "type": prob_type,
        "prompt": record.get("prompt", ""),
        "solution": record.get("solution", ""),  # Gold answer in $\boxed{}$ format
        "gold": record.get("solution", ""),       # Alias for compatibility
        "parameters": record.get("parameters", ""),
        "functions": record.get("functions", ""),
        "index": index,
        "meta": {
            "type_name": TYPE_NAMES[prob_type],
            "category": "CMT",
            "original_index": index,
        }
    }
    return normalized


def load_cmt_from_stub(
    split: str = "test",
    type_filter: Optional[str] = None,
    limit: Optional[int] = None,
    seed: int = 42
) -> List[Dict[str, Any]]:
    """Load CMT data from stub files (TEST mode).

    Args:
        split: Data split to load ("test" only for CMT)
        type_filter: Filter by type (e.g., "HF", "ED", etc.), or None for all
        limit: Maximum number of records to return
        seed: Random seed for reproducibility

    Returns:
        List of normalized CMT records
    """
    stub_dir = Path(__file__).parent.parent / "stubs"

    records = []

    if type_filter and type_filter in TYPE_NAMES:
        # Load only for specific type
        stub_file = stub_dir / f"cmt_test_{type_filter.lower()}.jsonl"
        if stub_file.exists():
            with open(stub_file) as f:
                for line in f:
                    if line.strip():
                        record = json.loads(line)
                        records.append(normalize_cmt_record(record))
    else:
        # Load all types
        for type_code in TYPE_NAMES.keys():
            stub_file = stub_dir / f"cmt_test_{type_code.lower()}.jsonl"
            if stub_file.exists():
                with open(stub_file) as f:
                    for line in f:
                        if line.strip():
                            record = json.loads(line)
                            records.append(normalize_cmt_record(record))

    if limit and len(records) > limit:
        rng = random.Random(seed)
        records = rng.sample(records, limit)

    return records


def load_cmt_from_hf(
    type_filter: Optional[str] = None,
    limit: Optional[int] = None,
    seed: int = 42
) -> List[Dict[str, Any]]:
    """Load CMT data from hf_cmt_prompts.json (LIVE mode).

    Args:
        type_filter: Filter by type (e.g., "HF", "ED", etc.), or None for all
        limit: Maximum number of records to return
        seed: Random seed for reproducibility

    Returns:
        List of normalized CMT records

    Raises:
        ValueError: If type_filter is not a valid CMT type
    """
    # Validate type_filter
    if type_filter and type_filter not in TYPE_NAMES:
        raise ValueError(
            f"Unknown CMT type: {type_filter}\n"
            f"Valid types: {', '.join(TYPE_NAMES.keys())}"
        )

    # Load the hf_cmt_prompts.json file
    cmt_file = Path(__file__).parent.parent.parent.parent / "hf_cmt_prompts.json"

    if not cmt_file.exists():
        raise FileNotFoundError(
            f"CMT prompts file not found: {cmt_file}\n"
            "Expected: hf_cmt_prompts.json in repository root"
        )

    all_records = []
    with open(cmt_file) as f:
        for line in f:
            # Skip empty lines
            if not line.strip():
                continue

            # Parse JSONL format (note: may have -> prefix)
            try:
                # Handle potential prefix (number followed by ->)
                content = line.strip()
                if "->" in content:
                    content = content.split("->", 1)[1]

                record = json.loads(content)
                all_records.append(record)
            except json.JSONDecodeError:
                continue

    # Filter by type if specified
    if type_filter and type_filter in TYPE_NAMES:
        indices = set(CMT_TYPE_RANGES.get(type_filter, []))
        filtered = [r for r in all_records if r.get("index", -1) in indices]
    else:
        filtered = all_records

    # Normalize records
    records = [normalize_cmt_record(r) for r in filtered]

    # Deterministic sampling
    if limit and len(records) > limit:
        rng = random.Random(seed)
        records = rng.sample(records, limit)
    elif limit:
        records = records[:limit]

    return records


def load_cmt(
    split: str = "test",
    type_filter: Optional[str] = None,
    limit: Optional[int] = None,
    seed: int = 42
) -> List[Dict[str, Any]]:
    """Load CMT dataset with automatic mode detection.

    Behavior:
    - LIVE mode (SYNTRA_TEST_MODE=0): Load from hf_cmt_prompts.json
    - TEST mode (SYNTRA_TEST_MODE=1): Load from stub files in Benchmarks/CMT/stubs/

    Safety Check:
    - Raises error if RUN_SYNTRA=1 and stubs are requested (not supported)

    Args:
        split: Data split ("test" only for CMT)
        type_filter: Filter by type (HF, ED, DMRG, VMC, QMC, PEPS, SM, Other) or None
        limit: Maximum number of records to return
        seed: Random seed for reproducibility

    Returns:
        List of normalized CMT records with metadata

    Raises:
        ValueError: If RUN_SYNTRA=1 and TEST mode requested
        FileNotFoundError: If required files not found
    """
    # Validate type_filter
    if type_filter and type_filter not in TYPE_NAMES:
        raise ValueError(
            f"Unknown CMT type: {type_filter}\n"
            f"Valid types: {', '.join(TYPE_NAMES.keys())}"
        )

    # Detect mode
    test_mode = os.getenv("SYNTRA_TEST_MODE", "0") == "1"
    run_syntra = os.getenv("RUN_SYNTRA", "0") == "1"

    # Safety check: refuse stubs if RUN_SYNTRA=1
    if test_mode and run_syntra:
        raise ValueError(
            "Safety check failed: RUN_SYNTRA=1 requires SYNTRA_TEST_MODE=0\n"
            "CMT stub data cannot be used with SYNTRA orchestration layer.\n"
            "Set SYNTRA_TEST_MODE=0 to use live hf_cmt_prompts.json data."
        )

    # Load from appropriate source
    if test_mode:
        return load_cmt_from_stub(split=split, type_filter=type_filter, limit=limit, seed=seed)
    else:
        return load_cmt_from_hf(type_filter=type_filter, limit=limit, seed=seed)


__all__ = [
    "load_cmt",
    "load_cmt_from_hf",
    "load_cmt_from_stub",
    "normalize_cmt_record",
    "CMT_TYPE_RANGES",
    "TYPE_NAMES",
]
