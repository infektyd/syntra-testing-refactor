"""Tests for CMT answer evaluation."""

import pytest
from Benchmarks.CMT.bench.eval_cmt import (
    extract_boxed_answer,
    normalize_latex,
    normalize_numeric,
    parse_multiple_choice,
    parse_multiple_selection,
    grade_cmt_response,
    grade_cmt_batch,
)


class TestExtractBoxedAnswer:
    """Test boxed answer extraction."""

    def test_extract_standard_boxed(self):
        """Test extraction from standard $\\boxed{}$ format."""
        response = "The answer is $\\boxed{a}$."
        answer = extract_boxed_answer(response)
        assert answer == "a"

    def test_extract_boxed_multiple_choice(self):
        """Test extraction with multiple selection."""
        response = "Therefore $\\boxed{a; b; d}$ are correct."
        answer = extract_boxed_answer(response)
        assert answer == "a; b; d"

    def test_extract_boxed_numeric(self):
        """Test extraction of numeric answer."""
        response = "The answer is $\\boxed{2280}$."
        answer = extract_boxed_answer(response)
        assert answer == "2280"

    def test_extract_boxed_expression(self):
        """Test extraction of algebraic expression."""
        response = "Thus $\\boxed{E_n = mc^2}$."
        answer = extract_boxed_answer(response)
        assert "E_n" in answer or "mc" in answer

    def test_extract_no_boxed(self):
        """Test when no boxed answer present."""
        response = "The answer is a."
        answer = extract_boxed_answer(response)
        assert answer == ""

    def test_extract_empty_response(self):
        """Test with empty response."""
        answer = extract_boxed_answer("")
        assert answer == ""


class TestNormalizeNumeric:
    """Test numeric parsing."""

    def test_parse_integer(self):
        """Test integer parsing."""
        val = normalize_numeric("2280")
        assert val == 2280.0

    def test_parse_float(self):
        """Test float parsing."""
        val = normalize_numeric("2.5")
        assert abs(val - 2.5) < 1e-9

    def test_parse_scientific(self):
        """Test scientific notation."""
        val = normalize_numeric("1.5e-3")
        assert abs(val - 0.0015) < 1e-9

    def test_parse_fraction(self):
        """Test fraction parsing."""
        val = normalize_numeric("1/2")
        assert abs(val - 0.5) < 1e-9

    def test_parse_with_comma(self):
        """Test parsing numbers with comma separator."""
        val = normalize_numeric("1,234")
        assert abs(val - 1234) < 1e-9

    def test_parse_invalid(self):
        """Test invalid numeric string."""
        val = normalize_numeric("abc")
        assert val is None


class TestParseMultipleChoice:
    """Test multiple choice parsing."""

    def test_parse_single_letter_upper(self):
        """Test extraction of single uppercase letter."""
        answer = parse_multiple_choice("a")
        assert answer == "A"

    def test_parse_single_letter_lower(self):
        """Test extraction of single lowercase letter."""
        answer = parse_multiple_choice("d")
        assert answer == "D"

    def test_parse_letter_with_text(self):
        """Test extraction from text containing letter."""
        answer = parse_multiple_choice("The answer is (c)")
        assert answer == "C"

    def test_parse_no_letter(self):
        """Test when no letter present."""
        answer = parse_multiple_choice("123")
        assert answer == ""


class TestParseMultipleSelection:
    """Test multiple selection parsing."""

    def test_parse_semicolon_separated(self):
        """Test parsing semicolon-separated letters."""
        answer = parse_multiple_selection("a; b; d")
        assert answer == {"A", "B", "D"}

    def test_parse_no_spaces(self):
        """Test parsing without spaces around semicolon."""
        answer = parse_multiple_selection("a;b;d")
        assert answer == {"A", "B", "D"}

    def test_parse_with_text(self):
        """Test parsing from text."""
        answer = parse_multiple_selection("Options are a, b and d")
        # Should extract letters from the text
        assert len(answer) > 0

    def test_parse_empty(self):
        """Test parsing empty string."""
        answer = parse_multiple_selection("")
        assert answer == set()


class TestGradeCmtResponse:
    """Test CMT grading logic."""

    def test_grade_multiple_choice_correct(self):
        """Test grading correct multiple choice."""
        response = "The answer is $\\boxed{a}$"
        gold = "$\\boxed{a}$"

        is_correct, details = grade_cmt_response(response, gold)

        assert is_correct is True
        assert details["answer_format"] == "multiple_choice"

    def test_grade_multiple_choice_incorrect(self):
        """Test grading incorrect multiple choice."""
        response = "The answer is $\\boxed{b}$"
        gold = "$\\boxed{a}$"

        is_correct, details = grade_cmt_response(response, gold)

        assert is_correct is False

    def test_grade_multiple_selection_correct(self):
        """Test grading correct multiple selection."""
        response = "Options: $\\boxed{a; b; d}$"
        gold = "$\\boxed{a; b; d}$"

        is_correct, details = grade_cmt_response(response, gold)

        assert is_correct is True
        assert details["answer_format"] == "multiple_selection"

    def test_grade_multiple_selection_order_independent(self):
        """Test that order doesn't matter in multiple selection."""
        response = "Options: $\\boxed{b; a; d}$"
        gold = "$\\boxed{a; b; d}$"

        is_correct, details = grade_cmt_response(response, gold)

        assert is_correct is True

    def test_grade_numeric_correct(self):
        """Test grading numeric answer."""
        response = "$\\boxed{2280}$"
        gold = "$\\boxed{2280}$"

        is_correct, details = grade_cmt_response(response, gold)

        assert is_correct is True
        assert details["answer_format"] == "numeric"

    def test_grade_numeric_tolerance(self):
        """Test numeric grading with tolerance."""
        response = "$\\boxed{2280.0000001}$"
        gold = "$\\boxed{2280}$"

        is_correct, details = grade_cmt_response(response, gold)

        # Should be correct within tolerance
        assert is_correct is True

    def test_grade_numeric_too_far(self):
        """Test numeric grading exceeding tolerance."""
        response = "$\\boxed{2290}$"
        gold = "$\\boxed{2280}$"

        is_correct, details = grade_cmt_response(response, gold)

        assert is_correct is False

    def test_grade_algebraic_correct(self):
        """Test grading algebraic expression."""
        response = "$\\boxed{U_1/2}$"
        gold = "$\\boxed{U_1/2}$"

        is_correct, details = grade_cmt_response(response, gold)

        assert is_correct is True
        assert details["answer_format"] == "algebraic"

    def test_grade_algebraic_whitespace_insensitive(self):
        """Test that whitespace doesn't affect algebraic matching."""
        response = "$\\boxed{U_1 / 2}$"
        gold = "$\\boxed{U_1/2}$"

        is_correct, details = grade_cmt_response(response, gold)

        assert is_correct is True

    def test_grade_no_boxed_answer(self):
        """Test grading when response lacks boxed answer."""
        response = "The answer is a"
        gold = "$\\boxed{a}$"

        is_correct, details = grade_cmt_response(response, gold)

        # Should handle gracefully
        assert isinstance(details, dict)
        assert "is_correct" in details


class TestGradeCmtBatch:
    """Test batch grading."""

    def test_grade_batch_correct(self):
        """Test batch grading with all correct."""
        responses = [
            "$\\boxed{a}$",
            "$\\boxed{b}$",
            "$\\boxed{c}$",
        ]
        golds = [
            "$\\boxed{a}$",
            "$\\boxed{b}$",
            "$\\boxed{c}$",
        ]

        result = grade_cmt_batch(responses, golds)

        assert result["total"] == 3
        assert result["correct"] == 3
        assert result["accuracy"] == 1.0

    def test_grade_batch_mixed(self):
        """Test batch grading with mixed results."""
        responses = [
            "$\\boxed{a}$",
            "$\\boxed{b}$",
            "$\\boxed{c}$",
        ]
        golds = [
            "$\\boxed{a}$",
            "$\\boxed{x}$",
            "$\\boxed{c}$",
        ]

        result = grade_cmt_batch(responses, golds)

        assert result["total"] == 3
        assert result["correct"] == 2
        assert abs(result["accuracy"] - 2/3) < 1e-9

    def test_grade_batch_length_mismatch(self):
        """Test that mismatched lengths raise error."""
        responses = ["$\\boxed{a}$", "$\\boxed{b}$"]
        golds = ["$\\boxed{a}$"]

        with pytest.raises(ValueError):
            grade_cmt_batch(responses, golds)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
