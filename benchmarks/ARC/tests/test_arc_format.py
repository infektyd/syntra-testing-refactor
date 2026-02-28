#!/usr/bin/env python3
"""
Tests for ARC prompt formatter
Validates dual-output formatting, schema compliance, and determinism.

Usage:
    SYNTRA_TEST_MODE=1 python -m pytest Benchmarks/ARC/tests/test_arc_format.py -v
"""

import os
import sys
import json
import unittest
import tempfile
from typing import List, Dict, Any

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from Benchmarks.ARC.bench.format_arc import (
    format_arc_dataset,
    format_arc_for_runner,
    format_arc_for_reference,
    format_question_text,
)
from Benchmarks.ARC.bench.datasets_arc import load_arc


class TestARCFormatter(unittest.TestCase):
    """Test suite for ARC prompt formatter."""

    def setUp(self):
        """Set up test environment."""
        os.environ["SYNTRA_TEST_MODE"] = "1"

    def tearDown(self):
        """Clean up test environment."""
        if "SYNTRA_TEST_MODE" in os.environ:
            del os.environ["SYNTRA_TEST_MODE"]

    def test_format_question_text_structure(self):
        """Test that formatted question has correct A) B) C) D) structure."""
        arc_record = load_arc(subset="challenge", split="validation", limit=1)[0]
        text = format_question_text(arc_record)

        # Check structure
        self.assertIn("Q: ", text)
        self.assertIn("A) ", text)
        self.assertIn("B) ", text)
        self.assertIn("C) ", text)
        self.assertIn("D) ", text)
        self.assertIn("Answer with a single letter", text)

        # Check ordering (A before B before C before D)
        pos_a = text.index("A) ")
        pos_b = text.index("B) ")
        pos_c = text.index("C) ")
        pos_d = text.index("D) ")

        self.assertLess(pos_a, pos_b, "A) should come before B)")
        self.assertLess(pos_b, pos_c, "B) should come before C)")
        self.assertLess(pos_c, pos_d, "C) should come before D)")

    def test_format_for_runner_schema(self):
        """Test runner format has correct Swift-compatible schema."""
        arc_record = load_arc(subset="challenge", split="validation", limit=1)[0]
        runner_rec = format_arc_for_runner(arc_record)

        # Required fields
        self.assertIn("id", runner_rec)
        self.assertIn("content", runner_rec)
        self.assertIn("metadata", runner_rec)

        # Type checks
        self.assertIsInstance(runner_rec["id"], str)
        self.assertIsInstance(runner_rec["content"], str)
        self.assertIsInstance(runner_rec["metadata"], dict)

        # Metadata fields
        meta = runner_rec["metadata"]
        self.assertEqual(meta["type"], "MCQ_ARC")
        self.assertIn(meta["gold"], ["A", "B", "C", "D", "E"])
        self.assertIn(meta["subset"], ["challenge", "easy"])
        self.assertIn(meta["split"], ["train", "validation", "test"])
        self.assertIn("original_id", meta)

    def test_format_for_reference_schema(self):
        """Test reference format has correct grading schema."""
        arc_record = load_arc(subset="challenge", split="validation", limit=1)[0]
        ref_rec = format_arc_for_reference(arc_record)

        # Required fields
        self.assertIn("id", ref_rec)
        self.assertIn("type", ref_rec)
        self.assertIn("input", ref_rec)
        self.assertIn("gold", ref_rec)
        self.assertIn("meta", ref_rec)

        # Type checks
        self.assertIsInstance(ref_rec["id"], str)
        self.assertEqual(ref_rec["type"], "MCQ_ARC")
        self.assertIsInstance(ref_rec["input"], str)
        self.assertIn(ref_rec["gold"], ["A", "B", "C", "D", "E"])
        self.assertIsInstance(ref_rec["meta"], dict)

        # Meta fields
        meta = ref_rec["meta"]
        self.assertIn("subset", meta)
        self.assertIn("split", meta)
        self.assertIn("original_id", meta)
        self.assertIn("question", meta)
        self.assertIn("choices", meta)

    def test_gold_answer_validity(self):
        """Test that gold answer is always a valid choice label."""
        records = load_arc(subset="challenge", split="validation", limit=10)

        for arc_rec in records:
            runner_rec = format_arc_for_runner(arc_rec)
            ref_rec = format_arc_for_reference(arc_rec)

            # Gold answer should be A-E
            self.assertIn(runner_rec["metadata"]["gold"], ["A", "B", "C", "D", "E"])
            self.assertIn(ref_rec["gold"], ["A", "B", "C", "D", "E"])

            # Runner and reference should have same gold answer
            self.assertEqual(
                runner_rec["metadata"]["gold"],
                ref_rec["gold"],
                "Runner and reference gold answers must match"
            )

    def test_id_consistency(self):
        """Test that runner and reference formats use same IDs."""
        arc_record = load_arc(subset="challenge", split="validation", limit=1)[0]

        runner_rec = format_arc_for_runner(arc_record)
        ref_rec = format_arc_for_reference(arc_record)

        self.assertEqual(
            runner_rec["id"],
            ref_rec["id"],
            "Runner and reference must have same ID"
        )

        # ID should follow pattern: arc_{subset}_{original_id}
        self.assertTrue(runner_rec["id"].startswith("arc_"))

    def test_content_not_empty(self):
        """Test that formatted content is never empty."""
        records = load_arc(subset="challenge", split="validation", limit=10)

        for arc_rec in records:
            runner_rec = format_arc_for_runner(arc_rec)
            ref_rec = format_arc_for_reference(arc_rec)

            self.assertGreater(len(runner_rec["content"]), 0, "Content cannot be empty")
            self.assertGreater(len(ref_rec["input"]), 0, "Input cannot be empty")

    def test_deterministic_formatting(self):
        """Test that formatting is deterministic."""
        arc_record = load_arc(subset="challenge", split="validation", limit=1)[0]

        # Format multiple times
        runner1 = format_arc_for_runner(arc_record)
        runner2 = format_arc_for_runner(arc_record)

        ref1 = format_arc_for_reference(arc_record)
        ref2 = format_arc_for_reference(arc_record)

        # Should be identical
        self.assertEqual(runner1, runner2, "Runner formatting must be deterministic")
        self.assertEqual(ref1, ref2, "Reference formatting must be deterministic")

    def test_dual_output_consistency(self):
        """Test that dual output (runner + reference) is consistent."""
        records = load_arc(subset="challenge", split="validation", limit=5)

        for arc_rec in records:
            runner_rec = format_arc_for_runner(arc_rec)
            ref_rec = format_arc_for_reference(arc_rec)

            # Same ID
            self.assertEqual(runner_rec["id"], ref_rec["id"])

            # Same gold answer
            self.assertEqual(runner_rec["metadata"]["gold"], ref_rec["gold"])

            # Same type
            self.assertEqual(runner_rec["metadata"]["type"], ref_rec["type"])

            # Content and input should match
            self.assertEqual(runner_rec["content"], ref_rec["input"])

    def test_format_arc_dataset_challenge(self):
        """Test formatting full ARC-Challenge dataset (limit 10)."""
        runner_recs, ref_recs = format_arc_dataset(
            subset="challenge",
            split="validation",
            limit=10
        )

        self.assertEqual(len(runner_recs), len(ref_recs))
        self.assertGreater(len(runner_recs), 0)
        self.assertLessEqual(len(runner_recs), 10)

    def test_format_arc_dataset_easy(self):
        """Test formatting ARC-Easy dataset (limit 10)."""
        runner_recs, ref_recs = format_arc_dataset(
            subset="easy",
            split="validation",
            limit=10
        )

        self.assertEqual(len(runner_recs), len(ref_recs))
        self.assertGreater(len(runner_recs), 0)
        self.assertLessEqual(len(runner_recs), 10)

    def test_save_to_file(self):
        """Test saving formatted records to JSONL files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner_path = os.path.join(tmpdir, "runner.jsonl")
            ref_path = os.path.join(tmpdir, "reference.jsonl")

            runner_recs, ref_recs = format_arc_dataset(
                subset="challenge",
                split="validation",
                limit=5,
                output_runner=runner_path,
                output_reference=ref_path
            )

            # Files should exist
            self.assertTrue(os.path.exists(runner_path))
            self.assertTrue(os.path.exists(ref_path))

            # Files should have content
            with open(runner_path, "r", encoding="utf-8") as f:
                runner_lines = [line.strip() for line in f if line.strip()]

            with open(ref_path, "r", encoding="utf-8") as f:
                ref_lines = [line.strip() for line in f if line.strip()]

            self.assertEqual(len(runner_lines), len(runner_recs))
            self.assertEqual(len(ref_lines), len(ref_recs))

            # Each line should be valid JSON
            for line in runner_lines:
                json.loads(line)  # Should not raise

            for line in ref_lines:
                json.loads(line)  # Should not raise

    def test_metadata_type_is_mcq_arc(self):
        """Test that all formatted records have type=MCQ_ARC."""
        records = load_arc(subset="challenge", split="validation", limit=10)

        for arc_rec in records:
            runner_rec = format_arc_for_runner(arc_rec)
            ref_rec = format_arc_for_reference(arc_rec)

            self.assertEqual(runner_rec["metadata"]["type"], "MCQ_ARC")
            self.assertEqual(ref_rec["type"], "MCQ_ARC")

    def test_no_missing_choices(self):
        """Test that formatted questions have all 4 choice markers."""
        records = load_arc(subset="challenge", split="validation", limit=10)

        for arc_rec in records:
            text = format_question_text(arc_rec)

            # Must have A), B), C), D)
            self.assertIn("A) ", text, "Missing choice A)")
            self.assertIn("B) ", text, "Missing choice B)")
            self.assertIn("C) ", text, "Missing choice C)")
            self.assertIn("D) ", text, "Missing choice D)")

    def test_question_starts_with_q(self):
        """Test that formatted content starts with 'Q: '."""
        records = load_arc(subset="challenge", split="validation", limit=10)

        for arc_rec in records:
            runner_rec = format_arc_for_runner(arc_rec)
            ref_rec = format_arc_for_reference(arc_rec)

            self.assertTrue(
                runner_rec["content"].startswith("Q: "),
                "Content must start with 'Q: '"
            )
            self.assertTrue(
                ref_rec["input"].startswith("Q: "),
                "Input must start with 'Q: '"
            )

    def test_metadata_original_id_preserved(self):
        """Test that original ARC ID is preserved in metadata."""
        arc_record = load_arc(subset="challenge", split="validation", limit=1)[0]
        original_id = arc_record["id"]

        runner_rec = format_arc_for_runner(arc_record)
        ref_rec = format_arc_for_reference(arc_record)

        self.assertEqual(runner_rec["metadata"]["original_id"], original_id)
        self.assertEqual(ref_rec["meta"]["original_id"], original_id)


if __name__ == "__main__":
    unittest.main()
