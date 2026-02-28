#!/usr/bin/env python3
"""
Minimal PDF→JSONL extractor for Official CMT examples.

Heuristic parsing strategy:
- Read full PDF text (pypdf), split into lines.
- Identify blocks around anchors like "Question:", "Answer modality:", and "Answer:".
- Infer type (HF|ED|DMRG|QMC|VMC|PEPS|SM|Other) from nearby context.
- Infer modality (numeric|multiple_choice|algebraic|operator) from explicit line or keywords.
- De-duplicate by normalized content hash.

Usage:
  python Tools/CMTExtractor/extract_cmt_from_pdf.py \
    --pdf resources/2510.05228v1.pdf \
    --out prompts/suites/official_cmt.jsonl \
    [--overwrite]

Notes:
- Append-safe by default (extends existing JSONL without duplicating entries).
- If --overwrite is passed, replaces the file.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import re
from datetime import datetime
from typing import Optional, Tuple

try:
    from pypdf import PdfReader
except Exception as e:
    print("ERROR: Missing dependency pypdf. Install Tools/CMTExtractor/requirements.txt", file=sys.stderr)
    raise

try:
    import regex as re2  # optional advanced regex; fallback to re if import fails
except Exception:
    re2 = None


TYPE_KEYWORDS = [
    ("ED", [r"\bExact\s*Diagonalization\b", r"\bED\b"]),
    ("QMC", [r"\bQuantum\s*Monte\s*Carlo\b", r"\bQMC\b"]),
    ("DMRG", [r"\bDMRG\b", r"\bDensity\s*Matrix\s*Renormalization\b"]),
    ("HF", [r"\bHartree\s*-?\s*Fock\b", r"\bHF\b"]),
    ("VMC", [r"\bVariational\s*Monte\s*Carlo\b", r"\bVMC\b"]),
    ("PEPS", [r"\bPEPS\b", r"\bProjected\s*Entangled\s*Pair\s*States?\b"]),
    ("SM", [r"\bStatistical\s*Mechanics\b", r"\bSM\b"]),
]

ANSWER_LINE_RE = re.compile(r"^\s*Answer\s*:\s*(.*)$", flags=re.IGNORECASE)
ANSWER_SEARCH_WINDOW = 20


def read_pdf_text(path: str) -> str:
    reader = PdfReader(path)
    parts = []
    for i, page in enumerate(reader.pages):
        try:
            parts.append(page.extract_text() or "")
        except Exception:
            # keep going even if a page fails
            parts.append("")
    return "\n".join(parts)


def compact_text(s: str) -> str:
    # Collapse whitespace but preserve backslashes (LaTeX), avoid double spaces
    # Keep simple newlines → spaces
    s = s.replace("\r", "\n")
    s = re.sub(r"\s*\n\s*", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def strip_boxed(s: str) -> str:
    # Remove simple \boxed{...} wrappers while retaining inner LaTeX
    pattern = re.compile(r"\\boxed\{(.+?)\}")
    previous = None
    current = s
    while previous != current:
        previous = current
        current = pattern.sub(r"\1", current)
    return current


def normalize_multiple_choice(text: str) -> str:
    m = re.fullmatch(r"\(?\s*([A-Za-z])\s*\)?(?:[.\)])?", text)
    if m:
        return m.group(1).lower()
    return text


def normalize_answer_text(raw: str, modality: Optional[str]) -> str:
    text = strip_boxed(raw)
    text = compact_text(text)
    if modality == "multiple_choice":
        text = normalize_multiple_choice(text)
    return text


def infer_type(context: str) -> str:
    for t, patterns in TYPE_KEYWORDS:
        for pat in patterns:
            if re.search(pat, context, flags=re.IGNORECASE):
                return t
    return "Other"


def map_modality_from_line(line: str) -> str | None:
    # Expected forms: "Answer modality: numeric", etc.
    m = re.search(r"Answer\s*modality\s*:\s*(.+)$", line, flags=re.IGNORECASE)
    if not m:
        return None
    raw = m.group(1).strip().lower()
    if any(k in raw for k in ["numeric", "number", "value"]):
        return "numeric"
    if any(k in raw for k in ["multiple", "choice", "mcq"]):
        return "multiple_choice"
    if any(k in raw for k in ["algebraic", "symbolic", "expression", "latex"]):
        return "algebraic"
    if any(k in raw for k in ["operator", "commutator", "non-commutative", "noncommutative"]):
        return "operator"
    return None


def infer_modality(question: str) -> str:
    ql = question.lower()
    # operator-like hints
    if any(k in ql for k in ["[a, b]", "commutator", "non-commutative", "noncommutative", "c^", "σx", "sigma_x", "h =", "∑", "\\sum", "\\hat{}"]):
        return "operator"
    # multiple choice cues
    if any(k in ql for k in ["which of the following", "choose", "select one", "(a)", "(b)", "(c)"]):
        return "multiple_choice"
    # algebraic cues
    if any(k in ql for k in ["latex", "algebraic", "symbolic", "expression", "simplify", "polynomial", "factor", "\\boxed"]):
        return "algebraic"
    # numeric cues
    if any(k in ql for k in ["numerical value", "value", "evaluate", "compute", "approximate", "decimal"]):
        return "numeric"
    # digits with units often numeric
    if re.search(r"\b\d+(\.\d+)?\s*(?:e[+-]?\d+)?\b", ql):
        return "numeric"
    return "algebraic"


def hash_question(s: str) -> str:
    n = re.sub(r"\s+", " ", s.strip().lower())
    return hashlib.sha1(n.encode("utf-8")).hexdigest()


def parse_blocks(lines: list[str]) -> list[dict]:
    # Collect detected problems with heuristics.
    problems = []
    pending_modality = None
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i].strip()

        # Track modality anchors even if no question yet
        if re.search(r"^\s*Answer\s*modality\s*:\s*", line, flags=re.IGNORECASE):
            pending_modality = map_modality_from_line(line)
            i += 1
            continue

        if re.search(r"^\s*Question\s*:\s*", line, flags=re.IGNORECASE):
            # Backward context for type inference
            context_start = max(0, i - 8)
            context = "\n".join(lines[context_start:i+1])
            qtype = infer_type(context)

            # Capture question body until next anchor
            qtext_parts = []
            # Extract content after 'Question:' on the same line
            qtext_parts.append(re.sub(r"^\s*Question\s*:\s*", "", line, flags=re.IGNORECASE))
            j = i + 1
            local_modality = pending_modality
            nearby_instructions = []

            while j < n:
                cur = lines[j].strip()
                if re.search(r"^\s*(Answer\s*modality\s*:|Question\s*:|Answer\s*:)", cur, flags=re.IGNORECASE):
                    # If modality appears inside the block, adopt it
                    if local_modality is None and cur.lower().startswith("answer modality"):
                        local_modality = map_modality_from_line(cur)
                    break
                # capture minor instructions about answer format
                if re.search(r"boxed\{|return your final answer|do not introduce new variables|answer format|latex", cur, flags=re.IGNORECASE):
                    nearby_instructions.append(cur)
                qtext_parts.append(cur)
                j += 1

            qtext = compact_text(" ".join(qtext_parts))

            # If modality still unknown, look forward a bit
            if local_modality is None:
                lookahead = "\n".join(lines[j:min(n, j+6)])
                mm = re.search(r"Answer\s*modality\s*:\s*(.+)$", lookahead, flags=re.IGNORECASE|re.MULTILINE)
                if mm:
                    local_modality = map_modality_from_line(mm.group(0))

            if local_modality is None:
                local_modality = infer_modality(qtext)

            # Append any detected instructions to content
            if nearby_instructions:
                instr = compact_text(" ".join(nearby_instructions))
                # Ensure instruction is included at the end in parentheses
                qtext = f"{qtext} (Instruction: {instr})"

            problems.append({
                "type": qtype,
                "modality": local_modality,
                "content": qtext,
                "anchor_index": i,
            })

            # Reset modality only if it was used directly before this question
            pending_modality = None
            i = j
            continue

        i += 1
    return problems


def collect_answer_text(lines: list[str], idx: int, first_line: str) -> str:
    parts: list[str] = []
    initial = first_line.strip()
    if initial:
        parts.append(initial)
    j = idx + 1
    n = len(lines)
    while j < n:
        cur_raw = lines[j]
        cur = cur_raw.strip()
        if not cur:
            break
        if re.search(r"^\s*(Question\s*:|Answer\s*modality\s*:|Answer\s*:)", cur, flags=re.IGNORECASE):
            break
        parts.append(cur)
        j += 1
    return " ".join(parts).strip()


def find_answer_near(lines: list[str], anchor: int, window: int = ANSWER_SEARCH_WINDOW) -> Tuple[Optional[int], Optional[str]]:
    n = len(lines)
    # Prefer answers that appear after the question within the window.
    for offset in range(0, window + 1):
        idx = anchor + offset
        if idx >= n:
            break
        m = ANSWER_LINE_RE.match(lines[idx])
        if m:
            return idx, collect_answer_text(lines, idx, m.group(1))
    # Fallback to the closest preceding answer if none found after.
    for offset in range(1, window + 1):
        idx = anchor - offset
        if idx < 0:
            break
        m = ANSWER_LINE_RE.match(lines[idx])
        if m:
            return idx, collect_answer_text(lines, idx, m.group(1))
    return None, None


def locate_answers(lines: list[str], problems: list[dict]) -> dict[int, str]:
    matches: dict[int, str] = {}
    for p in problems:
        anchor = p.get("anchor_index")
        if not isinstance(anchor, int):
            continue
        _, raw = find_answer_near(lines, anchor, ANSWER_SEARCH_WINDOW)
        if raw is not None:
            matches[anchor] = raw
    return matches


def load_existing_hashes(out_path: str) -> set[str]:
    hashes = set()
    if not os.path.exists(out_path):
        return hashes
    try:
        with open(out_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except Exception:
                    # skip non-JSON lines defensively
                    continue
                content = obj.get("content")
                if isinstance(content, str):
                    hashes.add(hash_question(content))
    except Exception:
        pass
    return hashes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", required=True, help="Path to local CMT PDF (e.g., resources/2510.05228v1.pdf)")
    ap.add_argument("--out", required=True, help="Output JSONL path (e.g., prompts/suites/official_cmt.jsonl)")
    ap.add_argument("--overwrite", action="store_true", help="Overwrite output file instead of appending")
    ap.add_argument("--answers-out", help="Optional answers JSONL path")
    args = ap.parse_args()

    if not os.path.isfile(args.pdf):
        print(f"ERROR: PDF not found: {args.pdf}. Place it under resources/ and retry.", file=sys.stderr)
        sys.exit(1)

    print(f"Reading PDF: {args.pdf}")
    raw_text = read_pdf_text(args.pdf)
    if not raw_text or not raw_text.strip():
        print("ERROR: No extractable text found in PDF.", file=sys.stderr)
        sys.exit(1)

    lines = raw_text.splitlines()
    problems = parse_blocks(lines)

    if not problems:
        print("ERROR: No problems identified. Please verify the PDF version/format.", file=sys.stderr)
        sys.exit(1)

    answers_line_count = 0
    anchor_to_answer: dict[int, str] = {}
    if args.answers_out:
        answers_line_count = sum(1 for line in lines if ANSWER_LINE_RE.match(line))
        anchor_to_answer = locate_answers(lines, problems)

    # Dedup vs existing content if appending
    existing_hashes = set()
    if not args.overwrite:
        existing_hashes = load_existing_hashes(args.out)

    # Prepare ids by type
    counters: dict[str, int] = {}
    out_records = []
    seen_hashes = set(existing_hashes)
    answer_records = []
    matched_count = len(anchor_to_answer)

    for p in problems:
        content = p["content"]
        h = hash_question(content)
        if h in seen_hashes:
            continue
        seen_hashes.add(h)

        ptype = p["type"] or "Other"
        counters[ptype] = counters.get(ptype, 0) + 1
        pid = f"cmt_{ptype.lower()}_{counters[ptype]:02d}"
        rec = {
            "id": pid,
            "content": content,
            "metadata": {
                "suite": "official_cmt",
                "type": ptype,
                "modality": p["modality"],
                "source": "arXiv_2510.05228v1_pdf"
            }
        }
        out_records.append(rec)

        if args.answers_out:
            anchor = p.get("anchor_index")
            raw_answer = anchor_to_answer.get(anchor)
            if raw_answer is not None:
                normalized = normalize_answer_text(raw_answer, p.get("modality"))
                answer_records.append({
                    "id": pid,
                    "modality": p.get("modality"),
                    "answer": normalized
                })
            else:
                print(f"warning: no answer matched for question id {pid}", file=sys.stderr)

    if not out_records:
        if args.answers_out:
            print(f"answers: {answers_line_count}, questions: {len(problems)}, matched: {matched_count}", file=sys.stderr)
            print("extracted problems: 0, answers: 0", file=sys.stderr)
        print("No new problems to write (all de-duplicated).", file=sys.stderr)
        sys.exit(0)

    # Ensure dir exists
    os.makedirs(os.path.dirname(args.out), exist_ok=True)

    mode = "w" if args.overwrite else ("a" if os.path.exists(args.out) else "w")
    with open(args.out, mode, encoding="utf-8") as f:
        for rec in out_records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    if args.answers_out:
        os.makedirs(os.path.dirname(args.answers_out) or ".", exist_ok=True)
        answer_mode = "w" if args.overwrite else ("a" if os.path.exists(args.answers_out) else "w")
        with open(args.answers_out, answer_mode, encoding="utf-8") as af:
            for rec in answer_records:
                af.write(json.dumps(rec, ensure_ascii=False) + "\n")
        print(f"answers: {answers_line_count}, questions: {len(problems)}, matched: {matched_count}", file=sys.stderr)
    print(f"extracted problems: {len(out_records)}, answers: {len(answer_records)}", file=sys.stderr)
    print(f"Wrote {len(out_records)} problems → {args.out}")
    if args.answers_out and answer_records:
        print(f"Wrote {len(answer_records)} answers → {args.answers_out}")


if __name__ == "__main__":
    main()
