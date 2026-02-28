#!/usr/bin/env python3
"""
Fix ARC prompt choice markers and gold labels in a JSONL run file.

Usage:
  python3 Tools/CMTExtractor/fix_arc_choices.py --input runs/arc_challenge/arc_challenge_prompts.jsonl \
    --output runs/arc_challenge/arc_challenge_prompts.fixed.jsonl \
    --patch-log runs/arc_challenge/fix_arc_choices.log

The script:
- Normalizes numeric gold answers (1-4) to letters A-D
- If the runner content is missing labeled choices (A) B) ...), but the record contains meta.choices,
  it rebuilds the content using meta.question and meta.choices.
- Writes a fixed JSONL and a patch log describing changes.
"""
import argparse
import json
import re
from typing import List, Dict, Any, Optional


def num_to_letter(num_str: str) -> Optional[str]:
    if not isinstance(num_str, str):
        num_str = str(num_str)
    if not num_str.isdigit():
        return None
    n = int(num_str)
    if 1 <= n <= 26:
        return chr(ord("A") + n - 1)
    return None


def has_choice_markers(content: str) -> bool:
    # Look for A) or A. or A - at start of line (case-insensitive)
    return bool(re.search(r'(?m)^[A-D]\s*[\)\.\-]', content))


def build_content_from_meta(meta: Dict[str, Any]) -> Optional[str]:
    question = meta.get("question") or meta.get("stem") or meta.get("input") or None
    choices = meta.get("choices")
    if not question or not choices:
        return None
    lines = []
    lines.append(f"Q: {question.strip()}")
    for idx, c in enumerate(choices):
        label = None
        text = None
        if isinstance(c, dict):
            label = c.get("label")
            text = c.get("text")
        else:
            text = str(c)
        if not label:
            # fallback enumerate A, B, C...
            label = chr(ord("A") + idx)
        if text is None:
            text = ""
        lines.append(f"{label}) {text.strip()}")
    lines.append("")  # blank line
    lines.append("Answer with a single letter (A-D).")
    return "\n".join(lines)


def normalize_record(rec: Dict[str, Any]) -> (Dict[str, Any], List[str]):
    """
    Return (fixed_record, list_of_changes)
    """
    changes: List[str] = []

    # Normalize gold in metadata or meta or top-level
    gold = None
    if isinstance(rec.get("metadata"), dict):
        gold = rec["metadata"].get("gold")
    if gold is None and isinstance(rec.get("meta"), dict):
        gold = rec["meta"].get("gold")
    if gold is None and "gold" in rec:
        gold = rec.get("gold")

    if gold is not None:
        # If numeric, map to letter
        if isinstance(gold, (int,)) or (isinstance(gold, str) and gold.isdigit()):
            mapped = num_to_letter(str(gold))
            if mapped:
                changes.append(f"gold: {gold} -> {mapped}")
                # write back to both metadata and meta if present
                if isinstance(rec.get("metadata"), dict):
                    rec["metadata"]["gold"] = mapped
                if isinstance(rec.get("meta"), dict):
                    rec["meta"]["gold"] = mapped
                if "gold" in rec:
                    rec["gold"] = mapped

    # Ensure content has choice markers; if not, try to rebuild from meta choices
    content = rec.get("content") or rec.get("input") or ""
    if not has_choice_markers(content):
        meta = rec.get("meta") or rec.get("metadata") or {}
        rebuilt = build_content_from_meta(meta)
        if rebuilt:
            changes.append("rebuilt content from meta.choices")
            rec["content"] = rebuilt
        else:
            # No meta choices to rebuild; attempt to normalize common numeric markers like 1) -> A)
            # Replace leading numeric choice markers 1) 2) 3) 4) with A) B) C) D)
            def repl_num_choice(match):
                num = int(match.group(1))
                if 1 <= num <= 26:
                    return f"{chr(ord('A') + num - 1)}) "
                return match.group(0)

            new_content = re.sub(r'(?m)^\s*([1-9]|1[0-9]|2[0-6])\s*[\)\.\-]\s*', repl_num_choice, content)
            if new_content != content:
                changes.append("converted numeric choice markers to letter markers")
                rec["content"] = new_content

    return rec, changes


def process_file(input_path: str, output_path: str, patch_log: str) -> Dict[str, Any]:
    total = 0
    fixed = 0
    changed_records: List[Dict[str, Any]] = []

    with open(input_path, "r", encoding="utf-8") as inf:
        lines = [l.rstrip("\n") for l in inf if l.strip()]

    for i, line in enumerate(lines):
        total += 1
        try:
            rec = json.loads(line)
        except Exception as e:
            changed_records.append({"index": i, "error": f"json_parse_error: {e}"})
            continue

        new_rec, changes = normalize_record(rec)
        if changes:
            fixed += 1
            changed_records.append({"index": i, "id": new_rec.get("id"), "changes": changes})
        # ensure we write content back in consistent fields
        if "content" not in new_rec and "input" in new_rec:
            new_rec["content"] = new_rec["input"]

        lines[i] = json.dumps(new_rec, ensure_ascii=False)

    # Write output file
    with open(output_path, "w", encoding="utf-8") as outf:
        for l in lines:
            outf.write(l + "\n")

    # Write patch log
    with open(patch_log, "w", encoding="utf-8") as pl:
        pl.write(f"Processed {input_path}\n")
        pl.write(f"Total records: {total}\n")
        pl.write(f"Fixed records: {fixed}\n\n")
        for item in changed_records:
            pl.write(json.dumps(item, ensure_ascii=False) + "\n")

    return {"total": total, "fixed": fixed, "changes": changed_records}


def main():
    parser = argparse.ArgumentParser(description="Fix ARC prompt choice markers and gold labels.")
    parser.add_argument("--input", required=True, help="Path to input jsonl prompts file")
    parser.add_argument("--output", required=True, help="Path to write fixed jsonl")
    parser.add_argument("--patch-log", required=True, help="Path to write patch log")

    args = parser.parse_args()

    result = process_file(args.input, args.output, args.patch_log)
    print(f"Processed {args.input}: total={result['total']} fixed={result['fixed']}")
    if result["fixed"]:
        print(f"Wrote fixed file to {args.output} and patch log to {args.patch_log}")


if __name__ == "__main__":
    main()