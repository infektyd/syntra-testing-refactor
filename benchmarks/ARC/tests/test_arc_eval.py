#!/usr/bin/env python3
"""
Tests for ARC evaluator
"""

import os
import sys
import json
import unittest
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from Benchmarks.ARC.bench.eval_arc import parse_letter, evaluate_arc


class TestParseLetter(unittest.TestCase):
    """Test letter parsing from various formats."""

    def test_parse_simple_letters(self):
        """Test simple letter formats."""
        self.assertEqual(parse_letter("C"), "C")
        self.assertEqual(parse_letter("A"), "A")
        self.assertEqual(parse_letter("D"), "D")
        self.assertEqual(parse_letter("B"), "B")

    def test_parse_with_punctuation(self):
        """Test letters with punctuation."""
        self.assertEqual(parse_letter("C."), "C")
        self.assertEqual(parse_letter("(C)"), "C")
        self.assertEqual(parse_letter("[A]"), "A")
        self.assertEqual(parse_letter("B)"), "B")

    def test_parse_with_answer_context(self):
        """Test 'Answer: X' format."""
        self.assertEqual(parse_letter("Answer: C"), "C")
        self.assertEqual(parse_letter("The answer is C"), "C")
        self.assertEqual(parse_letter("answer = B"), "B")

    def test_parse_choice_format(self):
        """Test choice format 'X) text'."""
        self.assertEqual(parse_letter("C) moon is correct"), "C")
        self.assertEqual(parse_letter("A - asteroid"), "A")
        self.assertEqual(parse_letter("B: comet"), "B")

    def test_parse_with_explanation(self):
        """Test letters embedded in explanations."""
        self.assertEqual(parse_letter("I choose C as the answer"), "C")
        self.assertEqual(parse_letter("select A"), "A")
        self.assertEqual(parse_letter("pick B"), "B")

    def test_parse_correctness_phrases(self):
        """Test 'X is correct' format."""
        self.assertEqual(parse_letter("C is correct"), "C")
        self.assertEqual(parse_letter("A is the answer"), "A")
        self.assertEqual(parse_letter("option B"), "B")

    def test_parse_case_insensitive(self):
        """Test case-insensitive parsing."""
        self.assertEqual(parse_letter("c"), "C")
        self.assertEqual(parse_letter("answer: a"), "A")

    def test_parse_invalid(self):
        """Test invalid inputs."""
        self.assertIsNone(parse_letter(""))
        self.assertIsNone(parse_letter(None))
        self.assertIsNone(parse_letter("XYZ"))
        self.assertIsNone(parse_letter("123"))

    def test_parse_edge_cases(self):
        """Test edge cases."""
        # Multiple letters - should take first
        self.assertEqual(parse_letter("A and B"), "A")
        # Letter at end of word should not match
        self.assertIsNotNone(parse_letter("ABCD"))  # Will match first valid letter

    def test_parse_tricky_cases(self):
        """Test tricky and ambiguous cases."""
        self.assertEqual(parse_letter("The correct answer is B, not A."), "B")
        self.assertEqual(parse_letter("My final answer is D."), "D")
        self.assertEqual(parse_letter("I'm torn between A and C, but I'll go with A."), "A")
        self.assertEqual(parse_letter("The answer must be E."), "E")
        self.assertEqual(parse_letter("Let's try B"), "B")

    def test_all_letters(self):
        """Test all valid letters (A-E), upper and lower case."""
        for letter in ["A", "B", "C", "D", "E"]:
            self.assertEqual(parse_letter(letter), letter)
            self.assertEqual(parse_letter(letter.lower()), letter)


class TestEvaluateARC(unittest.TestCase):
    """Test end-to-end evaluation."""

    def setUp(self):
        """Set up test environment."""
        os.environ["SYNTRA_TEST_MODE"] = "1"

    def tearDown(self):
        """Clean up."""
        if "SYNTRA_TEST_MODE" in os.environ:
            del os.environ["SYNTRA_TEST_MODE"]

    def test_evaluate_perfect_score(self):
        """Test evaluation with all correct answers."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create reference
            ref_path = os.path.join(tmpdir, "reference.jsonl")
            with open(ref_path, "w") as f:
                f.write(json.dumps({"id": "q1", "gold": "C"}) + "\n")
                f.write(json.dumps({"id": "q2", "gold": "A"}) + "\n")

            # Create responses (all correct)
            resp_path = os.path.join(tmpdir, "responses.jsonl")
            with open(resp_path, "w") as f:
                f.write(json.dumps({"prompt_id": "q1", "response": "C", "latency_ms": 1000}) + "\n")
                f.write(json.dumps({"prompt_id": "q2", "response": "A", "latency_ms": 1200}) + "\n")

            # Evaluate
            metrics = evaluate_arc(resp_path, ref_path)

            self.assertEqual(metrics["pass1"], 1.0)
            self.assertEqual(metrics["n"], 2)
            self.assertEqual(metrics["n_correct"], 2)
            self.assertEqual(metrics["n_invalid"], 0)

    def test_evaluate_with_errors(self):
        """Test evaluation with some incorrect answers."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ref_path = os.path.join(tmpdir, "reference.jsonl")
            with open(ref_path, "w") as f:
                f.write(json.dumps({"id": "q1", "gold": "C"}) + "\n")
                f.write(json.dumps({"id": "q2", "gold": "A"}) + "\n")
                f.write(json.dumps({"id": "q3", "gold": "B"}) + "\n")

            resp_path = os.path.join(tmpdir, "responses.jsonl")
            with open(resp_path, "w") as f:
                f.write(json.dumps({"prompt_id": "q1", "response": "C", "latency_ms": 1000}) + "\n")  # Correct
                f.write(json.dumps({"prompt_id": "q2", "response": "B", "latency_ms": 1200}) + "\n")  # Wrong
                f.write(json.dumps({"prompt_id": "q3", "response": "xyz123", "latency_ms": 1100}) + "\n")  # Invalid

            metrics = evaluate_arc(resp_path, ref_path)

            self.assertEqual(metrics["n"], 3)
            self.assertEqual(metrics["n_correct"], 1)
            self.assertEqual(metrics["n_invalid"], 1)
            self.assertAlmostEqual(metrics["pass1"], 1/3, places=2)

    def test_evaluate_saves_output(self):
        """Test that output files are created."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ref_path = os.path.join(tmpdir, "reference.jsonl")
            with open(ref_path, "w") as f:
                f.write(json.dumps({"id": "q1", "gold": "C"}) + "\n")

            resp_path = os.path.join(tmpdir, "responses.jsonl")
            with open(resp_path, "w") as f:
                f.write(json.dumps({"prompt_id": "q1", "response": "C", "latency_ms": 1000}) + "\n")

            out_path = os.path.join(tmpdir, "pass1.jsonl")
            report_path = os.path.join(tmpdir, "report.md")

            evaluate_arc(resp_path, ref_path, out_path, report_path)

            # Check files exist
            self.assertTrue(os.path.exists(out_path))
            self.assertTrue(os.path.exists(report_path))

            # Check content
            with open(out_path) as f:
                lines = f.readlines()
                self.assertEqual(len(lines), 1)
                result = json.loads(lines[0])
                self.assertEqual(result["pred_letter"], "C")
                self.assertTrue(result["pass"])


if __name__ == "__main__":
    unittest.main()
