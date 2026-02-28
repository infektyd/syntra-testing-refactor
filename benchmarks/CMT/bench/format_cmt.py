"""CMT prompt formatting for runner and reference use.

Formats CMT physics problems into standardized formats for:
1. Runner format: For sending to language models
2. Reference format: For grading and analysis
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional, Sequence

try:
    from Benchmarks.CMT.bench.datasets_cmt import load_cmt  # type: ignore
except ImportError:
    from datasets_cmt import load_cmt  # type: ignore

OUTPUT_RULES_FOOTER = (
    "---\n"
    "Output Rules (mandatory):\n"
    "1) Return ONLY the final result as LaTeX in a single box: \\boxed{...}\n"
    "2) No derivation, no prose, no code, no extra lines.\n"
    "3) If the answer is a vector/multiplet, use \\boxed{a; b; c}\n"
    "4) If operators are involved, preserve non-commutative ordering.\n"
)


def _optional_block(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, (list, tuple, set)):
        text = ", ".join(str(item) for item in value)
    else:
        text = str(value)
    return text if text.strip() else None


def _format_section(label: str, content: Any) -> Optional[str]:
    """Return a labeled section unless the content already supplies one."""
    text = _optional_block(content)
    if text is None:
        return None
    stripped = text.lstrip()
    if stripped.lower().startswith(label.lower()):
        return text
    return f"{label}:\n{text}"


def compose_cmt_prompt(
    prompt: Any,
    parameters: Any,
    functions: Any,
    allowed_symbols: Any = None,
) -> str:
    """Assemble the CMT prompt while preserving original math formatting."""
    problem_text = "" if prompt is None else str(prompt)
    sections: List[str] = []

    if problem_text:
        sections.append(problem_text)

    params_section = _format_section("Parameters", parameters)
    if params_section:
        sections.append(params_section)

    functions_section = _format_section("Functions", functions)
    if functions_section:
        sections.append(functions_section)

    allowed_section = _format_section("Allowed Symbols", allowed_symbols)
    if allowed_section:
        sections.append(allowed_section)

    body = "\n\n".join(sections)
    if body.endswith("\n"):
        return f"{body}{OUTPUT_RULES_FOOTER}"
    if body:
        return f"{body}\n\n{OUTPUT_RULES_FOOTER}"
    return OUTPUT_RULES_FOOTER


def format_cmt_for_runner(record: Dict[str, Any]) -> Dict[str, str]:
    """Format CMT problem for sending to language model runner.

    Includes clear instructions about answer format.

    Args:
        record: Normalized CMT record from dataset loader

    Returns:
        Dictionary with 'content' (the prompt) and metadata
    """
    prompt = record.get("prompt", "")
    cmt_type = record.get("type", "Unknown")
    parameters = record.get("parameters", "")
    functions = record.get("functions", "")
    allowed_symbols = record.get("allowed_symbols")
    formatted_prompt = compose_cmt_prompt(prompt, parameters, functions, allowed_symbols)
    answer_format = record.get("answer_format") or record.get("output_format")

    return {
        "content": formatted_prompt,
        "metadata": {
            "item_id": record.get("item_id", ""),
            "type": cmt_type,
            "parameters": parameters,
            "functions": functions,
            "allowed_symbols": allowed_symbols,
            "answer_format": answer_format,
            "original_prompt": prompt,
        }
    }



def format_cmt_for_reference(record: Dict[str, Any]) -> Dict[str, Any]:
    """Format CMT problem as reference for grading.

    Args:
        record: Normalized CMT record from dataset loader

    Returns:
        Dictionary with problem details and gold answer
    """
    return {
        "item_id": record.get("item_id", ""),
        "suite": "cmt",
        "type": record.get("type", "Unknown"),
        "protocol": "cmt_v1",
        "prompt": record.get("prompt", ""),
        "gold": record.get("gold", ""),  # Gold answer in $\boxed{}$ format
        "parameters": record.get("parameters", ""),
        "functions": record.get("functions", ""),
        "allowed_symbols": record.get("allowed_symbols", ""),
        "answer_format": record.get("answer_format") or record.get("output_format", ""),
        "meta": record.get("meta", {}),
    }



def format_cmt_dataset(
    records: List[Dict[str, Any]],
    for_reference: bool = False
) -> List[Dict[str, Any]]:
    """Format a list of CMT records.

    Args:
        records: List of normalized CMT records
        for_reference: If True, format for reference; else for runner

    Returns:
        List of formatted records
    """
    if for_reference:
        return [format_cmt_for_reference(r) for r in records]
    else:
        return [format_cmt_for_runner(r) for r in records]


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description="Format CMT dataset for benchmark runs.")
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of samples to format (default: all).",
    )
    parser.add_argument(
        "--output-runner",
        type=str,
        required=True,
        help="Output path for runner (prompt) format.",
    )
    parser.add_argument(
        "--output-reference",
        type=str,
        required=True,
        help="Output path for reference (grading) format.",
    )
    return parser.parse_args(argv)


def write_jsonl(path: Path, records: List[Dict[str, Any]]) -> None:
    """Write records to JSONL file."""
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def main(argv: Sequence[str]) -> int:
    """Main entry point for CLI."""
    args = parse_args(argv)

    # Load CMT dataset
    try:
        records = load_cmt(split="test", type_filter=None, limit=args.limit)
    except Exception as exc:
        print(f"ERROR: Failed to load CMT dataset: {exc}", file=sys.stderr)
        return 1

    if not records:
        print("ERROR: No CMT records loaded", file=sys.stderr)
        return 1

    # Format for runner and reference
    runner_records = format_cmt_dataset(records, for_reference=False)
    reference_records = format_cmt_dataset(records, for_reference=True)

    # Write output files
    try:
        runner_path = Path(args.output_runner)
        reference_path = Path(args.output_reference)

        runner_path.parent.mkdir(parents=True, exist_ok=True)
        reference_path.parent.mkdir(parents=True, exist_ok=True)

        write_jsonl(runner_path, runner_records)
        write_jsonl(reference_path, reference_records)

        print(f"Formatted {len(records)} CMT records", file=sys.stderr)
        print(f"  Runner:    {runner_path}", file=sys.stderr)
        print(f"  Reference: {reference_path}", file=sys.stderr)
    except Exception as exc:
        print(f"ERROR: Failed to write output files: {exc}", file=sys.stderr)
        return 1

    return 0


__all__ = [
    "OUTPUT_RULES_FOOTER",
    "compose_cmt_prompt",
    "format_cmt_for_runner",
    "format_cmt_for_reference",
    "format_cmt_dataset",
    "main",
]

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
