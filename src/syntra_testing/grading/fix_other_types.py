#!/usr/bin/env python3
import json, argparse, sys, pathlib

REMAP = {
    17: "ED", 39: "ED", 40: "ED", 47: "ED",
    23: "SM", 26: "SM", 29: "SM", 30: "SM", 31: "SM",
    32: "SM", 33: "SM", 34: "SM", 37: "SM", 38: "SM",
}

def fix_file(path: pathlib.Path, out: pathlib.Path):
    changed = 0
    kept = 0
    with path.open("r", encoding="utf-8") as f, out.open("w", encoding="utf-8") as w:
        for line in f:
            if not line.strip():
                w.write(line); continue
            try:
                rec = json.loads(line)
            except Exception:
                # HF_raw.md contains JSON objects line-by-line; write through non-JSON lines unchanged
                w.write(line); continue
            idx = rec.get("index", rec.get("idx"))
            if isinstance(idx, str) and idx.isdigit():
                idx = int(idx)
            if isinstance(idx, int) and idx in REMAP:
                desired = REMAP[idx]
                if rec.get("type") != desired:
                    rec["type"] = desired
                    changed += 1
                else:
                    kept += 1
            w.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"[INFO] {path} → {out} | changed={changed} kept={kept}")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True, help="Input file (jsonl-like)")
    ap.add_argument("--out", required=True, help="Output file (can be same as input)")
    args = ap.parse_args()

    src = pathlib.Path(args.inp)
    dst = pathlib.Path(args.out)

    # support in-place overwrite
    if src.resolve() == dst.resolve():
        tmp = src.with_suffix(src.suffix + ".tmp")
        fix_file(src, tmp)
        tmp.replace(src)
    else:
        fix_file(src, dst)

if __name__ == "__main__":
    sys.exit(main())
