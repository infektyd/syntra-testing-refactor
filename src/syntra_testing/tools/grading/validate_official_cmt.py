#!/usr/bin/env python3
"""
Validator for prompts/suites/official_cmt.jsonl

Checks JSONL validity and required fields, and prints a brief summary.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="prompts/suites/official_cmt.jsonl", help="Path to official CMT JSONL")
    args = ap.parse_args()

    path = args.input
    total = 0
    ok = 0
    by_type = Counter()
    by_mod = Counter()

    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                total += 1
                try:
                    obj = json.loads(line)
                except Exception as e:
                    print(f"Invalid JSONL line {total}: {e}", file=sys.stderr)
                    continue
                if not isinstance(obj, dict):
                    print(f"Invalid record at line {total}: not an object", file=sys.stderr)
                    continue
                rid = obj.get("id")
                content = obj.get("content")
                meta = obj.get("metadata") or {}
                t = meta.get("type")
                m = meta.get("modality")
                if not rid or not isinstance(rid, str):
                    print(f"Missing/invalid id at line {total}", file=sys.stderr)
                    continue
                if not content or not isinstance(content, str):
                    print(f"Missing/invalid content at line {total}", file=sys.stderr)
                    continue
                if not t or t not in {"HF","ED","DMRG","QMC","VMC","PEPS","SM","Other"}:
                    print(f"Missing/invalid metadata.type at line {total}", file=sys.stderr)
                    continue
                if not m or m not in {"numeric","multiple_choice","algebraic","operator"}:
                    print(f"Missing/invalid metadata.modality at line {total}", file=sys.stderr)
                    continue
                ok += 1
                by_type[t] += 1
                by_mod[m] += 1
    except FileNotFoundError:
        print(f"ERROR: File not found: {path}", file=sys.stderr)
        sys.exit(1)

    print(f"Validated {ok}/{total} records")
    if ok:
        print("By type:")
        for k, v in sorted(by_type.items()):
            print(f"  {k}: {v}")
        print("By modality:")
        for k, v in sorted(by_mod.items()):
            print(f"  {k}: {v}")


if __name__ == "__main__":
    main()

