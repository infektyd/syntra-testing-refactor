#!/usr/bin/env python3
"""Grade manifest runs and aggregate pass@1 metrics."""

from __future__ import annotations

import argparse
import json
import re
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Grade manifest dual-run outputs.")
    parser.add_argument("--suite", choices=["gsm8k", "arc_challenge", "cmt"], required=True, help="Benchmark suite.")
    parser.add_argument("--dir", required=True, help="Directory containing manifest and run outputs.")
    return parser.parse_args(argv)


def load_jsonl(path: Path) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                records.append(json.loads(stripped))
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path} line {line_number}: {exc}") from exc
    return records


BOXED_ANSWER_PATTERN = re.compile(r"\\boxed\{(.+?)\}", re.DOTALL)


def extract_boxed_answer(text: Any) -> Optional[str]:
    """Extract the first \\boxed{...} content from response text."""
    if not isinstance(text, str):
        return None
    match = BOXED_ANSWER_PATTERN.search(text)
    if not match:
        return None
    return match.group(1).strip()


def normalize_gsm8k_answer(answer: Optional[Any]) -> Optional[Decimal]:
    if answer is None:
        return None
    cleaned = str(answer).replace(",", "").strip()
    if cleaned == "":
        return None
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None


def extract_gsm8k_from_response(response: Any) -> Optional[str]:
    if not isinstance(response, str):
        return None
    matches = re.findall(r"Final Answer:\s*([+-]?\d+(?:\.\d+)?)", response, flags=re.IGNORECASE)
    if matches:
        return matches[-1]
    return None


def grade_gsm8k_row(row: Dict[str, Any]) -> bool:
    raw_parsed = row.get("parsed_answer")
    if raw_parsed is None:
        raw_parsed = extract_gsm8k_from_response(row.get("response"))
    parsed = normalize_gsm8k_answer(raw_parsed)
    gold = normalize_gsm8k_answer(row.get("gold"))
    return parsed is not None and gold is not None and parsed == gold


def extract_arc_from_response(response: Any) -> Optional[str]:
    if not isinstance(response, str):
        return None
    matches = re.findall(r"Final Answer:\s*([A-D])", response, flags=re.IGNORECASE)
    if matches:
        return matches[-1].upper()
    return None


def grade_arc_row(row: Dict[str, Any]) -> bool:
    parsed = row.get("parsed_answer")
    if not isinstance(parsed, str):
        parsed = extract_arc_from_response(row.get("response"))
    gold = row.get("gold")
    if not isinstance(parsed, str) or not isinstance(gold, str):
        return False
    parsed_letter = parsed.strip().upper()
    gold_letter = gold.strip().upper()
    allowed = {"A", "B", "C", "D"}
    if parsed_letter not in allowed or gold_letter not in allowed:
        return False
    return parsed_letter == gold_letter


def grade_cmt_row(row: Dict[str, Any]) -> bool:
    """Grade CMT response enforcing \\boxed{} extraction."""
    try:
        from Benchmarks.CMT.bench.eval_cmt import grade_cmt_response  # type: ignore
    except ImportError:
        row["parse_error"] = "grader_import_failed"
        row["parsed_answer"] = None
        row["parsed_answer_content"] = None
        return False

    response = row.get("response")
    gold = row.get("gold")
    item_type = row.get("type")

    if not isinstance(response, str) or not isinstance(gold, str):
        row["parse_error"] = "invalid_response_or_gold"
        row["parsed_answer"] = None
        row["parsed_answer_content"] = None
        return False

    boxed = extract_boxed_answer(response)
    if boxed is None:
        row["parse_error"] = "missing_boxed_answer"
        row["parsed_answer"] = None
        row["parsed_answer_content"] = None
        return False

    row["parsed_answer"] = f"\\boxed{{{boxed}}}"
    row["parsed_answer_content"] = boxed
    row.pop("parse_error", None)

    is_correct, _ = grade_cmt_response(response, gold, item_type=item_type)
    return is_correct


def grade_row(suite: str, row: Dict[str, Any]) -> bool:
    if suite == "gsm8k":
        return grade_gsm8k_row(row)
    if suite == "arc_challenge":
        return grade_arc_row(row)
    if suite == "cmt":
        return grade_cmt_row(row)
    raise ValueError(f"Unsupported suite '{suite}'")


def ensure_item_alignment(baseline: List[Dict[str, Any]], syntra: List[Dict[str, Any]]) -> None:
    baseline_ids = {row.get("item_id") for row in baseline}
    syntra_ids = {row.get("item_id") for row in syntra}
    if baseline_ids != syntra_ids:
        missing_in_syntra = baseline_ids - syntra_ids
        missing_in_baseline = syntra_ids - baseline_ids
        messages: List[str] = ["Mismatch between baseline and syntra item ids."]
        if missing_in_syntra:
            messages.append(f"- Missing in syntra: {sorted(missing_in_syntra)}")
        if missing_in_baseline:
            messages.append(f"- Missing in baseline: {sorted(missing_in_baseline)}")
        raise RuntimeError("\n".join(messages))


def annotate_rows_with_score(suite: str, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    annotated: List[Dict[str, Any]] = []
    for row in rows:
        working = dict(row)
        working["is_correct"] = grade_row(suite, working)
        annotated.append(working)
    return annotated


def _to_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def compute_metrics(rows: List[Dict[str, Any]]) -> Tuple[float, float]:
    if not rows:
        return 0.0, 0.0
    passes = sum(1 for row in rows if row.get("is_correct"))
    total = len(rows)
    avg_latency = sum(_to_float(row.get("latency_ms")) for row in rows) / total
    return passes / total, avg_latency


def write_jsonl(path: Path, rows: List[Dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_summary(path: Path, summary: Dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def load_manifest_metadata(path: Path) -> Tuple[Optional[int], Optional[str]]:
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped:
                continue
            try:
                record = json.loads(stripped)
            except json.JSONDecodeError:
                continue
            seed = record.get("seed")
            protocol = record.get("protocol")
            seed_int = int(seed) if isinstance(seed, int) else None
            protocol_str = str(protocol) if isinstance(protocol, str) else None
            return seed_int, protocol_str
    return None, None


def grade_suite(suite: str, run_dir: Path) -> None:
    manifest_path = run_dir / "manifest.jsonl"
    if not manifest_path.exists():
        raise FileNotFoundError(f"Manifest not found: {manifest_path}")

    if suite == "gsm8k":
        baseline_path = run_dir / "gsm8k.pass1.baseline.jsonl"
        syntra_path = run_dir / "gsm8k.pass2.syntra.jsonl"
        graded_baseline_path = run_dir / "graded.gsm8k.baseline.jsonl"
        graded_syntra_path = run_dir / "graded.gsm8k.syntra.jsonl"
        summary_path = run_dir / "summary.gsm8k.json"
    elif suite == "arc_challenge":
        baseline_path = run_dir / "arc.pass1.baseline.jsonl"
        syntra_path = run_dir / "arc.pass2.syntra.jsonl"
        graded_baseline_path = run_dir / "graded.arc.baseline.jsonl"
        graded_syntra_path = run_dir / "graded.arc.syntra.jsonl"
        summary_path = run_dir / "summary.arc.json"
    elif suite == "cmt":
        baseline_path = run_dir / "cmt.pass1.baseline.jsonl"
        syntra_path = run_dir / "cmt.pass2.syntra.jsonl"
        graded_baseline_path = run_dir / "graded.cmt.baseline.jsonl"
        graded_syntra_path = run_dir / "graded.cmt.syntra.jsonl"
        summary_path = run_dir / "summary.cmt.json"
    else:
        raise ValueError(f"Unsupported suite '{suite}'")

    for path in [baseline_path, syntra_path]:
        if not path.exists():
            raise FileNotFoundError(f"Run output not found: {path}")

    baseline_rows = load_jsonl(baseline_path)
    syntra_rows = load_jsonl(syntra_path)

    ensure_item_alignment(baseline_rows, syntra_rows)

    annotated_baseline = annotate_rows_with_score(suite, baseline_rows)
    annotated_syntra = annotate_rows_with_score(suite, syntra_rows)

    baseline_pass, baseline_latency = compute_metrics(annotated_baseline)
    syntra_pass, syntra_latency = compute_metrics(annotated_syntra)

    write_jsonl(graded_baseline_path, annotated_baseline)
    write_jsonl(graded_syntra_path, annotated_syntra)

    seed, protocol = load_manifest_metadata(manifest_path)

    summary = {
        "suite": suite,
        "n_items": len(annotated_baseline),
        "baseline": {
            "pass@1": baseline_pass,
            "avg_ms": baseline_latency,
        },
        "syntra": {
            "pass@1": syntra_pass,
            "avg_ms": syntra_latency,
        },
        "seed": seed,
        "protocol": protocol,
    }
    write_summary(summary_path, summary)


def main(argv: Sequence[str]) -> int:
    args = parse_args(argv)
    run_dir = Path(args.dir)
    if not run_dir.exists():
        print(f"ERROR: Run directory not found: {run_dir}")
        return 1

    try:
        grade_suite(args.suite, run_dir)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
