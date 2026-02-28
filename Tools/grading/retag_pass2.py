# Tools/CMTExtractor/retag_pass2.py
import json, argparse

def load_map(path):
    with open(path,"r",encoding="utf-8") as f:
        return {int(k):v for k,v in json.load(f).items()}

def retag(in_path, out_path, tmap):
    out = []
    with open(in_path,"r",encoding="utf-8") as f:
        for line in f:
            if not line.strip(): continue
            rec = json.loads(line)
            idx = rec.get("idx") if "idx" in rec else rec.get("index")
            t = tmap.get(int(idx), "OTHER")
            rec["type"] = t
            out.append(rec)
    with open(out_path,"w",encoding="utf-8") as w:
        for rec in out:
            w.write(json.dumps(rec, ensure_ascii=False)+"\n")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--type-map", required=True, help="prompts/suites/hf_cmt.type_map.json")
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    tmap = load_map(args.type_map)
    retag(args.inp, args.out, tmap)
    print(f"[INFO] retagged → {args.out}")

if __name__ == "__main__":
    main()
