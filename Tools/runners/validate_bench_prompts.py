#!/usr/bin/env python3
"""
Validator for SYNTRA benchmark prompts/answers across active suites.
Scans Benchmarks/, prompts/, resources/ and normalizes to a common schema.
Produces Tools/validation_report.md and Tools/validation_report.json.
Exit code:
  0 -> no blocking errors
  1 -> blocking errors found (duplicates, empty/too-short questions,
      invalid MC answers, GSM8K non-numeric)

CLI:
  python3 Tools/validate_bench_prompts.py --suites all
  Optional:
    --suite CMT|ARC|GSM8K (ARC covers both Challenge/Easy)
    --fix-gsm8k-numeric  (emit normalized answers alongside)
    --fail-on-warn       (treat warnings as blocking)
"""
import sys
import re
import json
import csv
import html
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional, Tuple, Iterable
from pathlib import Path

# Path setup
ROOT = Path(__file__).resolve().parents[2]
TOOLS_DIR = ROOT / "Tools"

SUITE_PATH_HINTS: Dict[str, List[str]] = {
    "CMT": [
        "Benchmarks/CMT", "prompts/cmt", "resources/cmt",
        "Tools/CMTExtractor/out", "resources/hf_cmt", "prompts/suites"
    ],
    "ARC-Challenge": ["Benchmarks/ARC", "prompts/arc", "resources/arc"],
    "ARC-Easy": ["Benchmarks/ARC", "prompts/arc", "resources/arc"],
    "GSM8K": [
        "Benchmarks/GSM8K", "prompts/gsm8k", "resources/gsm8k",
        "Benchmarks/GSM8K/stubs"
    ],
}

ACTIVE_SUITES = ["CMT", "ARC-Challenge", "ARC-Easy", "GSM8K"]

STUB_RE = re.compile(
    r"\b(TODO|FIXME|PLACEHOLDER|DUMMY|LOREM|STUB|FILL ME|TBD)\b", re.I
)
# integers with commas or decimals
NUM_RE = re.compile(r"(?<![A-Za-z])(?:(?:\d{1,3}(?:,\d{3})+)|\d+)(?:\.\d+)?")


# ---------- Utilities ----------

def strip_md_html(text: str) -> str:
    if not isinstance(text, str):
        return ""
    t = html.unescape(text)
    # Remove code fences/inline backticks
    t = re.sub(r"```[\s\S]*?```", " ", t)
    t = re.sub(r"`[^`]*`", " ", t)
    # Remove HTML tags
    t = re.sub(r"<[^>]+>", " ", t)
    # Remove markdown links/images
    t = re.sub(r"!\[[^\]]*\]\([^\)]*\)", " ", t)
    t = re.sub(r"\[[^\]]*\]\([^\)]*\)", " ", t)
    # Remove common markdown markers
    t = re.sub(r"[#*_>~\-]+", " ", t)
    # Collapse whitespace
    t = re.sub(r"\s+", " ", t).strip()
    return t


def extract_final_number(text: str) -> Optional[str]:
    if not isinstance(text, str) or not text.strip():
        return None
    matches = list(NUM_RE.finditer(text))
    if not matches:
        return None
    last = matches[-1].group(0)
    # strip commas
    return last.replace(",", "")


# ---------- Schema ----------
@dataclass
class NormalizedRecord:
    id: str
    suite: str  # CMT | ARC-Challenge | ARC-Easy | GSM8K
    question: str
    choices: List[Dict[str, str]]  # [{label: 'A', text: '...'}] or []
    answer: str
    source_path: str
    split: Optional[str]  # train|dev|test|validation|null
    meta: Dict[str, Any]
    # GSM8K extras (optional)
    raw_answer: Optional[str] = None
    normalized_answer: Optional[str] = None


# ---------- File discovery ----------

SUPPORTED_EXT = (".jsonl", ".json", ".csv")


def discover_files_for_suite(suite: str) -> List[Path]:
    files: List[Path] = []
    for rel in SUITE_PATH_HINTS.get(suite, []):
        p = ROOT / rel
        if not p.exists():
            continue
        if p.is_file():
            if p.suffix.lower() in SUPPORTED_EXT:
                files.append(p)
            continue
        # recursively find supported
        for ext in SUPPORTED_EXT:
            files.extend(p.rglob(f"*{ext}"))
    return sorted({f for f in files})


# ---------- Loaders ----------

def load_jsonl(path: Path) -> Iterable[Dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except Exception:
                continue


def load_json(path: Path) -> Iterable[Dict[str, Any]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    if isinstance(data, list):
        return data
    elif isinstance(data, dict):
        # try common keys
        for key in ("data", "records", "items"):
            if key in data and isinstance(data[key], list):
                return data[key]
        return [data]
    return []


def load_csv(path: Path) -> Iterable[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(row)
    except Exception:
        return []
    return rows


def iter_records(path: Path) -> Iterable[Dict[str, Any]]:
    suf = path.suffix.lower()
    if suf == ".jsonl":
        return load_jsonl(path)
    if suf == ".json":
        return load_json(path)
    if suf == ".csv":
        return load_csv(path)
    return []


# ---------- Heuristics to map files to suite ----------

def guess_suite_from_path(
    path: Path, default_suite: Optional[str] = None
) -> Optional[str]:
    p = str(path).lower()
    if "arc" in p:
        # decide easy vs challenge by filename or subset
        if any(tag in p for tag in ["easy", "_e_", "-easy"]):
            return "ARC-Easy"
        if any(tag in p for tag in ["challenge", "_c_", "-challenge"]):
            return "ARC-Challenge"
        # fallback to dir name
        if "easy" in p:
            return "ARC-Easy"
        return "ARC-Challenge"
    if "gsm8k" in p:
        return "GSM8K"
    if "cmt" in p or "hf_cmt" in p:
        return "CMT"
    return default_suite


# ---------- Normalizers per suite ----------

def normalize_arc(
    rec: Dict[str, Any], suite: str, source_path: Path
) -> Optional[NormalizedRecord]:
    # Expected keys in stubs: id, question, choices:[{label,text}],
    # answerKey, subset, split
    rid = str(rec.get("id", "")).strip()
    q = rec.get("question") or rec.get("prompt") or ""
    choices = rec.get("choices") or []
    answer = str(rec.get("answerKey", rec.get("answer", "")).strip())
    # Require minimal fields for ARC prompt sources
    if not q or not choices or not answer:
        return None
    # Normalize choices list of dicts
    norm_choices: List[Dict[str, str]] = []
    if isinstance(choices, list):
        for c in choices:
            if isinstance(c, dict) and "label" in c and "text" in c:
                norm_choices.append({
                    "label": str(c["label"]).strip(),
                    "text": str(c["text"]).strip()
                })
            elif isinstance(c, (list, tuple)) and len(c) >= 2:
                norm_choices.append({
                    "label": str(c[0]).strip(),
                    "text": str(c[1]).strip()
                })
    split = rec.get("split") or rec.get("dataset_split")
    meta = {
        k: v for k, v in rec.items()
        if k not in {
            "id", "question", "prompt",
            "choices", "answerKey", "answer", "split"
        }
    }
    return NormalizedRecord(
        id=rid,
        suite=suite,
        question=str(q),
        choices=norm_choices,
        answer=answer,
        source_path=str(source_path.relative_to(ROOT)),
        split=str(split) if split else None,
        meta=meta,
    )


def normalize_gsm8k(
    rec: Dict[str, Any], suite: str, source_path: Path
) -> Optional[NormalizedRecord]:
    rid = str(rec.get("id", "")).strip()
    q = rec.get("question") or rec.get("prompt") or ""
    raw_answer = rec.get("answer") or rec.get("solution") or ""
    norm_num = extract_final_number(str(raw_answer))
    answer = norm_num or ""
    split = rec.get("split") or rec.get("dataset_split") or \
        ("test" if "test" in str(source_path).lower() else None)
    meta = {
        k: v for k, v in rec.items()
        if k not in {
            "id", "question", "prompt", "answer", "solution", "split"
        }
    }
    return NormalizedRecord(
        id=rid,
        suite=suite,
        question=str(q),
        choices=[],
        answer=answer,
        source_path=str(source_path.relative_to(ROOT)),
        split=str(split) if split else None,
        meta=meta,
        raw_answer=str(raw_answer) if raw_answer is not None else None,
        normalized_answer=norm_num,
    )


def normalize_cmt(
    rec: Dict[str, Any], suite: str, source_path: Path
) -> Optional[NormalizedRecord]:
    # Only support MC-style CMT here; skip algebraic/NLP without choices.
    rid = str(rec.get("id", rec.get("cmt_id", "")).strip())
    q = rec.get("question") or rec.get("prompt") or ""
    choices = rec.get("choices") or []
    ans_key = rec.get("answerKey", rec.get("answer", ""))
    if choices and ans_key:
        norm_choices: List[Dict[str, str]] = []
        if isinstance(choices, list):
            for c in choices:
                if isinstance(c, dict) and "label" in c and "text" in c:
                    norm_choices.append({
                        "label": str(c["label"]).strip(),
                        "text": str(c["text"]).strip()
                    })
        split = rec.get("split") or rec.get("dataset_split")
        meta = {
            k: v for k, v in rec.items()
            if k not in {
                "id", "cmt_id", "question", "prompt", "choices",
                "answerKey", "answer", "split"
            }
        }
        return NormalizedRecord(
            id=rid,
            suite=suite,
            question=str(q),
            choices=norm_choices,
            answer=str(ans_key).strip(),
            source_path=str(source_path.relative_to(ROOT)),
            split=str(split) if split else None,
            meta=meta,
        )
    # Not an MC CMT record; skip.
    return None


# ---------- Validation ----------
@dataclass
class Issue:
    category: str
    id: str
    suite: str
    source_path: str
    detail: str


def validate_records(
    records: List[NormalizedRecord]
) -> Tuple[Dict[str, Any], List[Issue]]:
    issues: List[Issue] = []
    stats: Dict[str, Dict[str, int]] = {}

    # helper to bump stats per suite
    def bump(suite: str, key: str, inc: int = 1):
        stats.setdefault(suite, {})
        stats[suite][key] = stats[suite].get(key, 0) + inc

    # Track duplicates within suite+split+source
    seen: Dict[Tuple[str, Optional[str], str, str], int] = {}

    for r in records:
        bump(r.suite, "total_items")

        # Question checks
        q_clean = strip_md_html(r.question)
        if not q_clean or len(q_clean) < 10:
            issues.append(
                Issue("invalid_items", r.id, r.suite, r.source_path,
                      "empty or too short question"))
            bump(r.suite, "invalid_items")

        # Stub detection
        if STUB_RE.search(r.question or ""):
            issues.append(
                Issue("stub_items", r.id, r.suite, r.source_path,
                      "stub token in question"))
            bump(r.suite, "stub_items")

        # ID
        if not r.id:
            issues.append(
                Issue("invalid_items", r.id, r.suite, r.source_path,
                      "missing id"))
            bump(r.suite, "invalid_items")

        key = (r.suite, r.split, r.source_path, r.id)
        if key in seen:
            issues.append(
                Issue("duplicate_ids", r.id, r.suite, r.source_path,
                      "duplicate id within suite+split+source"))
            bump(r.suite, "duplicate_ids")
        else:
            seen[key] = 1

        # Suite-specific
        if r.suite in ("ARC-Challenge", "ARC-Easy", "CMT"):
            # MC validation
            labels = [c.get("label") for c in r.choices if isinstance(c, dict)]
            if not (2 <= len(labels) <= 10):
                issues.append(
                    Issue("bad_answers", r.id, r.suite, r.source_path,
                          f"choices count {len(labels)} out of range"))
                bump(r.suite, "bad_answers")
            # labels contiguous A..N
            if labels:
                exp = [chr(ord('A') + i) for i in range(len(labels))]
                if labels != exp:
                    issues.append(
                        Issue("bad_answers", r.id, r.suite, r.source_path,
                              f"labels not contiguous A..: {labels}"))
                    bump(r.suite, "bad_answers")
            # answer key valid
            if r.answer and labels and r.answer not in labels:
                issues.append(
                    Issue("bad_answers", r.id, r.suite, r.source_path,
                          f"answer '{r.answer}' not in labels {labels}"))
                bump(r.suite, "bad_answers")
        elif r.suite == "GSM8K":
            if not r.normalized_answer:
                issues.append(
                    Issue("gsm8k_non_numeric", r.id, r.suite, r.source_path,
                          "no numeric answer found"))
                bump(r.suite, "gsm8k_non_numeric")

    return stats, issues


# ---------- Reporting ----------

def write_reports(stats: Dict[str, Dict[str, int]], issues: List[Issue]):
    TOOLS_DIR.mkdir(parents=True, exist_ok=True)
    # JSON report
    issues_json = [asdict(i) for i in issues]
    (TOOLS_DIR / "validation_report.json").write_text(json.dumps({
        "stats": stats,
        "issues": issues_json
    }, indent=2), encoding="utf-8")

    # MD report
    def suite_stat(suite: str, key: str) -> int:
        return stats.get(suite, {}).get(key, 0)

    lines: List[str] = [
        "# Benchmark Validation Report\n",
        "This report summarizes schema and content checks for active suites.\n"
    ]

    for suite in ACTIVE_SUITES:
        total = suite_stat(suite, "total_items")
        invalid = suite_stat(suite, "invalid_items")
        stub = suite_stat(suite, "stub_items")
        dup = suite_stat(suite, "duplicate_ids")
        bad = suite_stat(suite, "bad_answers")
        gbad = suite_stat(suite, "gsm8k_non_numeric")
        lines.append(f"\n## {suite}\n")
        lines.append(
            "| total_items | invalid_items | stub_items | duplicate_ids | "
            "bad_answers | gsm8k_non_numeric |\n"
        )
        lines.append(
            "|-------------|---------------|------------|---------------|"
            "-------------|-------------------|\n"
        )
        lines.append(
            f"| {total} | {invalid} | {stub} | {dup} | {bad} | {gbad} |\n"
        )

        # Example issues per category
        issue_cats = [
            "invalid_items", "stub_items", "duplicate_ids",
            "bad_answers", "gsm8k_non_numeric"
        ]
        for cat in issue_cats:
            examples = [
                i for i in issues if i.suite == suite and i.category == cat
            ][:10]
            if examples:
                lines.append(
                    f"\n### {cat} (first {len(examples)} examples)\n"
                )
                for ex in examples:
                    lines.append(
                        f"- {ex.source_path} :: id={ex.id} — {ex.detail}"
                    )

    (TOOLS_DIR / "validation_report.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )


# ---------- Main ----------

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--suites", default="all", help="all or comma list")
    parser.add_argument(
        "--suite", choices=["CMT", "ARC", "GSM8K"], default=None, nargs='?'
    )
    parser.add_argument("--fix-gsm8k-numeric", action="store_true")
    parser.add_argument(
        "--fail_on_warn", dest="fail_on_warn", action="store_true"
    )
    args = parser.parse_args()

    selected: List[str]
    if args.suite:
        if args.suite == "ARC":
            selected = ["ARC-Challenge", "ARC-Easy"]
        else:
            selected = [args.suite]
    elif args.suites == "all":
        selected = ACTIVE_SUITES
    else:
        chunks = [s.strip() for s in args.suites.split(",") if s.strip()]
        # expand ARC umbrella
        selected = []
        for s in chunks:
            if s.upper() == "ARC":
                selected.extend(["ARC-Challenge", "ARC-Easy"])
            else:
                selected.append(s)

    all_norm: List[NormalizedRecord] = []

    for suite in selected:
        files = discover_files_for_suite(suite)
        # Filter files by heuristic (avoid unrelated .json/.csv)
        suite_files = [
            f for f in files if guess_suite_from_path(f, suite) == suite
        ]
        for path in suite_files:
            # Skip Arrow/Parquet or HF datasets we can't parse here
            if any(path.name.endswith(x) for x in [".arrow", ".parquet"]):
                continue
            # Iterate records
            for rec in iter_records(path):
                if not isinstance(rec, dict):
                    continue
                norm: Optional[NormalizedRecord] = None
                # Determine suite per-record if needed
                sguess = guess_suite_from_path(path, suite)
                if sguess in ("ARC-Challenge", "ARC-Easy"):
                    # allow subset field to refine
                    subset = str(rec.get("subset", "")).lower()
                    s_actual = "ARC-Challenge" if "challenge" in subset else \
                        ("ARC-Easy" if "easy" in subset else sguess)
                    norm = normalize_arc(rec, s_actual, path)
                elif sguess == "GSM8K":
                    norm = normalize_gsm8k(rec, "GSM8K", path)
                elif sguess == "CMT":
                    norm = normalize_cmt(rec, "CMT", path)
                if norm:
                    all_norm.append(norm)
                else:
                    # Not recognized structure; warn but don't block
                    pass

    stats, issues = validate_records(all_norm)
    write_reports(stats, issues)

    # Blocking conditions
    blocking_cats = {
        "duplicate_ids", "invalid_items",
        "bad_answers", "gsm8k_non_numeric"
    }
    blocking = any(i.category in blocking_cats for i in issues)

    if args.fail_on_warn:
        blocking = blocking or any(
            i.category not in blocking_cats for i in issues
        )

    # Optionally write normalized answers for GSM8K alongside sources
    # (non-destructive: emit .normalized.jsonl next to file)
    if args.fix_gsm8k_numeric:
        by_source: Dict[str, List[NormalizedRecord]] = {}
        for r in all_norm:
            if r.suite == "GSM8K":
                by_source.setdefault(r.source_path, []).append(r)
        for src_rel, recs in by_source.items():
            out_path = ROOT / (src_rel + ".normalized.jsonl")
            try:
                with out_path.open("w", encoding="utf-8") as f:
                    for r in recs:
                        f.write(json.dumps({
                            "id": r.id,
                            "question": r.question,
                            "answer": r.raw_answer,
                            "normalized_answer": r.normalized_answer
                        }, ensure_ascii=False) + "\n")
            except Exception:
                pass

    # Print quick summary
    print("Validation complete. Report: Tools/validation_report.md")
    for suite in selected:
        sstats = stats.get(suite, {})
        print(
            f"- {suite}: total={sstats.get('total_items', 0)}, "
            f"invalid={sstats.get('invalid_items', 0)}, "
            f"stubs={sstats.get('stub_items', 0)}, "
            f"dup={sstats.get('duplicate_ids', 0)}, "
            f"bad={sstats.get('bad_answers', 0)}, "
            f"gsm8k_non_numeric={sstats.get('gsm8k_non_numeric', 0)}"
        )

    sys.exit(1 if blocking else 0)


if __name__ == "__main__":
    main()
