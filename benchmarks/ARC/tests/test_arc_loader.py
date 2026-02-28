#!/usr/bin/env python3
"""
Tests for ARC dataset loader
Validates schema, loads from stub in test mode, and optionally tests HuggingFace integration.

Usage:
    SYNTRA_TEST_MODE=1 python -m pytest Benchmarks/ARC/tests -q
    python -m pytest Benchmarks/ARC/tests -q  # (requires network & datasets library)
"""

import os
import sys
import json
import unittest
from typing import List, Dict, Any

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from Benchmarks.ARC.bench.datasets_arc import (
    load_arc,
    load_arc_from_stub,
    normalize_arc_record,
)


class TestARCLoader(unittest.TestCase):
    """Test suite for ARC dataset loader."""

    def setUp(self):
        """Set up test environment."""
        # Force test mode for deterministic tests
        os.environ["SYNTRA_TEST_MODE"] = "1"

    def tearDown(self):
        """Clean up test environment."""
        # Restore environment
        if "SYNTRA_TEST_MODE" in os.environ:
            del os.environ["SYNTRA_TEST_MODE"]

    def test_load_arc_challenge_validation_stub(self):
        """Test loading ARC-Challenge validation from stub."""
        records = load_arc(subset="challenge", split="validation", limit=20)

        self.assertIsInstance(records, list)
        self.assertGreater(len(records), 0, "Should load at least 1 record")
        self.assertLessEqual(len(records), 20, "Should respect limit of 20")

    def test_load_arc_easy_validation_stub(self):
        """Test loading ARC-Easy validation from stub."""
        records = load_arc(subset="easy", split="validation", limit=20)

        self.assertIsInstance(records, list)
        self.assertGreater(len(records), 0, "Should load at least 1 record")
        self.assertLessEqual(len(records), 20, "Should respect limit of 20")

    def test_schema_validation_challenge(self):
        """Test schema validation for Challenge subset."""
        records = load_arc(subset="challenge", split="validation", limit=20)

        for rec in records:
            # Required fields
            self.assertIn("id", rec)
            self.assertIn("question", rec)
            self.assertIn("choices", rec)
            self.assertIn("answerKey", rec)
            self.assertIn("subset", rec)
            self.assertIn("split", rec)

            # Type checks
            self.assertIsInstance(rec["id"], str)
            self.assertIsInstance(rec["question"], str)
            self.assertIsInstance(rec["choices"], list)
            self.assertIsInstance(rec["answerKey"], str)
            self.assertIsInstance(rec["subset"], str)
            self.assertIsInstance(rec["split"], str)

            # Value checks
            self.assertGreaterEqual(len(rec["choices"]), 4, "Must have at least 4 choices")
            self.assertIn(rec["answerKey"], ["A", "B", "C", "D", "E"], "answerKey must be A-E")
            self.assertEqual(rec["subset"], "challenge")
            self.assertEqual(rec["split"], "validation")

    def test_schema_validation_easy(self):
        """Test schema validation for Easy subset."""
        records = load_arc(subset="easy", split="validation", limit=20)

        for rec in records:
            # Required fields
            self.assertIn("id", rec)
            self.assertIn("question", rec)
            self.assertIn("choices", rec)
            self.assertIn("answerKey", rec)
            self.assertIn("subset", rec)
            self.assertIn("split", rec)

            # Type checks
            self.assertIsInstance(rec["id"], str)
            self.assertIsInstance(rec["question"], str)
            self.assertIsInstance(rec["choices"], list)
            self.assertIsInstance(rec["answerKey"], str)

            # Value checks
            self.assertGreaterEqual(len(rec["choices"]), 4, "Must have at least 4 choices")
            self.assertIn(rec["answerKey"], ["A", "B", "C", "D", "E"], "answerKey must be A-E")
            self.assertEqual(rec["subset"], "easy")
            self.assertEqual(rec["split"], "validation")

    def test_choices_structure(self):
        """Test that choices have correct structure with labels A-D."""
        records = load_arc(subset="challenge", split="validation", limit=5)

        for rec in records:
            choices = rec["choices"]
            self.assertGreaterEqual(len(choices), 4, "Must have at least 4 choices")

            for choice in choices:
                self.assertIn("label", choice, "Each choice must have a label")
                self.assertIn("text", choice, "Each choice must have text")
                self.assertIsInstance(choice["label"], str)
                self.assertIsInstance(choice["text"], str)
                self.assertIn(choice["label"], ["A", "B", "C", "D", "E"], "Label must be A-E")

            # Check that labels are unique and in order
            labels = [c["label"] for c in choices[:4]]
            self.assertIn("A", labels, "Must have choice A")
            self.assertIn("B", labels, "Must have choice B")
            self.assertIn("C", labels, "Must have choice C")
            self.assertIn("D", labels, "Must have choice D")

    def test_deterministic_loading_in_test_mode(self):
        """Test that loading in test mode is deterministic."""
        records1 = load_arc(subset="challenge", split="validation", limit=10)
        records2 = load_arc(subset="challenge", split="validation", limit=10)

        self.assertEqual(len(records1), len(records2))

        for r1, r2 in zip(records1, records2):
            self.assertEqual(r1["id"], r2["id"])
            self.assertEqual(r1["question"], r2["question"])
            self.assertEqual(r1["answerKey"], r2["answerKey"])

    def test_normalize_arc_record(self):
        """Test the normalize_arc_record function."""
        raw = {
            "id": "test_001",
            "question": "What is 2+2?",
            "choices": {
                "text": ["3", "4", "5", "6"],
                "label": ["A", "B", "C", "D"]
            },
            "answerKey": "B"
        }

        normalized = normalize_arc_record(raw, subset="challenge", split="train")

        self.assertEqual(normalized["id"], "test_001")
        self.assertEqual(normalized["question"], "What is 2+2?")
        self.assertEqual(normalized["answerKey"], "B")
        self.assertEqual(normalized["subset"], "challenge")
        self.assertEqual(normalized["split"], "train")
        self.assertEqual(len(normalized["choices"]), 4)

        # Check choices structure
        self.assertEqual(normalized["choices"][0]["label"], "A")
        self.assertEqual(normalized["choices"][0]["text"], "3")
        self.assertEqual(normalized["choices"][1]["label"], "B")
        self.assertEqual(normalized["choices"][1]["text"], "4")

    def test_answer_key_validity(self):
        """Test that answerKey always points to a valid choice label."""
        records = load_arc(subset="challenge", split="validation", limit=20)

        for rec in records:
            answer_key = rec["answerKey"]
            choice_labels = [c["label"] for c in rec["choices"]]
            self.assertIn(
                answer_key,
                choice_labels,
                f"answerKey '{answer_key}' must be in choice labels {choice_labels}"
            )

    def test_no_empty_questions(self):
        """Test that no questions or IDs are empty."""
        records = load_arc(subset="challenge", split="validation", limit=20)

        for rec in records:
            self.assertGreater(len(rec["id"]), 0, "ID cannot be empty")
            self.assertGreater(len(rec["question"]), 0, "Question cannot be empty")
            self.assertGreater(len(rec["answerKey"]), 0, "answerKey cannot be empty")

    def test_no_empty_choice_text(self):
        """Test that choice text is not empty."""
        records = load_arc(subset="challenge", split="validation", limit=20)

        for rec in records:
            for choice in rec["choices"][:4]:  # Check first 4 choices
                self.assertGreater(
                    len(choice["text"]),
                    0,
                    f"Choice text cannot be empty for question {rec['id']}"
                )

    def test_stub_file_exists_challenge(self):
        """Test that stub file exists for challenge validation."""
        stub_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "stubs",
            "arc_challenge_validation_20.jsonl"
        )
        self.assertTrue(
            os.path.exists(stub_path),
            f"Stub file must exist: {stub_path}"
        )

    def test_stub_file_exists_easy(self):
        """Test that stub file exists for easy validation."""
        stub_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "stubs",
            "arc_easy_validation_20.jsonl"
        )
        self.assertTrue(
            os.path.exists(stub_path),
            f"Stub file must exist: {stub_path}"
        )


class TestARCLoaderNetworkMode(unittest.TestCase):
    """
    Tests that require network access (HuggingFace datasets).
    These are skipped in SYNTRA_TEST_MODE=1.
    """

    def setUp(self):
        """Check if we should skip network tests."""
        self.test_mode = os.getenv("SYNTRA_TEST_MODE", "0") == "1"

    def test_load_from_huggingface_challenge(self):
        """Test loading from HuggingFace (requires network)."""
        if self.test_mode:
            self.skipTest("Skipping network test in SYNTRA_TEST_MODE=1")

        # Temporarily disable test mode
        original_test_mode = os.environ.get("SYNTRA_TEST_MODE")
        if "SYNTRA_TEST_MODE" in os.environ:
            del os.environ["SYNTRA_TEST_MODE"]

        try:
            records = load_arc(subset="challenge", split="validation", limit=5)
            self.assertGreater(len(records), 0, "Should load at least 1 record from HF")

            # Verify schema
            for rec in records:
                self.assertIn("id", rec)
                self.assertIn("question", rec)
                self.assertIn("choices", rec)
                self.assertIn("answerKey", rec)

        finally:
            # Restore test mode
            if original_test_mode:
                os.environ["SYNTRA_TEST_MODE"] = original_test_mode

    def test_load_from_huggingface_easy(self):
        """Test loading from HuggingFace Easy subset (requires network)."""
        if self.test_mode:
            self.skipTest("Skipping network test in SYNTRA_TEST_MODE=1")

        # Temporarily disable test mode
        original_test_mode = os.environ.get("SYNTRA_TEST_MODE")
        if "SYNTRA_TEST_MODE" in os.environ:
            del os.environ["SYNTRA_TEST_MODE"]

        try:
            records = load_arc(subset="easy", split="validation", limit=5)
            self.assertGreater(len(records), 0, "Should load at least 1 record from HF")

            # Verify subset is correct
            for rec in records:
                self.assertEqual(rec["subset"], "easy")

        finally:
            # Restore test mode
            if original_test_mode:
                os.environ["SYNTRA_TEST_MODE"] = original_test_mode


if __name__ == "__main__":
    # Run tests
    unittest.main()
