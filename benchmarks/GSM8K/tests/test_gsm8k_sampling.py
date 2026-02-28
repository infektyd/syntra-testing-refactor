"""Tests for deterministic GSM8K sampling helper."""

import os
import sys
import unittest
from typing import List, Dict

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from Benchmarks.GSM8K.bench.datasets_gsm8k import _take_random_subset


class TestGSM8KSampling(unittest.TestCase):
    """Validate sampling helper without hitting HuggingFace."""

    def setUp(self) -> None:
        self.records: List[Dict[str, str]] = [
            {
                "id": f"gsm8k_test_{i:03d}",
                "question": f"Question {i}?",
                "answer": f"Answer {i} #### {i}",
                "split": "test",
            }
            for i in range(10)
        ]

    def test_limit_above_dataset_size_returns_all(self) -> None:
        """Limits above dataset length should return every row."""
        sampled = _take_random_subset(self.records, n=len(self.records) + 5, seed=123)
        self.assertEqual(sampled, self.records)

    def test_sampling_is_deterministic_for_seed(self) -> None:
        """Repeated calls with the same seed must match exactly."""
        first = _take_random_subset(self.records, n=3, seed=42)
        second = _take_random_subset(self.records, n=3, seed=42)
        expected_ids = [self.records[i]["id"] for i in [0, 1, 4]]

        self.assertEqual(first, second)
        self.assertEqual([rec["id"] for rec in first], expected_ids)

    def test_different_seeds_produce_distinct_samples(self) -> None:
        """Different seeds should yield different subsets when sampling."""
        sample_a = _take_random_subset(self.records, n=3, seed=42)
        sample_b = _take_random_subset(self.records, n=3, seed=1337)

        ids_a = {rec["id"] for rec in sample_a}
        ids_b = {rec["id"] for rec in sample_b}

        self.assertNotEqual(ids_a, ids_b)


if __name__ == "__main__":
    unittest.main()
