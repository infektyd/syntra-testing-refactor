"""Smoke test for ARC evaluator comment handling."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from Benchmarks.ARC.bench import eval_arc


def test_arc_evaluator_handles_header_comments(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Evaluator should tolerate comment headers and produce outputs."""
    monkeypatch.setenv("SYNTRA_TEST_MODE", "1")

    reference_path = tmp_path / "arc_reference.jsonl"
    responses_path = tmp_path / "arc_responses.jsonl"
    pass1_path = tmp_path / "arc_pass1.jsonl"
    report_path = tmp_path / "arc_report.md"

    reference_rows = [
        {"id": "arc_q1", "gold": "B"},
        {"id": "arc_q2", "gold": "A"},
    ]
    responses_rows = [
        {"id": "arc_q1", "response": "Answer: B", "latency_ms": 10},
        {"id": "arc_q2", "response": "C", "latency_ms": 20},
    ]

    reference_path.write_text("\n".join(json.dumps(row) for row in reference_rows) + "\n", encoding="utf-8")
    responses_path.write_text(
        "# SYNTRA ARC responses\n"
        + "\n".join(json.dumps(row) for row in responses_rows)
        + "\n",
        encoding="utf-8",
    )

    metrics = eval_arc.evaluate_arc(
        responses_path=str(responses_path),
        reference_path=str(reference_path),
        output_path=str(pass1_path),
        report_path=str(report_path),
    )

    assert metrics["pass1"] == pytest.approx(0.5)
    assert pass1_path.exists()
    assert report_path.exists()

    pass1_lines = pass1_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(pass1_lines) == 2
