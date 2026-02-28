"""Tests for deterministic ARC sampling helper."""

import os
import sys
import unittest
from typing import List, Dict, Any

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from Benchmarks.ARC.bench.datasets_arc import _take_random_subset


class TestARCSampling(unittest.TestCase):
    """Validate sampling helper without hitting HuggingFace."""

    def setUp(self) -> None:
        self.records: List[Dict[str, Any]] = []
        for i in range(10):
            self.records.append(
                {
                    "id": f"arc_{i}",
                    "question": f"Question {i}?",
                    "choices": [
                        {"label": label, "text": f"Choice {label} for {i}"}
                        for label in ["A", "B", "C", "D"]
                    ],
                    "answerKey": "A",
                    "subset": "challenge",
                    "split": "validation",
                }
            )

    def test_limit_above_dataset_size_returns_all(self) -> None:
        """Limits above dataset length should return every row."""
        sampled = _take_random_subset(self.records, n=len(self.records) + 10, seed=7)
        self.assertEqual(sampled, self.records)

    def test_sampling_is_deterministic_for_seed(self) -> None:
        """Repeated calls with the same seed must match exactly."""
        first = _take_random_subset(self.records, n=4, seed=2024)
        second = _take_random_subset(self.records, n=4, seed=2024)
        expected_indices = [1, 2, 4, 7]
        expected_ids = [self.records[i]["id"] for i in expected_indices]

        self.assertEqual(first, second)
        self.assertEqual([rec["id"] for rec in first], expected_ids)

    def test_different_seeds_produce_distinct_samples(self) -> None:
        """Different seeds should yield different subsets when sampling."""
        sample_a = _take_random_subset(self.records, n=4, seed=2024)
        sample_b = _take_random_subset(self.records, n=4, seed=1337)

        ids_a = {rec["id"] for rec in sample_a}
        ids_b = {rec["id"] for rec in sample_b}

        self.assertNotEqual(ids_a, ids_b)


if __name__ == "__main__":
    unittest.main()
