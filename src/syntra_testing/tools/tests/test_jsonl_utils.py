"""Tests for JSONL iterator helpers."""

from __future__ import annotations

import io

from Benchmarks.jsonl_utils import iter_jsonl


def test_iter_jsonl_skips_noise_and_preserves_order():
    """Blank lines, comments, BOMs, and malformed rows are ignored."""
    jsonl_buffer = io.StringIO(
        "\ufeff# Header comment that should be ignored\n"
        "\n"
        '{"id": 1, "value": "keep"}\n'
        '{"id": 2, "value": "also keep"},\n'  # Trailing comma
        "{malformed json}\n"
        "   # Indented comment\n"
        '{"id": 3, "value": "final"}\n'
    )

    records = list(iter_jsonl(jsonl_buffer))

    assert [record["id"] for record in records] == [1, 2, 3]
    assert [record["value"] for record in records] == ["keep", "also keep", "final"]
