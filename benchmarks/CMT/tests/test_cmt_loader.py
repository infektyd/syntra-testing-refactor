"""Tests for CMT dataset loader."""

import os
import pytest
from Benchmarks.CMT.bench.datasets_cmt import (
    load_cmt,
    load_cmt_from_hf,
    load_cmt_from_stub,
    normalize_cmt_record,
    TYPE_NAMES,
)


def test_normalize_cmt_record():
    """Test CMT record normalization."""
    raw_record = {
        "prompt": "Test question?",
        "solution": "$\\boxed{a}$",
        "type": "HF",
        "index": 0,
        "parameters": "$x$",
        "functions": "",
    }

    normalized = normalize_cmt_record(raw_record)

    assert normalized["suite"] == "cmt"
    assert normalized["type"] == "HF"
    assert normalized["id"] == "cmt_hf_0"
    assert normalized["item_id"] == "cmt_hf_0"
    assert normalized["prompt"] == "Test question?"
    assert normalized["gold"] == "$\\boxed{a}$"
    assert normalized["meta"]["category"] == "CMT"
    assert normalized["meta"]["type_name"] == TYPE_NAMES["HF"]


def test_normalize_cmt_record_unknown_type():
    """Test normalization with unknown type."""
    raw_record = {
        "prompt": "Test",
        "solution": "$\\boxed{answer}$",
        "type": "Unknown",
        "index": 0,
    }

    normalized = normalize_cmt_record(raw_record)
    assert normalized["type"] == "Other"


def test_load_cmt_from_hf():
    """Test loading CMT from hf_cmt_prompts.json (LIVE mode)."""
    records = load_cmt_from_hf(limit=5, seed=42)

    assert len(records) == 5
    assert all("item_id" in r for r in records)
    assert all("type" in r for r in records)
    assert all("gold" in r for r in records)


def test_load_cmt_from_hf_type_filter():
    """Test type filtering in LIVE mode."""
    records = load_cmt_from_hf(type_filter="HF", limit=10)

    assert len(records) <= 10
    assert all(r["type"] == "HF" for r in records)


def test_load_cmt_from_hf_invalid_type():
    """Test that invalid type raises error."""
    with pytest.raises(ValueError):
        load_cmt_from_hf(type_filter="InvalidType")


def test_load_cmt_from_stub():
    """Test loading from stub files (TEST mode)."""
    records = load_cmt_from_stub(limit=5, seed=42)

    assert len(records) <= 5
    assert all("item_id" in r for r in records)


def test_load_cmt_from_stub_type_filter():
    """Test type filtering with stubs."""
    records = load_cmt_from_stub(type_filter="HF")

    assert all(r["type"] == "HF" for r in records)


def test_load_cmt_auto_mode_live():
    """Test auto mode detection (LIVE)."""
    os.environ["SYNTRA_TEST_MODE"] = "0"
    os.environ["RUN_SYNTRA"] = "0"

    records = load_cmt(limit=3, seed=42)
    assert len(records) == 3


def test_load_cmt_auto_mode_test():
    """Test auto mode detection (TEST)."""
    os.environ["SYNTRA_TEST_MODE"] = "1"
    os.environ["RUN_SYNTRA"] = "0"

    records = load_cmt(limit=3, seed=42)
    assert len(records) <= 3


def test_load_cmt_safety_check():
    """Test safety check: RUN_SYNTRA=1 refuses stubs."""
    os.environ["SYNTRA_TEST_MODE"] = "1"
    os.environ["RUN_SYNTRA"] = "1"

    with pytest.raises(ValueError, match="Safety check failed"):
        load_cmt()

    # Clean up
    os.environ["RUN_SYNTRA"] = "0"


def test_load_cmt_deterministic_sampling():
    """Test that sampling is deterministic with same seed."""
    os.environ["SYNTRA_TEST_MODE"] = "0"

    records1 = load_cmt(limit=10, seed=42)
    records2 = load_cmt(limit=10, seed=42)

    # Should have same items in same order
    ids1 = [r["item_id"] for r in records1]
    ids2 = [r["item_id"] for r in records2]
    assert ids1 == ids2


def test_load_cmt_different_seeds():
    """Test that different seeds produce different samples."""
    os.environ["SYNTRA_TEST_MODE"] = "0"

    records1 = load_cmt(limit=10, seed=42)
    records2 = load_cmt(limit=10, seed=123)

    ids1 = [r["item_id"] for r in records1]
    ids2 = [r["item_id"] for r in records2]

    # Should be different (very unlikely to be same by chance)
    assert ids1 != ids2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
