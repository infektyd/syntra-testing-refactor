# SYNTRA CMT Benchmarking Suite

This layer measures SYNTRA's symbolic reasoning quality, stability, and latency via a lightweight, reproducible harness.

## Quick Start

```bash
cd Benchmarks/SyntraCMT
swift build -c release
mkdir -p runs
.build/release/syntra-cmt \\
  --endpoint http://127.0.0.1:8081/v1/chat/completions \\
  --model syntra-consciousness \\
  --input prompts/sample_prompts.jsonl \\
  --output runs/syntra_cmt_results.jsonl \\
  --trials 3 \\
  --seed 42 \\
  --temperature 0.2
```

## Timeouts & Robust Decoding

Longer round trips or atypical payloads can now be handled with CLI flags that extend networking timeouts and emit verbose diagnostics. Example release run with the hardened decoder:

```bash
.build/release/syntra-cmt --timeout 180 --verbose --trials 3 --endpoint https://host/v1/chat/completions --input prompts/sample_prompts.jsonl --output runs/hardened_run.jsonl
```

## What It Does

- Loads prompts from JSONL (`id`, `content`, `metadata`).
- Sends each prompt to your local SYNTRA Vapor endpoint.
- Records **latency**, raw **response text**, and heuristic **metrics** into JSONL.
- Appends results with a run separator, never overwriting old data.

## Current Metrics (Heuristic, Deterministic)

- `tokens_est`: crude token estimate by character length.
- `unique_word_ratio`: lexical diversity proxy (higher often indicates richer content).
- `repetition_penalty`: penalizes consecutive repeated words.
- `sentence_terminal_ratio`: fraction of sentences with proper terminal punctuation.
- `coherence_score`: blend of structure/diversity with repetition penalty.
- `logical_consistency_score`: rewards connective structure and enumerations.
- `moral_stability_score`: proxy for balanced ethical language (low-risk vs. extreme terms).
- `drift_deviation`: populated by the aggregator with the stddev of response length per prompt.
- `unique_word_ratio_std`: optional aggregator output capturing stddev of `unique_word_ratio` per prompt.

> **Note:** These metrics are intentionally **LLM-agnostic** and do not call any external graders. They create a stable baseline you can compare across backends and settings. You can later add an LLM-assisted scorer as a *separate* pass if desired.

## File Layout

```text
Benchmarks/SyntraCMT
├── Package.swift
├── Sources/SyntraCMT/main.swift
├── prompts/sample_prompts.jsonl
├── runs/                     # created at runtime
├── metrics_schema.json
└── BENCHMARKS.md
```

## JSONL Output Schema

See `metrics_schema.json`. Each line contains a `RunRecord` with metrics and raw text.

## Aggregator

Build in release mode and run the post-processor to backfill drift metrics:

```bash
swift build -c release
.build/release/syntra-cmt-aggregate \
  --input runs/drift_resilience.jsonl \
  --output runs/drift_resilience.aggregated.jsonl \
  --metric length,stddev,unique_ratio_std \
  --group-by prompt_id
```

Use `./aggregate.sh runs/drift_resilience.jsonl` for the common case (defaults to `length,stddev` and writes `<input>.aggregated.jsonl`).

## Performance Trace Merge (--merge-perf)

Pass `--merge-perf PATH` to the runner to enrich each `RunRecord` with performance data emitted by Vapor's `PerformanceLogger`. The JSONL file should provide one object per timing sample:

```json
{ "timestamp_iso": "2024-05-18T12:34:56Z", "latency_ms": 123, "tags": { "prompt_id": "valon_ethics_consent_01" } }
```

For every run result the merger grabs the closest timing entry with the same `prompt_id` inside ±5 seconds, appending it as a `perf` block without altering the recorded `latency_ms`. Parse failures or missing matches are counted and reported once as `perf-merge: <errors> errors, <matches> matches`.

## Prompt Suites

- `valon_ethics` — consent, fairness, and transparency framing.
- `modi_logic` — numbered reasoning with connective language.
- `drift_resilience` — paraphrase families for stability checks.
- `coherence_structures` — rubric-friendly explainers with headings.

Run any suite (appends to `runs/<suite>.jsonl`) and forward extra flags as needed:

```bash
./run_suite.sh drift_resilience --trials 5 --temperature 0.2
```

## Baseline Comparison

1. Capture SYNTRA output:\
   `./run_cmt.sh --endpoint http://127.0.0.1:8081/v1/chat/completions --input prompts/suites/valon_ethics.jsonl --output runs/syntra_valon_ethics.jsonl --trials 3`
2. Capture a baseline model under the same prompts:\
   `./run_cmt.sh --endpoint http://baseline.example/v1/chat/completions --input prompts/suites/valon_ethics.jsonl --output runs/baseline_valon_ethics.jsonl --trials 3`
3. Aggregate both files and compare metrics (length mean/std, coherence mean):\
   `./aggregate.sh runs/syntra_valon_ethics.jsonl --metric length,stddev,unique_ratio_std`\
   `./aggregate.sh runs/baseline_valon_ethics.jsonl --metric length,stddev,unique_ratio_std`

Review the aggregated JSONL outputs with your analysis tool of choice to inspect `metrics.drift_deviation`, `metrics.unique_word_ratio_std`, and `metrics.coherence_score`.

## Official CMT Import (from PDF)

Import the Official CMT problems from a local PDF and run them in this harness.

1) Place the PDF under `resources/`:
   - `resources/2510.05228v1.pdf`

2) Extract and validate:
```bash
python Tools/CMTExtractor/extract_cmt_from_pdf.py \
  --pdf resources/2510.05228v1.pdf \
  --out prompts/suites/official_cmt.jsonl \
  --overwrite

python Tools/CMTExtractor/validate_official_cmt.py --input prompts/suites/official_cmt.jsonl
```

3) Run the suite:
```bash
./run_suite.sh official_cmt --trials 1 --timeout 180 --verbose
```

Notes:
- The extractor is append-safe by default; pass `--overwrite` to replace the output file.
- Each prompt includes metadata: `type` in `{HF,ED,DMRG,QMC,VMC,PEPS,SM,Other}` and `modality` in `{numeric,multiple_choice,algebraic,operator}`.
- A grading skeleton is available at `Tools/CMTExtractor/grade_official_cmt.py` to compute Pass@1 for numeric/algebraic/multiple_choice; operator grading is a TODO hook.

## 🧩 Utility Scripts (v2.1.1+)

### `Scripts/count_hf_cmt_prompts.py`

**Purpose:**  
Quick verification utility for confirming that benchmark suites are properly loaded and contain the expected number of prompt entries before initiating a full SYNTRA run.

**Details:**  
- Reads the `prompts/suites/hf_cmt.jsonl` file directly.  
- Counts the number of JSON lines (prompts).  
- Prints a clean diagnostic message for immediate visual confirmation.  
- Helps ensure data integrity after merges or gold patching steps.

**Usage:**
```bash
python Scripts/count_hf_cmt_prompts.py
```

**Expected Output:**
```
✅ SYNTRA suite loaded: 50 prompts detected
```

**Context:**  
This script can be invoked locally or through Codex Web (via VS Code).  
Running it through **Codex Web** routes execution to the cloud sandbox, confirming connection integrity and remote reasoning readiness.

**Version:** Introduced in `v2.1.1` (October 2026) — Maintainer: Hans Axelsson
