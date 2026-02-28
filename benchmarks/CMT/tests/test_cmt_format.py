"""Tests for CMT prompt formatting."""

import pytest
from Benchmarks.CMT.bench.format_cmt import (
    format_cmt_for_runner,
    format_cmt_for_reference,
    format_cmt_dataset,
    OUTPUT_RULES_FOOTER,
)


def test_format_cmt_for_runner():
    """Test formatting for runner."""
    record = {
        "item_id": "cmt_hf_0",
        "type": "HF",
        "prompt": "What is the ground state energy?",
        "gold": "$\\boxed{U_1/2}$",
        "parameters": "$U_0;U_1$",
        "functions": "\\mathcal{H}(U_0, U_1)",
    }

    formatted = format_cmt_for_runner(record)

    assert "content" in formatted
    assert "metadata" in formatted
    assert "\\boxed{" in formatted["content"]
    assert "ground state energy" in formatted["content"]
    assert OUTPUT_RULES_FOOTER in formatted["content"]
    assert "Parameters:\n$U_0;U_1$" in formatted["content"]
    assert "Functions:\n\\mathcal{H}(U_0, U_1)" in formatted["content"]
    assert formatted["metadata"]["type"] == "HF"
    assert formatted["metadata"]["item_id"] == "cmt_hf_0"
    assert formatted["metadata"]["functions"] == record["functions"]


def test_format_cmt_for_reference():
    """Test formatting for reference."""
    record = {
        "item_id": "cmt_hf_0",
        "type": "HF",
        "suite": "cmt",
        "prompt": "What is the ground state energy?",
        "gold": "$\\boxed{U_1/2}$",
        "parameters": "$U_0;U_1$",
        "functions": "\\mathcal{H}(U_0, U_1)",
        "meta": {"type_name": "Hartree-Fock"},
    }

    formatted = format_cmt_for_reference(record)

    assert formatted["item_id"] == "cmt_hf_0"
    assert formatted["suite"] == "cmt"
    assert formatted["type"] == "HF"
    assert formatted["protocol"] == "cmt_v1"
    assert formatted["gold"] == "$\\boxed{U_1/2}$"
    assert formatted["meta"]["type_name"] == "Hartree-Fock"


def test_format_cmt_dataset():
    """Test formatting dataset for runner."""
    records = [
        {
            "item_id": "cmt_hf_0",
            "type": "HF",
            "prompt": "Question 1?",
            "gold": "$\\boxed{a}$",
            "parameters": "p",
            "functions": "f",
        },
        {
            "item_id": "cmt_ed_0",
            "type": "ED",
            "prompt": "Question 2?",
            "gold": "$\\boxed{b}$",
            "parameters": "p2",
            "functions": "f2",
        },
    ]

    formatted = format_cmt_dataset(records, for_reference=False)

    assert len(formatted) == 2
    assert all("content" in f for f in formatted)
    assert all("metadata" in f for f in formatted)
    assert "Parameters:\np" in formatted[0]["content"]
    assert "Functions:\nf" in formatted[0]["content"]


def test_format_cmt_dataset_for_reference():
    """Test formatting dataset for reference."""
    records = [
        {
            "item_id": "cmt_hf_0",
            "type": "HF",
            "suite": "cmt",
            "prompt": "Question 1?",
            "gold": "$\\boxed{a}$",
            "meta": {},
            "parameters": "p",
            "functions": "f",
        },
    ]

    formatted = format_cmt_dataset(records, for_reference=True)

    assert len(formatted) == 1
    assert formatted[0]["protocol"] == "cmt_v1"


def test_format_cmt_runner_handles_missing_sections():
    """Ensure missing parameters/functions do not add empty headings."""
    record = {
        "item_id": "cmt_hf_2",
        "type": "HF",
        "prompt": "Question?",
        "gold": "$\\boxed{1}$",
        "parameters": "",
        "functions": "",
    }

    formatted = format_cmt_for_runner(record)

    assert "Parameters:" not in formatted["content"]
    assert "Functions:" not in formatted["content"]
    assert OUTPUT_RULES_FOOTER in formatted["content"]


def test_format_cmt_runner_preserves_existing_labels_and_lists():
    """Ensure existing headings and list-like allowed symbols render cleanly."""
    record = {
        "item_id": "cmt_hf_3",
        "type": "HF",
        "prompt": "Prompt?",
        "parameters": "Parameters:\nalpha, beta",
        "functions": "Functions:\nf(x)",
        "allowed_symbols": ["alpha", "beta"],
    }

    formatted = format_cmt_for_runner(record)

    content = formatted["content"]
    assert content.count("Parameters:") == 1
    assert content.count("Functions:") == 1
    assert "Allowed Symbols:\nalpha, beta" in content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
