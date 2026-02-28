#!/usr/bin/env python3
"""
Tests for GSM8K dataset loader and formatter
Validates schema, loads from stub in test mode, and tests formatting.
"""

import os
import sys
import json
import unittest
from typing import List, Dict, Any

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from Benchmarks.GSM8K.bench.datasets_gsm8k import (
    load_gsm8k,
    load_gsm8k_from_stub,
    normalize_gsm8k_record,
)
from Benchmarks.GSM8K.bench.format_gsm8k import (
    format_gsm8k_for_runner,
    format_gsm8k_for_reference,
    extract_final_answer,
    format_question_text,
)


class TestGSM8KLoader(unittest.TestCase):
    """Test suite for GSM8K dataset loader."""

    def setUp(self):
        """Set up test environment."""
        # Force test mode for deterministic tests
        os.environ["SYNTRA_TEST_MODE"] = "1"

    def tearDown(self):
        """Clean up test environment."""
        # Restore environment
        if "SYNTRA_TEST_MODE" in os.environ:
            del os.environ["SYNTRA_TEST_MODE"]

    def test_load_gsm8k_test_stub(self):
        """Test loading GSM8K test from stub."""
        records = load_gsm8k(split="test", limit=20)

        self.assertIsInstance(records, list)
        self.assertGreater(len(records), 0, "Should load at least 1 record")
        self.assertLessEqual(len(records), 20, "Should respect limit of 20")

    def test_schema_validation_test(self):
        """Test schema validation for test split."""
        records = load_gsm8k(split="test", limit=5)

        for rec in records:
            # Required fields
            self.assertIn("id", rec)
            self.assertIn("question", rec)
            self.assertIn("answer", rec)
            self.assertIn("split", rec)

            # Type checks
            self.assertIsInstance(rec["id"], str)
            self.assertIsInstance(rec["question"], str)
            self.assertIsInstance(rec["answer"], str)
            self.assertIsInstance(rec["split"], str)

            # Value checks
            self.assertTrue(rec["id"].startswith("gsm8k_test_"))
            self.assertEqual(rec["split"], "test")
            self.assertIn("####", rec["answer"], "Answer should contain #### marker")

    def test_deterministic_loading_in_test_mode(self):
        """Test that loading in test mode is deterministic."""
        records1 = load_gsm8k(split="test", limit=10)
        records2 = load_gsm8k(split="test", limit=10)

        self.assertEqual(len(records1), len(records2))

        for r1, r2 in zip(records1, records2):
            self.assertEqual(r1["id"], r2["id"])
            self.assertEqual(r1["question"], r2["question"])
            self.assertEqual(r1["answer"], r2["answer"])

    def test_normalize_gsm8k_record(self):
        """Test the normalize_gsm8k_record function."""
        raw = {
            "question": "What is 2+2?",
            "answer": "2 + 2 = 4. #### 4"
        }

        normalized = normalize_gsm8k_record(raw, split="test")

        self.assertTrue(normalized["id"].startswith("gsm8k_test_"))
        self.assertEqual(normalized["question"], "What is 2+2?")
        self.assertEqual(normalized["answer"], "2 + 2 = 4. #### 4")
        self.assertEqual(normalized["split"], "test")

    def test_no_empty_questions_answers(self):
        """Test that no questions or answers are empty."""
        records = load_gsm8k(split="test", limit=10)

        for rec in records:
            self.assertGreater(len(rec["id"]), 0, "ID cannot be empty")
            self.assertGreater(len(rec["question"]), 0, "Question cannot be empty")
            self.assertGreater(len(rec["answer"]), 0, "Answer cannot be empty")

    def test_stub_file_exists(self):
        """Test that stub file exists."""
        stub_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "stubs",
            "gsm8k_test_20.jsonl"
        )
        self.assertTrue(
            os.path.exists(stub_path),
            f"Stub file must exist: {stub_path}"
        )


class TestGSM8KFormatter(unittest.TestCase):
    """Test suite for GSM8K formatter."""

    def setUp(self):
        """Set up test environment."""
        os.environ["SYNTRA_TEST_MODE"] = "1"

    def tearDown(self):
        """Clean up test environment."""
        if "SYNTRA_TEST_MODE" in os.environ:
            del os.environ["SYNTRA_TEST_MODE"]

    def test_extract_final_answer(self):
        """Test extracting final answer from GSM8K format."""
        test_cases = [
            ("Some reasoning here. #### 42", "42"),
            ("Calculation: 2+2=4. #### 4", "4"),
            ("Answer is 123. #### 123", "123"),
            ("Final: #### 999", "999"),
            ("No marker here just 77", "77"),  # fallback
        ]

        for answer_text, expected in test_cases:
            with self.subTest(answer_text=answer_text):
                result = extract_final_answer(answer_text)
                self.assertEqual(result, expected)

    def test_format_gsm8k_for_runner(self):
        """Test formatting GSM8K record for runner."""
        record = {
            "id": "gsm8k_test_001",
            "question": "What is 2+2?",
            "answer": "2 + 2 = 4. #### 4",
            "split": "test"
        }

        result = format_gsm8k_for_runner(record, include_fewshot=False)

        self.assertEqual(result["id"], "gsm8k_test_001")
        self.assertIn("content", result)
        self.assertIn("metadata", result)

        # Check metadata
        meta = result["metadata"]
        self.assertEqual(meta["type"], "GSM8K_FREE")
        self.assertEqual(meta["gold"], "4")
        self.assertEqual(meta["split"], "test")
        self.assertEqual(meta["source"], "openai/gsm8k")

        # Check content
        content = result["content"]
        self.assertIn("Solve the problem. Return only the final number.", content)
        self.assertIn("Question: What is 2+2?", content)
        self.assertIn("Answer:", content)

    def test_format_gsm8k_for_reference(self):
        """Test formatting GSM8K record for reference."""
        record = {
            "id": "gsm8k_test_001",
            "question": "What is 2+2?",
            "answer": "2 + 2 = 4. #### 4",
            "split": "test"
        }

        result = format_gsm8k_for_reference(record)

        self.assertEqual(result["id"], "gsm8k_test_001")
        self.assertEqual(result["type"], "GSM8K_FREE")
        self.assertEqual(result["gold"], "4")
        self.assertIn("meta", result)

        meta = result["meta"]
        self.assertEqual(meta["split"], "test")
        self.assertEqual(meta["source"], "openai/gsm8k")
        self.assertEqual(meta["question"], "What is 2+2?")
        self.assertEqual(meta["full_answer"], "2 + 2 = 4. #### 4")

    def test_format_question_text_with_fewshot(self):
        """Test formatting question text with few-shot examples."""
        record = {
            "id": "gsm8k_test_001",
            "question": "What is 3+3?",
            "answer": "3 + 3 = 6. #### 6",
            "split": "test"
        }

        result = format_question_text(record, include_fewshot=True)

        self.assertIn("Solve the problem. Return only the final number.", result)
        self.assertIn("Question: What is 3+3?", result)
        self.assertIn("Answer:", result)

        # Should include few-shot examples
        self.assertIn("Natalia sold clips", result)  # from fewshot.txt
        self.assertIn("bakery has", result)  # from fewshot.txt

    def test_format_question_text_without_fewshot(self):
        """Test formatting question text without few-shot examples."""
        record = {
            "id": "gsm8k_test_001",
            "question": "What is 3+3?",
            "answer": "3 + 3 = 6. #### 6",
            "split": "test"
        }

        result = format_question_text(record, include_fewshot=False)

        self.assertIn("Solve the problem. Return only the final number.", result)
        self.assertIn("Question: What is 3+3?", result)
        self.assertIn("Answer:", result)

        # Should NOT include few-shot examples
        self.assertNotIn("Natalia sold clips", result)
        self.assertNotIn("bakery has", result)


if __name__ == "__main__":
    unittest.main()