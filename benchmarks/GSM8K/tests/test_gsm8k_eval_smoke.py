"""Smoke test for GSM8K evaluator numeric parsing."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from Benchmarks.GSM8K.bench import eval_gsm8k


def test_gsm8k_evaluator_parses_numeric_formats(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Evaluator should parse diverse numeric formats and create output artifacts."""
    monkeypatch.setenv("SYNTRA_TEST_MODE", "1")

    reference_path = tmp_path / "gsm8k_reference.jsonl"
    responses_path = tmp_path / "gsm8k_responses.jsonl"
    pass1_path = tmp_path / "gsm8k_pass1.jsonl"
    report_path = tmp_path / "gsm8k_report.md"

    reference_rows = [
        {"id": "gsm_q1", "gold": "1200"},
        {"id": "gsm_q2", "gold": "7"},
    ]
    responses_rows = [
        {"id": "gsm_q1", "response": "Final Answer: $1,200.", "latency_ms": 15},
        {"id": "gsm_q2", "response": "We get 12 meters after simplification.", "latency_ms": 30},
    ]

    reference_path.write_text("\n".join(json.dumps(row) for row in reference_rows) + "\n", encoding="utf-8")
    responses_path.write_text(
        "# GSM8K SYNTRA responses\n"
        + "\n".join(json.dumps(row) for row in responses_rows)
        + "\n",
        encoding="utf-8",
    )

    metrics = eval_gsm8k.evaluate_gsm8k(
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
