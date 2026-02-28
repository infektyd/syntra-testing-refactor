# Tools/CMTExtractor/build_type_map.py
import json, argparse
import sys
from pathlib import Path

try:
    from ..common.type_utils import resolve_type
except ImportError:  # pragma: no cover - fallback when executed as standalone script
    CURRENT_DIR = Path(__file__).resolve().parent
    ROOT_DIR = CURRENT_DIR.parent.parent
    if str(ROOT_DIR) not in sys.path:
        sys.path.insert(0, str(ROOT_DIR))
    from Tools.common.type_utils import resolve_type  # type: ignore

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--suite", required=True, help="e.g. hf_cmt")
    ap.add_argument("--answers", required=True, help="prompts/suites/hf_cmt.fixed.jsonl")
    ap.add_argument("--out", required=True, help="prompts/suites/hf_cmt.type_map.json")
    args = ap.parse_args()

    out = {}
    with open(args.answers, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip(): continue
            rec = json.loads(line)
            idx = rec.get("idx") if "idx" in rec else rec.get("index")
            t = resolve_type(rec)
            out[str(idx)] = t or "OTHER"

    with open(args.out, "w", encoding="utf-8") as w:
        json.dump(out, w, indent=2, ensure_ascii=False)
    print(f"[INFO] wrote type map → {args.out}")

if __name__ == "__main__":
    main()
