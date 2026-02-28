#!/usr/bin/env python3
"""
Tests for GSM8K response evaluator
Validates numeric answer extraction and evaluation logic.
"""

import os
import sys
import json
import unittest
import tempfile
from decimal import Decimal

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from Benchmarks.GSM8K.bench.eval_gsm8k import (
    extract_numeric_answer,
    evaluate_gsm8k,
)


class TestGSM8KEvaluator(unittest.TestCase):
    """Test suite for GSM8K evaluator."""

    def test_extract_numeric_answer_simple(self):
        """Test extracting simple numeric answers."""
        test_cases = [
            ("42", Decimal("42")),
            ("3.14", Decimal("3.14")),
            ("100", Decimal("100")),
            ("0", Decimal("0")),
            ("", None),
            ("no numbers here", None),
        ]

        for text, expected in test_cases:
            with self.subTest(text=text):
                result = extract_numeric_answer(text)
                self.assertEqual(result, expected)

    def test_extract_numeric_answer_with_commas(self):
        """Test extracting numbers with commas."""
        test_cases = [
            ("1,200", Decimal("1200")),
            ("1,000,000", Decimal("1000000")),
            ("$1,200", Decimal("1200")),
            ("€50", Decimal("50")),
        ]

        for text, expected in test_cases:
            with self.subTest(text=text):
                result = extract_numeric_answer(text)
                self.assertEqual(result, expected)

    def test_extract_numeric_answer_with_units(self):
        """Test extracting numbers with units."""
        test_cases = [
            ("12 meters", Decimal("12")),
            ("5 kg", Decimal("5")),
            ("$1200 dollars", Decimal("1200")),
            ("42.5 pounds", Decimal("42.5")),
        ]

        for text, expected in test_cases:
            with self.subTest(text=text):
                result = extract_numeric_answer(text)
                self.assertEqual(result, expected)

    def test_extract_numeric_answer_with_punctuation(self):
        """Test extracting numbers with punctuation."""
        test_cases = [
            ("42.", Decimal("42")),
            ("(42)", Decimal("42")),
            ("[42]", Decimal("42")),
            ("42!", Decimal("42")),
        ]

        for text, expected in test_cases:
            with self.subTest(text=text):
                result = extract_numeric_answer(text)
                self.assertEqual(result, expected)

    def test_extract_numeric_answer_in_text(self):
        """Test extracting numbers embedded in text."""
        test_cases = [
            ("The answer is 42", Decimal("42")),
            ("Result: 42", Decimal("42")),
            ("Final answer: 42", Decimal("42")),
            ("Answer: 42", Decimal("42")),
            ("So the total is 42", Decimal("42")),
            ("Therefore, 42", Decimal("42")),
            ("Total: 42", Decimal("42")),
        ]

        for text, expected in test_cases:
            with self.subTest(text=text):
                result = extract_numeric_answer(text)
                self.assertEqual(result, expected)

    def test_extract_numeric_answer_boxed(self):
        """Test extracting boxed answers (LaTeX style)."""
        test_cases = [
            (r"\boxed{42}", Decimal("42")),
            (r"Some text \boxed{3.14}", Decimal("3.14")),
            (r"\boxed{1,200}", Decimal("1200")),
        ]

        for text, expected in test_cases:
            with self.subTest(text=text):
                result = extract_numeric_answer(text)
                self.assertEqual(result, expected)

    def test_extract_numeric_answer_final_markers(self):
        """Test extracting answers with final markers."""
        test_cases = [
            ("#### 42", Decimal("42")),
            ("Final Answer: 42", Decimal("42")),
            ("Answer = 42", Decimal("42")),
        ]

        for text, expected in test_cases:
            with self.subTest(text=text):
                result = extract_numeric_answer(text)
                self.assertEqual(result, expected)

    def test_extract_numeric_answer_last_number(self):
        """Test fallback to last number in text."""
        test_cases = [
            ("There are 10 apples and 20 oranges. Total: 30", Decimal("30")),
            ("Step 1: 5, Step 2: 10, Final: 15", Decimal("15")),
            ("Wrong: 99, Right: 42", Decimal("42")),
        ]

        for text, expected in test_cases:
            with self.subTest(text=text):
                result = extract_numeric_answer(text)
                self.assertEqual(result, expected)

    def test_extract_numeric_answer_edge_cases(self):
        """Test edge cases and invalid inputs."""
        test_cases = [
            ("", None),
            ("no numbers", None),
            ("123abc", None),  # number not standalone (followed by letters)
            ("42abc", None),  # not at end
        ]

        for text, expected in test_cases:
            with self.subTest(text=text):
                result = extract_numeric_answer(text)
                self.assertEqual(result, expected)

    def test_evaluate_gsm8k_perfect_score(self):
        """Test evaluation with perfect score."""
        # Create temporary files
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as resp_file, \
             tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as ref_file:

            # Reference answers
            ref_data = [
                {"id": "test1", "gold": "42"},
                {"id": "test2", "gold": "3.14"},
            ]
            for item in ref_data:
                json.dump(item, ref_file)
                ref_file.write('\n')

            # Responses (correct)
            resp_data = [
                {"id": "test1", "response": "42", "latency_ms": 100},
                {"id": "test2", "response": "3.14", "latency_ms": 200},
            ]
            for item in resp_data:
                json.dump(item, resp_file)
                resp_file.write('\n')

            resp_file.close()
            ref_file.close()

            try:
                metrics = evaluate_gsm8k(resp_file.name, ref_file.name)

                self.assertEqual(metrics["n"], 2)
                self.assertEqual(metrics["n_correct"], 2)
                self.assertEqual(metrics["n_invalid"], 0)
                self.assertEqual(metrics["pass1"], 1.0)
                self.assertAlmostEqual(metrics["latency_ms_mean"], 150.0)

            finally:
                os.unlink(resp_file.name)
                os.unlink(ref_file.name)

    def test_evaluate_gsm8k_with_errors(self):
        """Test evaluation with some incorrect answers."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as resp_file, \
             tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as ref_file:

            # Reference answers
            ref_data = [
                {"id": "test1", "gold": "42"},
                {"id": "test2", "gold": "3.14"},
                {"id": "test3", "gold": "100"},
            ]
            for item in ref_data:
                json.dump(item, ref_file)
                ref_file.write('\n')

            # Responses (mixed correct/incorrect)
            resp_data = [
                {"id": "test1", "response": "42", "latency_ms": 100},  # correct
                {"id": "test2", "response": "wrong", "latency_ms": 200},  # invalid
                {"id": "test3", "response": "99", "latency_ms": 150},  # incorrect
            ]
            for item in resp_data:
                json.dump(item, resp_file)
                resp_file.write('\n')

            resp_file.close()
            ref_file.close()

            try:
                metrics = evaluate_gsm8k(resp_file.name, ref_file.name)

                self.assertEqual(metrics["n"], 3)
                self.assertEqual(metrics["n_correct"], 1)
                self.assertEqual(metrics["n_invalid"], 1)
                self.assertEqual(metrics["pass1"], 1.0/3.0)

            finally:
                os.unlink(resp_file.name)
                os.unlink(ref_file.name)

    def test_evaluate_gsm8k_saves_output(self):
        """Test that evaluation saves output files."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as resp_file, \
             tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as ref_file, \
             tempfile.NamedTemporaryFile(suffix='.jsonl', delete=False) as out_file:

            # Simple test data
            ref_data = [{"id": "test1", "gold": "42"}]
            json.dump(ref_data[0], ref_file)
            ref_file.write('\n')

            resp_data = [{"id": "test1", "response": "42", "latency_ms": 100}]
            json.dump(resp_data[0], resp_file)
            resp_file.write('\n')

            resp_file.close()
            ref_file.close()

            try:
                metrics = evaluate_gsm8k(resp_file.name, ref_file.name, output_path=out_file.name)

                # Check output file was created and has content
                self.assertTrue(os.path.exists(out_file.name))
                with open(out_file.name, 'r') as f:
                    content = f.read()
                    self.assertIn('"pass": true', content)
                    self.assertIn('"id": "test1"', content)

            finally:
                for f in [resp_file.name, ref_file.name, out_file.name]:
                    if os.path.exists(f):
                        os.unlink(f)


if __name__ == "__main__":
    unittest.main()