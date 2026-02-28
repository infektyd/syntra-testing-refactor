#!/usr/bin/env python3
"""
analyze_results.py — Auto-discover SYNTRA benchmark results and compute stats.

Usage:
  python3 Tools/analyze_results.py runs/ \
    [--bootstrap 5000] [--seed 42] [--out_dir runs/stats] \
    [--alpha 0.05] [--target_power 0.80]

Behavior:
- Recursively scans <runs_dir> for files named "graded.*.jsonl" (case-insensitive).
- Treats the immediate parent directory name as the suite (e.g., runs/ARC/graded.syntra.jsonl → suite=ARC).
- Heuristically classifies variant as "syntra" or "baseline" from the filename:
    * syntra keywords: syntra, orchestration, tri, modivalondrift
    * baseline keywords: base, baseline, vanilla, control, raw
  Unrecognized variants are kept as their filename stem (e.g., "gpt5mini").
- Reads each JSONL into a mapping id → bool(correct), where id and label are auto-detected among common fields.

Outputs:
- <out_dir>/stats_report.md — human-friendly Markdown
- <out_dir>/stats_summary.json — structured JSON with all computed metrics

Statistics:
- Per-suite accuracy for each variant with Wilson 95% CI.
- If both "syntra" and "baseline" exist for a suite, computes:
    * Paired exact McNemar p-value
    * Δ accuracy (syntra − baseline) with approximate CI (±1.96*sqrt(discordant)/n)
    * Bootstrap 95% CI for Δ (paired resampling over items)
    * Effect size for proportions (Cohen's h)
    * B win-rate among discordants with Wilson 95% CI
    * Pairing integrity audit (missing IDs, duplicates; JSON + concise Markdown)
    * Power guidance: required discordants & estimated paired N
- Overall summaries:
    * Micro-average across items (pooled across suites where both variants exist)
    * Macro-average across suites (unweighted mean of per-suite accuracies)
"""

import os, json, math, glob, random, argparse
from typing import Dict, Any, List, Tuple, Optional
from collections import defaultdict

ID_CANDIDATES = ["id", "item_id", "prompt_id", "index", "qid", "key"]
LABEL_CANDIDATES = ["correct", "is_correct", "pass", "passed", "label", "score", "success"]
TYPE_CANDIDATES = ["type", "problem_type", "category", "question_type"]

SYNTRA_KEYS = ["syntra", "orchestration", "tri", "modivalondrift"]
BASE_KEYS   = ["baseline", "base", "vanilla", "control", "raw"]

def detect_field(record: Dict[str, Any], candidates: List[str]) -> Optional[str]:
    for c in candidates:
        if c in record:
            return c
    return None

def to_bool(x: Any) -> Optional[bool]:
    if isinstance(x, bool):
        return x
    if isinstance(x, (int, float)):
        if x == 1: return True
        if x == 0: return False
        if 0 <= x <= 1: return bool(x >= 0.5)
        return None
    if isinstance(x, str):
        s = x.strip().lower()
        if s in ("1", "true", "t", "yes", "y", "pass", "passed", "correct", "success"): return True
        if s in ("0", "false", "f", "no", "n", "fail", "failed", "incorrect"): return False
        try:
            v = float(s)
            if v == 1: return True
            if v == 0: return False
            if 0 <= v <= 1: return bool(v >= 0.5)
        except:
            pass
    return None

def read_jsonl(path: str) -> Tuple[Dict[str, bool], str, str, Dict[str, str], Dict[str, Any]]:
    results: Dict[str, bool] = {}
    types: Dict[str, str] = {}  # id -> type
    id_field = None
    label_field = None
    type_field = None
    missing_pf_ids: List[str] = []
    missing_boxed_ids: List[str] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line: continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if id_field is None:
                id_field = detect_field(rec, ID_CANDIDATES)
            if label_field is None:
                label_field = detect_field(rec, LABEL_CANDIDATES)
            if type_field is None:
                type_field = detect_field(rec, TYPE_CANDIDATES)
            if id_field is None or label_field is None:
                continue
            rid = str(rec.get(id_field))
            val = to_bool(rec.get(label_field))
            if val is None:
                continue
            results[rid] = val
            if type_field:
                types[rid] = str(rec.get(type_field, "Unknown"))
            # Protocol auditing (CMT)
            params = rec.get("parameters")
            funcs = rec.get("functions")
            if ((not isinstance(params, str)) or params.strip() == "" or
                (not isinstance(funcs, str)) or funcs.strip() == ""):
                if rid:
                    missing_pf_ids.append(rid)
            parse_error = rec.get("parse_error")
            if isinstance(parse_error, str) and parse_error == "missing_boxed_answer":
                if rid:
                    missing_boxed_ids.append(rid)
    if id_field is None or label_field is None:
        raise ValueError(f"Could not detect id/label fields in {path}")
    protocol_meta = {
        "total": len(results),
        "missing_pf_ids": missing_pf_ids,
        "missing_boxed_ids": missing_boxed_ids,
    }
    return results, id_field, label_field, types, protocol_meta

def wilson_ci(successes: int, n: int, z: float = 1.96) -> Tuple[float, float]:
    if n == 0: return (0.0, 0.0)
    phat = successes / n
    denom = 1 + z*z/n
    center = (phat + z*z/(2*n)) / denom
    half = z * math.sqrt((phat*(1-phat) + z*z/(4*n)) / n) / denom
    return (max(0.0, center - half), min(1.0, center + half))

def mcnemar_exact_p(n01: int, n10: int) -> float:
    # two-sided exact binomial test with p=0.5
    n = n01 + n10
    if n == 0: return 1.0
    k = min(n01, n10)
    from math import comb
    s = 0.0
    for i in range(0, k+1):
        s += comb(n, i) * (0.5**i) * (0.5**(n-i))
    p = 2.0 * s
    return min(1.0, p)

def cohens_h(p1: float, p2: float) -> float:
    # Cohen's h (for proportions). Positive means p1>p2.
    from math import asin, sqrt
    return 2*(asin(sqrt(p1)) - asin(sqrt(p2)))

def wilson_ci_int(successes: int, n: int) -> tuple[float, float]:
    """Convenience wrapper to return Wilson CI for a proportion as floats (0..1)."""
    return wilson_ci(successes, n)

def power_required_discordants(p: float, alpha: float, power: float) -> int:
    """
    Approximate required discordant count (D_required) to detect win-rate p vs 0.5
    with two-sided alpha and desired power, using normal approx for a binomial test.
    n ≈ ((z_{alpha/2}*sqrt(0.25) + z_{power}*sqrt(p*(1-p)))**2) / (p-0.5)**2
    Return ceil(n). Clamp if p==0.5 → return a large sentinel (e.g., 10**9).
    """
    from math import sqrt, ceil
    if p <= 0.0 or p >= 1.0 or abs(p - 0.5) < 1e-9:
        return 10**9
    # z-values: use 1.96 for alpha=0.05 two-sided; for general alpha & power: invert normal CDF.
    # Implement a small helper for inverse CDF (erfinv-based).
    def z_for(prob: float) -> float:
        # prob is one-sided tail complement: e.g., 1 - alpha/2 for two-sided
        # Use inverse error function approximation
        import math
        # Clamp to (0,1)
        p = min(max(prob, 1e-12), 1-1e-12)
        # Approximate inverse normal CDF (Acklam)
        a1=-3.969683028665376e+01; a2= 2.209460984245205e+02; a3=-2.759285104469687e+02
        a4= 1.383577518672690e+02; a5=-3.066479806614716e+01; a6= 2.506628277459239e+00
        b1=-5.447609879822406e+01; b2= 1.615858368580409e+02; b3=-1.556989798598866e+02
        b4= 6.680131188771972e+01; b5=-1.328068155288572e+01
        c1=-7.784894002430293e-03; c2=-3.223964580411365e-01; c3=-2.400758277161838e+00
        c4=-2.549732539343734e+00; c5= 4.374664141464968e+00; c6= 2.938163982698783e+00
        d1= 7.784695709041462e-03; d2= 3.224671290700398e-01; d3= 2.445134137142996e+00
        d4= 3.754408661907416e+00
        # Beasley-Springer/Moro/Acklam split
        plow = 0.02425; phigh = 1 - plow
        if p < plow:
            q = math.sqrt(-2*math.log(p))
            return (((((c1*q+c2)*q+c3)*q+c4)*q+c5)*q+c6)/((((d1*q+d2)*q+d3)*q+d4)*q+1)
        if phigh < p:
            q = math.sqrt(-2*math.log(1-p))
            return -(((((c1*q+c2)*q+c3)*q+c4)*q+c5)*q+c6)/((((d1*q+d2)*q+d3)*q+d4)*q+1)
        q = p - 0.5
        r = q*q
        return (((((a1*r+a2)*r+a3)*r+a4)*r+a5)*r+a6)*q/(((((b1*r+b2)*r+b3)*r+b4)*r+b5)*r+1)

    z_alpha = z_for(1 - alpha/2.0)
    z_beta  = z_for(power)
    num = (z_alpha*0.5 + z_beta*((p*(1-p))**0.5))**2
    den = (p - 0.5)**2
    return int(ceil(num / den))

def classify_variant(fname: str) -> str:
    low = fname.lower()
    for k in SYNTRA_KEYS:
        if k in low: return "syntra"
    for k in BASE_KEYS:
        if k in low: return "baseline"
    # fallback to stem between 'graded.' and '.jsonl'
    stem = low
    if "graded." in low and low.endswith(".jsonl"):
        stem = low.split("graded.",1)[1].rsplit(".jsonl",1)[0]
    return stem or "unknown"

def bootstrap_delta(items: List[Tuple[bool, bool]], B: int, rng: random.Random) -> Tuple[float, float]:
    # items: list of (baseline_correct, syntra_correct) for paired ids
    n = len(items)
    if n == 0:
        return (0.0, 0.0)
    deltas = []
    for _ in range(B):
        accA = accB = 0
        for _i in range(n):
            b, s = items[rng.randrange(n)]
            if b: accA += 1
            if s: accB += 1
        deltas.append((accB - accA) / n)
    deltas.sort()
    lo = deltas[int(0.025*B)]
    hi = deltas[int(0.975*B)-1]
    return lo, hi

def get_report_filename(suites: List[str]) -> str:
    """Generate a descriptive filename based on the suites being analyzed."""
    if not suites:
        return "stats_report.md"
    
    # Map suite names to shorter identifiers
    suite_map = {
        "arc_challenge": "arc",
        "gsm8k": "gsm8k",
        "cmt": "cmt"
    }
    
    # Get short names for found suites
    short_names = []
    for suite in sorted(suites):
        short_names.append(suite_map.get(suite, suite))
    
    # Create filename
    if len(short_names) == 1:
        return f"stats_{short_names[0]}.md"
    else:
        return f"stats_{'_'.join(short_names)}.md"

def process_timestamp_folder(timestamp: str, files: List[str], runs_dir: str, args, rng: random.Random):
    """Process all graded files in a single timestamp folder and generate reports."""
    out_dir = os.path.join(runs_dir, timestamp)
    os.makedirs(out_dir, exist_ok=True)

    # suite is parent directory name
    by_suite: Dict[str, Dict[str, Dict[str, bool]]] = defaultdict(dict)  # suite -> variant -> {id->bool}
    by_suite_type: Dict[str, Dict[str, Dict[str, Dict[str, bool]]]] = defaultdict(lambda: defaultdict(dict))  # suite -> variant -> type -> {id->bool}
    type_map: Dict[str, Dict[str, Dict[str, str]]] = defaultdict(dict)  # suite -> variant -> {id->type}
    meta: Dict[str, Dict[str, Any]] = defaultdict(dict)  # suite -> variant -> meta info

    for f in files:
        suite = os.path.basename(os.path.dirname(os.path.dirname(f))) or "root"
        variant = classify_variant(os.path.basename(f))
        try:
            results, id_field, label_field, types, protocol_meta = read_jsonl(f)
        except Exception as e:
            # skip unreadable
            continue
        by_suite[suite][variant] = results
        type_map[suite][variant] = types

        # Group by type
        for item_id, is_correct in results.items():
            item_type = types.get(item_id, "Unknown")
            if item_type not in by_suite_type[suite][variant]:
                by_suite_type[suite][variant][item_type] = {}
            by_suite_type[suite][variant][item_type][item_id] = is_correct

        meta[suite][variant] = {
            "path": f,
            "id_field": id_field,
            "label_field": label_field,
            "n": len(results),
            "protocol": protocol_meta,
        }

    # Prepare report structures
    report_lines: List[str] = []
    summary = {"timestamp": timestamp, "suites": {}, "overall": {}}

    report_lines.append(f"# SYNTRA Preliminary Stats - {timestamp}\n")

    # Per-suite
    comparable_suites = []  # suites with both baseline and syntra
    micro_pool_items: List[Tuple[bool, bool]] = []
    macro_acc_syntra = []
    macro_acc_base = []

    for suite in sorted(by_suite.keys()):
        variants = by_suite[suite]
        protocol_details_by_variant: Dict[str, Dict[str, Any]] = {}
        suite_pf_union: set[str] = set()
        suite_box_union: set[str] = set()
        if suite.lower() == "cmt":
            for variant_name, meta_info in meta.get(suite, {}).items():
                protocol_meta = meta_info.get("protocol", {}) or {}
                missing_pf_ids: List[str] = list(protocol_meta.get("missing_pf_ids", []))
                missing_boxed_ids: List[str] = list(protocol_meta.get("missing_boxed_ids", []))
                total_items = int(protocol_meta.get("total", 0))
                present_pf = max(total_items - len(missing_pf_ids), 0)
                protocol_details_by_variant[variant_name] = {
                    "total": total_items,
                    "present_pf": present_pf,
                    "missing_pf": len(missing_pf_ids),
                    "missing_boxed": len(missing_boxed_ids),
                    "missing_pf_ids": missing_pf_ids,
                    "missing_boxed_ids": missing_boxed_ids,
                }
                suite_pf_union.update(missing_pf_ids)
                suite_box_union.update(missing_boxed_ids)
        else:
            protocol_details_by_variant = {}
        report_lines.append(f"## {suite}")
        summary["suites"][suite] = {"variants": {}}
        if suite.lower() == "cmt":
            report_lines.append(
                f"Protocol stats — params/functions missing: {len(suite_pf_union)}, "
                f"unboxed answers: {len(suite_box_union)}"
            )
            summary["suites"][suite]["protocol"] = {
                "missing_pf_ids_union": sorted(suite_pf_union),
                "missing_boxed_ids_union": sorted(suite_box_union),
                "missing_pf_count": len(suite_pf_union),
                "missing_boxed_count": len(suite_box_union),
            }

        # Per-variant accuracy
        for variant, mp in sorted(variants.items()):
            n = len(mp)
            succ = sum(1 for v in mp.values() if v)
            acc = succ / n if n else 0.0
            lo, hi = wilson_ci(succ, n)
            report_lines.append(f"- {variant}: **{acc:.3f}**  (n={n}, 95% CI {lo:.3f}–{hi:.3f})")
            summary["suites"][suite]["variants"][variant] = {
                "n": n, "successes": succ, "accuracy": acc, "ci_wilson": [lo, hi], "path": meta[suite][variant]["path"]
            }
            if suite.lower() == "cmt":
                proto_detail = protocol_details_by_variant.get(variant, {})
                present_pf = int(proto_detail.get("present_pf", n))
                missing_pf = int(proto_detail.get("missing_pf", 0))
                missing_boxed = int(proto_detail.get("missing_boxed", 0))
                report_lines.append(
                    "  Protocol: params/functions present="
                    f"{present_pf}, missing={missing_pf}; missing boxed answers={missing_boxed}"
                )
                summary["suites"][suite]["variants"][variant]["protocol"] = {
                    "total": int(proto_detail.get("total", n)),
                    "parameters_functions_present": present_pf,
                    "parameters_functions_missing": missing_pf,
                    "missing_boxed_answers": missing_boxed,
                    "missing_pf_ids": proto_detail.get("missing_pf_ids", []),
                    "missing_boxed_ids": proto_detail.get("missing_boxed_ids", []),
                }

            # Per-type accuracy (if types available)
            if variant in by_suite_type[suite]:
                type_stats = {}
                for item_type, type_results in sorted(by_suite_type[suite][variant].items()):
                    type_n = len(type_results)
                    type_succ = sum(1 for v in type_results.values() if v)
                    type_acc = type_succ / type_n if type_n else 0.0
                    type_lo, type_hi = wilson_ci(type_succ, type_n)
                    type_stats[item_type] = {
                        "n": type_n, "successes": type_succ, "accuracy": type_acc, "ci_wilson": [type_lo, type_hi]
                    }
                if type_stats:
                    summary["suites"][suite]["variants"][variant]["by_type"] = type_stats

        # Pairwise syntra vs baseline if both exist
        if "baseline" in variants and "syntra" in variants:
            A = variants["baseline"]
            B = variants["syntra"]
            report_lines.append("**Syntra vs Baseline (paired)**")
            # --- Pairing integrity audit (before computing n11/n10/n01/n00) ---
            from collections import Counter

            ids_A = list(A.keys())           # baseline ids
            ids_B = list(B.keys())           # syntra ids
            set_A, set_B = set(ids_A), set(ids_B)
            paired_ids = sorted(set_A & set_B)
            paired_n = len(paired_ids)

            missing_in_syntra   = sorted(set_A - set_B)
            missing_in_baseline = sorted(set_B - set_A)
            dupe_A = [k for k, c in Counter(ids_A).items() if c > 1]
            dupe_B = [k for k, c in Counter(ids_B).items() if c > 1]

            def _preview(lst, k=10):
                return f"{', '.join(map(str, lst[:k]))}" + (f", +{len(lst)-k} more" if len(lst) > k else "")

            # JSON summary: always record integrity counts and samples (capped)
            summary["suites"][suite].setdefault("paired", {})["integrity"] = {
                "paired_n": paired_n,
                "missing_in_syntra_count": len(missing_in_syntra),
                "missing_in_baseline_count": len(missing_in_baseline),
                "duplicate_ids_baseline_count": len(dupe_A),
                "duplicate_ids_syntra_count": len(dupe_B),
                "missing_in_syntra_sample": missing_in_syntra[:50],
                "missing_in_baseline_sample": missing_in_baseline[:50],
                "duplicate_ids_baseline_sample": dupe_A[:50],
                "duplicate_ids_syntra_sample": dupe_B[:50],
            }

            # Markdown: quiet on pass, verbose on fail
            if (missing_in_syntra or missing_in_baseline or dupe_A or dupe_B):
                report_lines.append("Integrity")
                report_lines.append(f"- paired_n: **{paired_n}**")
                if missing_in_syntra:
                    report_lines.append(f"- missing_in_syntra: **{len(missing_in_syntra)}** [{_preview(missing_in_syntra)}]")
                if missing_in_baseline:
                    report_lines.append(f"- missing_in_baseline: **{len(missing_in_baseline)}** [{_preview(missing_in_baseline)}]")
                if dupe_A:
                    report_lines.append(f"- duplicate_ids_baseline: **{len(dupe_A)}** [{_preview(dupe_A)}]")
                if dupe_B:
                    report_lines.append(f"- duplicate_ids_syntra: **{len(dupe_B)}** [{_preview(dupe_B)}]")
            else:
                report_lines.append(f"Integrity — OK (paired_n={paired_n})")

            keys = paired_ids
            n = paired_n

            n11 = n10 = n01 = n00 = 0
            a_correct = b_correct = 0
            paired_items: List[Tuple[bool, bool]] = []
            for k in keys:
                a = A[k]; b = B[k]
                paired_items.append((a,b))
                if a: a_correct += 1
                if b: b_correct += 1
                if a and b: n11 += 1
                elif a and not b: n10 += 1
                elif (not a) and b: n01 += 1
                else: n00 += 1
            accA = a_correct / n if n else 0.0
            accB = b_correct / n if n else 0.0
            delta = accB - accA
            p = mcnemar_exact_p(n01, n10)
            discordant = n01 + n10
            se = math.sqrt(discordant) / n if n else 0.0
            approx_lo = delta - 1.96*se if n else delta
            approx_hi = delta + 1.96*se if n else delta
            boot_lo, boot_hi = bootstrap_delta(paired_items, args.bootstrap, rng) if n else (delta, delta)
            h = cohens_h(accB, accA)

            report_lines.append(f"- Accuracy baseline: **{accA:.3f}**, syntra: **{accB:.3f}**, Δ(B−A): **{delta:+.3f}** (approx 95% CI {approx_lo:+.3f}..{approx_hi:+.3f})")
            report_lines.append(f"- McNemar exact p: **{p:.4g}**  | discordant: {discordant} (B only={n01}, A only={n10})")

            # Discordant win-rate
            D = discordant
            b_win_rate = (n01 / D) if D else 0.5
            ci_lo, ci_hi = wilson_ci(n01, D) if D else (0.0, 1.0)
            report_lines.append(f"- B win-rate among discordants: **{b_win_rate:.3f}** (95% CI {ci_lo:.3f}–{ci_hi:.3f})")
            
            report_lines.append(f"- Bootstrap 95% CI for Δ: **{boot_lo:+.3f} .. {boot_hi:+.3f}**")
            report_lines.append(f"- Effect size (Cohen's h for proportions): **{h:+.3f}**\n")

            # Power guidance
            D_required = power_required_discordants(max(min(b_win_rate, 0.999999), 1e-6), args.alpha, args.target_power)
            paired_n = n
            r = (discordant / paired_n) if paired_n else 0.0
            est_paired_needed = int(math.ceil(D_required / r)) if r > 0 else None
            report_lines.append(f"- Power guidance (α={args.alpha}, power={args.target_power:.2f}): need ~{D_required} discordants; at current discordant rate {r:.3f}, paired N ≈ {est_paired_needed if est_paired_needed else 'n/a'}.")

            paired_summary = summary["suites"][suite]["paired"]
            paired_summary.update({
                "paired_n": n,
                "acc_baseline": accA, "acc_syntra": accB, "delta": delta,
                "mcnemar_p": p, "discordant": discordant, "n01": n01, "n10": n10,
                "delta_ci_approx": [approx_lo, approx_hi],
                "delta_ci_bootstrap": [boot_lo, boot_hi],
                "cohens_h": h,
                "b_win_rate": b_win_rate, "b_win_rate_ci": [ci_lo, ci_hi],
                "power_guidance": {"alpha": args.alpha, "target_power": args.target_power, "required_discordants": D_required, "discordant_rate": r, "estimated_paired_N": est_paired_needed}
            })
            comparable_suites.append(suite)
            micro_pool_items.extend(paired_items)

        report_lines.append("")

    # Overall summaries
    report_lines.append("# Overall\n")

    # Micro-average across all paired items
    if micro_pool_items:
        n = len(micro_pool_items)
        a = sum(1 for b,s in micro_pool_items if b)
        b = sum(1 for b,s in micro_pool_items if s)
        accA = a / n
        accB = b / n
        delta = accB - accA
        discordant = sum(1 for b,s in micro_pool_items if (b != s))
        se = math.sqrt(discordant) / n
        approx_lo = delta - 1.96*se
        approx_hi = delta + 1.96*se
        boot_lo, boot_hi = bootstrap_delta(micro_pool_items, args.bootstrap, rng)
        h = cohens_h(accB, accA)
        report_lines.append("**Micro-average (pooled items where both variants exist)**")
        report_lines.append(f"- Accuracy baseline: **{accA:.3f}**, syntra: **{accB:.3f}**, Δ: **{delta:+.3f}** (approx 95% CI {approx_lo:+.3f}..{approx_hi:+.3f})")
        report_lines.append(f"- Bootstrap 95% CI for Δ: **{boot_lo:+.3f} .. {boot_hi:+.3f}**")
        report_lines.append(f"- Effect size (Cohen's h): **{h:+.3f}**\n")
        pooled_r = discordant / n if n else 0.0
        report_lines.append(f"- Pooled discordant rate: **{pooled_r:.3f}**")
        summary["overall"]["micro"] = {
            "paired_item_n": n,
            "acc_baseline": accA, "acc_syntra": accB, "delta": delta,
            "delta_ci_approx": [approx_lo, approx_hi],
            "delta_ci_bootstrap": [boot_lo, boot_hi],
            "cohens_h": h,
            "pooled_discordant_rate": pooled_r
        }

    # Macro-average across suites
    # For macro we include only suites that have both variants, to be comparable.
    if comparable_suites:
        base_list = []
        syn_list = []
        for suite in comparable_suites:
            a = summary["suites"][suite]["paired"]["acc_baseline"]
            b = summary["suites"][suite]["paired"]["acc_syntra"]
            base_list.append(a); syn_list.append(b)
        accA = sum(base_list)/len(base_list)
        accB = sum(syn_list)/len(syn_list)
        delta = accB - accA
        h = cohens_h(accB, accA)
        report_lines.append("**Macro-average (mean of per-suite accuracies, comparable suites only)**")
        report_lines.append(f"- Accuracy baseline: **{accA:.3f}**, syntra: **{accB:.3f}**, Δ: **{delta:+.3f}**")
        report_lines.append(f"- Effect size (Cohen's h): **{h:+.3f}**\n")
        summary["overall"]["macro"] = {
            "suite_count": len(comparable_suites),
            "acc_baseline": accA, "acc_syntra": accB, "delta": delta,
            "cohens_h": h
        }

    # Write outputs
    report_md = "\n".join(report_lines)
    report_filename = get_report_filename(list(by_suite.keys()))
    with open(os.path.join(out_dir, report_filename), "w", encoding="utf-8") as f:
        f.write(report_md)
    with open(os.path.join(out_dir, "stats_summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print(f"Wrote {os.path.join(out_dir, report_filename)}")
    print(f"Wrote {os.path.join(out_dir, 'stats_summary.json')}")
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("runs_dir", help="Path to runs/")
    ap.add_argument("--bootstrap", type=int, default=5000, help="Bootstrap draws for Δ CI")
    ap.add_argument("--seed", type=int, default=42, help="RNG seed")
    ap.add_argument("--out_dir", default=None, help="Output directory (default: <runs_dir>/_reports)")
    ap.add_argument("--alpha", type=float, default=0.05, help="Significance level for power calculations")
    ap.add_argument("--target_power", type=float, default=0.80, help="Target power for power calculations")
    args = ap.parse_args()

    rng = random.Random(args.seed)
    runs_dir = args.runs_dir

    # Discover files
    pattern = os.path.join(runs_dir, "**", "graded*.jsonl")
    all_files = sorted(glob.glob(pattern, recursive=True))
    if not all_files:
        raise SystemExit(f"No graded*.jsonl files under {runs_dir}")

    # Group files by their timestamp folder (immediate parent directory)
    files_by_timestamp: Dict[str, List[str]] = defaultdict(list)
    for f in all_files:
        timestamp_dir = os.path.basename(os.path.dirname(f))
        files_by_timestamp[timestamp_dir].append(f)

    # Process each timestamp folder separately
    for timestamp, files in sorted(files_by_timestamp.items()):
        print(f"Processing timestamp folder: {timestamp}")
        process_timestamp_folder(timestamp, files, runs_dir, args, rng)

if __name__ == "__main__":
    main()
