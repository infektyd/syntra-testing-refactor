#!/usr/bin/env python3
"""Generate dual-run manifest samples for GSM8K and ARC."""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

GSM8K_PROMPT_TEMPLATE = (
    "You are given a math word problem. Solve it carefully.\n"
    "Output only the final number on the last line as:\n"
    "Final Answer: <number>\n\n"
    "Problem:\n"
    "{question}"
)

ARC_PROMPT_TEMPLATE = (
    "Choose exactly one answer (A, B, C, or D).\n"
    "Output only:\n"
    "Final Answer: <A|B|C|D>\n\n"
    "Question:\n"
    "{question}\n\n"
    "Choices:\n"
    "A) {A}\n"
    "B) {B}\n"
    "C) {C}\n"
    "D) {D}"
)


def extract_gsm8k_gold(answer_text: str) -> str:
    """Extract the final numeric answer from GSM8K reasoning text."""
    match = re.search(r"####\s*([^\n]+)", answer_text)
    if match:
        return match.group(1).strip()

    lines = [line.strip() for line in answer_text.strip().splitlines() if line.strip()]
    if lines:
        last_line = lines[-1]
        match = re.search(r"(-?\d+(?:\.\d+)?)", last_line)
        if match:
            return match.group(1)

    return answer_text.strip()


def with_env_override(key: str, value: str) -> Tuple[Optional[str], bool]:
    """Temporarily override an environment variable; returns old value and flag if it existed."""
    existed = key in os.environ
    previous = os.environ.get(key)
    os.environ[key] = value
    return previous, existed


def restore_env(key: str, previous: Optional[str], existed: bool) -> None:
    """Restore an environment variable after override."""
    if existed:
        if previous is not None:
            os.environ[key] = previous
        else:
            os.environ.pop(key, None)
    else:
        os.environ.pop(key, None)


def try_repo_gsm8k_loader() -> Tuple[Optional[List[Dict[str, Any]]], Optional[str]]:
    """Attempt to load GSM8K records via the repo's canonical loader."""
    try:
        from Benchmarks.GSM8K.bench.datasets_gsm8k import load_gsm8k  # type: ignore
    except ImportError as exc:  # pragma: no cover - defensive
        return None, f"Import Benchmarks.GSM8K loader failed: {exc}"

    prev_value, existed = with_env_override("SYNTRA_TEST_MODE", "0")
    try:
        raw_records = load_gsm8k(split="test", limit=None, force_stub=False)
    except Exception as exc:  # pragma: no cover - loader failure handled downstream
        return None, f"load_gsm8k raised: {exc}"
    finally:
        restore_env("SYNTRA_TEST_MODE", prev_value, existed)

    if not raw_records:
        return None, "load_gsm8k returned no records"

    normalized: List[Dict[str, Any]] = []
    for record in raw_records:
        item_id = str(record.get("id", "")).strip()
        question = str(record.get("question", "")).strip()
        answer = str(record.get("answer", "")).strip()
        if not item_id or not question or not answer:
            continue
        normalized.append(
            {
                "item_id": item_id,
                "question": question,
                "answer": answer,
                "gold": extract_gsm8k_gold(answer),
            }
        )

    if not normalized:
        return None, "Repository loader produced empty/invalid records"

    return normalized, None


def load_jsonl_records(path: Path) -> List[Dict[str, Any]]:
    """Load JSONL file into a list of dicts."""
    records: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path} line {line_number}: {exc}") from exc
    return records


def try_fallback_gsm8k() -> Tuple[Optional[List[Dict[str, Any]]], List[str], List[str]]:
    """Attempt to load GSM8K from local JSONL fallbacks."""
    candidate_paths = [
        PROJECT_ROOT / "runs" / "gsm8k" / "gsm8k_reference.jsonl",
        PROJECT_ROOT / "runs" / "gsm8k" / "gsm8k_reference 2.jsonl",
        PROJECT_ROOT / "Benchmarks" / "GSM8K" / "stubs" / "gsm8k_test_20.jsonl",
    ]
    errors: List[str] = []
    tried: List[str] = []

    for path in candidate_paths:
        tried.append(str(path))
        if not path.exists():
            continue
        try:
            raw_records = load_jsonl_records(path)
        except ValueError as exc:
            errors.append(str(exc))
            continue

        normalized: List[Dict[str, Any]] = []
        for record in raw_records:
            item_id = str(record.get("id") or record.get("item_id") or record.get("metadata", {}).get("id") or "").strip()
            question = ""
            answer_text = ""
            gold = ""

            if "meta" in record:
                meta = record["meta"] or {}
                question = str(meta.get("question", "")).strip()
                answer_text = str(meta.get("full_answer", "")).strip()
                gold = str(record.get("gold", "")).strip()
            else:
                question = str(record.get("question", "")).strip()
                answer_text = str(record.get("answer", "")).strip()
                gold = extract_gsm8k_gold(answer_text)

            if not item_id and record.get("metadata"):
                item_id = str(record["metadata"].get("original_id") or record["metadata"].get("id") or "").strip()

            if not item_id:
                continue

            if not question and "content" in record:
                question = record["content"]

            if not gold:
                gold = extract_gsm8k_gold(answer_text)

            if not question or not gold:
                continue

            normalized.append(
                {
                    "item_id": item_id,
                    "question": question,
                    "answer": answer_text,
                    "gold": gold,
                }
            )

        if normalized:
            return normalized, errors, tried

    return None, errors, tried


def load_gsm8k_records() -> List[Dict[str, Any]]:
    """Load GSM8K canonical records, raising descriptive errors if unavailable."""
    records, loader_error = try_repo_gsm8k_loader()
    fallback_errors: List[str] = []
    fallback_paths: List[str] = []

    if records is None:
        fallback_records, fallback_errors, fallback_paths = try_fallback_gsm8k()
        if fallback_records is not None:
            return fallback_records

    if records is not None:
        return records

    message_lines = [
        "Unable to load canonical GSM8K dataset.",
        f"- Repo loader: {loader_error or 'not attempted'}",
    ]
    if fallback_errors or fallback_paths:
        message_lines.append("- Paths examined:")
        for path in fallback_paths:
            status = "found" if Path(path).exists() else "missing"
            message_lines.append(f"    {path} ({status})")
        if fallback_errors:
            message_lines.append("- File parsing issues:")
            for err in fallback_errors:
                message_lines.append(f"    {err}")
    message_lines.append("Ensure the dataset is available or adjust the paths above.")
    raise RuntimeError("\n".join(message_lines))


def try_repo_arc_loader() -> Tuple[Optional[List[Dict[str, Any]]], Optional[str]]:
    """Attempt to load ARC challenge validation records via repo loader."""
    try:
        from Benchmarks.ARC.bench.datasets_arc import load_arc  # type: ignore
    except ImportError as exc:  # pragma: no cover - defensive
        return None, f"Import Benchmarks.ARC loader failed: {exc}"

    prev_value, existed = with_env_override("SYNTRA_TEST_MODE", "0")
    try:
        raw_records = load_arc(subset="challenge", split="validation", limit=None, force_stub=False)
    except Exception as exc:  # pragma: no cover
        return None, f"load_arc raised: {exc}"
    finally:
        restore_env("SYNTRA_TEST_MODE", prev_value, existed)

    if not raw_records:
        return None, "load_arc returned no records"

    normalized: List[Dict[str, Any]] = []
    for record in raw_records:
        item_id = f"arc_{record.get('subset', 'challenge')}_{record.get('id', '')}".strip("_")
        question = str(record.get("question", "")).strip()
        choices = record.get("choices", [])
        answer_key = str(record.get("answerKey", "")).strip().upper()
        if not item_id or not question or not choices or not answer_key:
            continue
        if not arc_choices_complete(choices):
            continue
        normalized.append(
            {
                "item_id": item_id,
                "question": question,
                "choices": choices,
                "gold": answer_key,
            }
        )

    if not normalized:
        return None, "Repository loader produced empty/invalid records"

    return normalized, None


def try_repo_cmt_loader() -> Tuple[Optional[List[Dict[str, Any]]], Optional[str]]:
    """Attempt to load CMT records via repo loader."""
    try:
        from Benchmarks.CMT.bench.datasets_cmt import load_cmt  # type: ignore
    except ImportError as exc:  # pragma: no cover - defensive
        return None, f"Import Benchmarks.CMT loader failed: {exc}"

    prev_value, existed = with_env_override("SYNTRA_TEST_MODE", "0")
    try:
        raw_records = load_cmt(split="test", type_filter=None, limit=None)
    except Exception as exc:  # pragma: no cover
        return None, f"load_cmt raised: {exc}"
    finally:
        restore_env("SYNTRA_TEST_MODE", prev_value, existed)

    if not raw_records:
        return None, "load_cmt returned no records"

    normalized: List[Dict[str, Any]] = []
    for record in raw_records:
        item_id = str(record.get("item_id", "")).strip()
        prompt = str(record.get("prompt", "")).strip()
        gold = str(record.get("gold", "")).strip()
        item_type = str(record.get("type", "")).strip()
        parameters = _stringify_protocol_field(record.get("parameters"))
        functions = _stringify_protocol_field(record.get("functions"))
        allowed_symbols = _stringify_protocol_field(record.get("allowed_symbols"))
        answer_format = _stringify_protocol_field(record.get("answer_format") or record.get("output_format"))
        if not item_id or not prompt or not gold:
            continue
        normalized.append(
            {
                "item_id": item_id,
                "prompt": prompt,
                "gold": gold,
                "type": item_type,
                "parameters": parameters,
                "functions": functions,
                "allowed_symbols": allowed_symbols,
                "answer_format": answer_format,
            }
        )

    if not normalized:
        return None, "Repository loader produced empty/invalid records"

    return normalized, None


def try_fallback_arc() -> Tuple[Optional[List[Dict[str, Any]]], List[str], List[str]]:
    """Attempt to load ARC challenge validation data from local JSONL files."""
    candidate_paths = [
        PROJECT_ROOT / "runs" / "arc_challenge" / "arc_challenge_reference.jsonl",
        PROJECT_ROOT / "runs" / "arc_challenge" / "arc_challenge_reference 2.jsonl",
        PROJECT_ROOT / "Benchmarks" / "ARC" / "stubs" / "arc_challenge_validation_20.jsonl",
    ]
    errors: List[str] = []
    tried: List[str] = []

    for path in candidate_paths:
        tried.append(str(path))
        if not path.exists():
            continue
        try:
            raw_records = load_jsonl_records(path)
        except ValueError as exc:
            errors.append(str(exc))
            continue

        normalized: List[Dict[str, Any]] = []
        for record in raw_records:
            meta = record.get("meta", {})
            subset = str(meta.get("subset") or record.get("subset") or "challenge").strip()
            original_id = str(meta.get("original_id") or record.get("id") or "").strip()
            item_id = f"arc_{subset}_{original_id}".strip("_")
            question = str(meta.get("question") or record.get("question") or "").strip()
            choices_raw = meta.get("choices") or record.get("choices") or []
            answer_key = str(record.get("gold") or record.get("answerKey") or "").strip().upper()

            if not item_id or not question or not choices_raw or not answer_key:
                continue
            if not arc_choices_complete(choices_raw):
                continue

            normalized.append(
                {
                    "item_id": item_id,
                    "question": question,
                    "choices": choices_raw,
                    "gold": answer_key,
                }
            )

        if normalized:
            return normalized, errors, tried

    return None, errors, tried


def load_arc_records() -> List[Dict[str, Any]]:
    """Load ARC challenge validation records with clear error reporting."""
    records, loader_error = try_repo_arc_loader()
    fallback_errors: List[str] = []
    fallback_paths: List[str] = []

    if records is None:
        fallback_records, fallback_errors, fallback_paths = try_fallback_arc()
        if fallback_records is not None:
            return fallback_records

    if records is not None:
        return records

    message_lines = [
        "Unable to load canonical ARC (challenge/validation) dataset.",
        f"- Repo loader: {loader_error or 'not attempted'}",
    ]
    if fallback_errors or fallback_paths:
        message_lines.append("- Paths examined:")
        for path in fallback_paths:
            status = "found" if Path(path).exists() else "missing"
            message_lines.append(f"    {path} ({status})")
        if fallback_errors:
            message_lines.append("- File parsing issues:")
            for err in fallback_errors:
                message_lines.append(f"    {err}")
    message_lines.append("Ensure the dataset is available or adjust the paths above.")
    raise RuntimeError("\n".join(message_lines))


def load_cmt_records() -> List[Dict[str, Any]]:
    """Load CMT records with clear error reporting."""
    records, loader_error = try_repo_cmt_loader()

    if records is not None:
        return records

    message_lines = [
        "Unable to load canonical CMT dataset.",
        f"- Repo loader: {loader_error or 'not attempted'}",
    ]
    message_lines.append("Ensure the CMT benchmark is available in Benchmarks/CMT/bench/.")
    raise RuntimeError("\n".join(message_lines))


def sample_records(records: Sequence[Dict[str, Any]], k: int, seed: int, suite: str) -> List[Dict[str, Any]]:
    """Deterministically sample k records from the pool."""
    total = len(records)
    if k > total:
        raise ValueError(
            f"Requested n={k} samples for suite '{suite}' but only {total} records are available."
        )
    rng = random.Random(seed)
    return rng.sample(list(records), k)


def normalize_arc_choices(choices_raw: Sequence[Dict[str, Any]]) -> List[str]:
    """Ensure ARC choices are ordered A-D and represented as plain strings."""
    label_to_text: Dict[str, str] = {}
    for choice in choices_raw:
        label = str(choice.get("label", "")).strip().upper()
        text = str(choice.get("text", "")).strip()
        if label and text:
            label_to_text[label] = text

    ordered_labels = ["A", "B", "C", "D"]
    normalized = [label_to_text.get(label, "") for label in ordered_labels]

    if not all(normalized):
        raise ValueError("ARC record missing one or more choices for labels A-D.")
    return normalized


def arc_choices_complete(choices_raw: Sequence[Dict[str, Any]]) -> bool:
    """Return True when choices contain non-empty text for labels A-D."""
    label_to_text: Dict[str, str] = {}
    for choice in choices_raw:
        label = str(choice.get("label", "")).strip().upper()
        text = str(choice.get("text", "")).strip()
        if label:
            label_to_text[label] = text
    return all(label_to_text.get(label) for label in ["A", "B", "C", "D"])


def build_manifest_entry(
    suite: str,
    record: Dict[str, Any],
    seed: int,
    sample_id: int,
) -> Dict[str, Any]:
    """Construct a manifest entry for the sampled record."""
    if suite == "gsm8k":
        prompt = GSM8K_PROMPT_TEMPLATE.format(question=record["question"])
        entry = {
            "suite": "gsm8k",
            "item_id": record["item_id"],
            "protocol": "gsm8k_short_ans_v1",
            "prompt": prompt,
            "gold": record["gold"],
            "seed": seed,
            "sample_id": sample_id,
        }
        return entry

    if suite == "arc_challenge":
        try:
            choices = normalize_arc_choices(record["choices"])
        except ValueError as exc:
            item_id = record.get("item_id", "unknown")
            raise ValueError(f"{item_id}: {exc}") from exc
        prompt = ARC_PROMPT_TEMPLATE.format(
            question=record["question"],
            A=choices[0],
            B=choices[1],
            C=choices[2],
            D=choices[3],
        )
        entry = {
            "suite": "arc_challenge",
            "item_id": record["item_id"],
            "protocol": "arc_mc_v1",
            "prompt": prompt,
            "gold": record["gold"],
            "choices": choices,
            "seed": seed,
            "sample_id": sample_id,
        }
        return entry

    if suite == "cmt":
        parameters = _stringify_protocol_field(record.get("parameters"))
        functions = _stringify_protocol_field(record.get("functions"))
        prompt_text = _stringify_protocol_field(record.get("prompt"))
        gold_text = _stringify_protocol_field(record.get("gold"))
        entry: Dict[str, Any] = {
            "suite": "cmt",
            "item_id": record["item_id"],
            "protocol": "cmt_v1",
            "prompt": prompt_text,
            "parameters": parameters,
            "functions": functions,
            "gold": gold_text,
            "type": record.get("type", ""),
            "seed": seed,
            "sample_id": sample_id,
        }
        allowed_symbols = _stringify_protocol_field(record.get("allowed_symbols"))
        if allowed_symbols.strip():
            entry["allowed_symbols"] = allowed_symbols
        answer_format = _stringify_protocol_field(record.get("answer_format"))
        if answer_format.strip():
            entry["answer_format"] = answer_format
        return entry

    raise ValueError(f"Unsupported suite '{suite}'")


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description="Generate manifest samples for live runs.")
    parser.add_argument(
        "--suite",
        choices=["gsm8k", "arc_challenge", "cmt"],
        required=True,
        help="Benchmark suite to sample.",
    )
    parser.add_argument(
        "--n",
        type=int,
        default=50,
        help="Number of samples to draw (default: 50).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for deterministic sampling (default: 42).",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str]) -> int:
    args = parse_args(argv)
    suite = args.suite
    n = args.n
    seed = args.seed

    if n <= 0:
        raise ValueError("Number of samples (--n) must be positive.")

    if suite == "gsm8k":
        records = load_gsm8k_records()
    elif suite == "arc_challenge":
        records = load_arc_records()
    elif suite == "cmt":
        records = load_cmt_records()
    else:  # pragma: no cover - guarded by argparse choices
        raise ValueError(f"Unsupported suite '{suite}'")

    sampled = sample_records(records, n, seed, suite)

    for sample_id, record in enumerate(sampled):
        entry = build_manifest_entry(suite, record, seed, sample_id)
        print(json.dumps(entry, ensure_ascii=False))

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except Exception as exc:  # pragma: no cover - CLI surface
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
def _stringify_protocol_field(value: Any) -> str:
    """Normalize protocol fields to readable strings for manifests."""
    if value is None:
        return ""
    if isinstance(value, (list, tuple, set)):
        return "; ".join(str(item) for item in value)
    if isinstance(value, dict):
        try:
            return json.dumps(value, ensure_ascii=False, sort_keys=True)
        except TypeError:
            return str(value)
    return str(value)
