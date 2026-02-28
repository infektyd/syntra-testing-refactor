"""Protocol compliance tests for CMT runner and tooling."""

import pytest

from Tools.run_manifest import prepare_prompts
from Tools.grade_and_aggregate import grade_cmt_row


def test_prepare_prompts_tolerates_missing_sections():
    """Runner prompt assembly should handle empty protocol sections."""
    records = [
        {
            "suite": "cmt",
            "item_id": "cmt_empty",
            "prompt": "Describe the ground state.",
            "parameters": "",
            "functions": "",
            "protocol": "cmt_v1",
        }
    ]

    prepared = prepare_prompts(records)
    assert len(prepared) == 1
    prompt_text = prepared[0]["prompt"]
    assert "Describe the ground state." in prompt_text
    assert "Output Rules (mandatory):" in prompt_text


def test_prepare_prompts_includes_output_rules_block():
    """Runner prompt assembly must include sections and output rules."""
    record = {
        "suite": "cmt",
        "item_id": "cmt_test_0",
        "prompt": "Compute the correlator.",
        "parameters": "Parameters:\nU_0, U_1",
        "functions": "Functions:\nG(\\tau)",
        "allowed_symbols": "\\alpha, \\beta",
        "protocol": "cmt_v1",
    }

    prepared = prepare_prompts([record])
    assert len(prepared) == 1
    prompt_text = prepared[0]["prompt"]

    assert "Compute the correlator." in prompt_text
    assert "Parameters:\nU_0, U_1" in prompt_text
    assert "Functions:\nG(\\tau)" in prompt_text
    assert "Output Rules (mandatory):" in prompt_text
    assert prepared[0]["prompt_stem"] == "Compute the correlator."


def test_grade_cmt_row_flags_missing_box():
    """Grader should flag responses lacking a boxed answer."""
    row = {
        "response": "Final answer: 1/2",
        "gold": "\\boxed{1/2}",
        "type": "HF",
        "parameters": "p(x)",
        "functions": "f(x)",
    }

    assert not grade_cmt_row(row)
    assert row["parse_error"] == "missing_boxed_answer"
    assert row["parsed_answer"] is None
    assert row["parsed_answer_content"] is None


def test_grade_cmt_row_accepts_boxed_answer():
    """Grader should accept a compliant boxed LaTeX answer."""
    row = {
        "response": "Working...\n\\boxed{1/2}",
        "gold": "\\boxed{1/2}",
        "type": "HF",
        "parameters": "p(x)",
        "functions": "f(x)",
    }

    assert grade_cmt_row(row)
    assert row.get("parse_error") is None
    assert row["parsed_answer"] == "\\boxed{1/2}"
    assert row["parsed_answer_content"] == "1/2"
