# HF-CMT Grading Suite v1.0

This folder contains the official HF-CMT benchmarking audit and grading tools, which verify the Hf-CMT subset (50 items) of the Condensed Matter Theory benchmark. The suite implements robust normalization, validation, and comparison logic to ensure reproducible evaluation of model performance.

## Purpose of HF-CMT Grader and Audit

The HF-CMT Grader evaluates model predictions against gold answers from the Hf-CMT benchmark, implementing Pass@1 scoring with tolerance-based comparison for different answer modalities. The HF-CMT Audit validates gold answer integrity and identifies inconsistent model predictions.

Normalization handles:
- Multi-choice order insensitivity (`a;c;b` ≡ `a;b;c`) enforced via `normalize_multichoice` with the `MC_ORDER_ONLY` reason code.
- Numeric tolerance through the pure helper `numeric_equal`, comparing scalars, lists, and tuple bundles within ±0.02 (default `--float-tol`).
- Canonical symbolic cleanup in `canon_symbol`, trimming LaTeX spacing and prefixes like `alpha=` or `\left`.
- LaTeX wrapper removal

## Gold Validation Process

Gold answers are validated against prompt-derived choice sets:
- Letter-option validation only for multiple-choice questions
- Parameter-based fallback when prompts lack explicit options
- Regex extraction supports formats: `(a)`, `a)`, `a.`, `[a]`, `{a}`

## Known Issues

- Gold index 12 (`\boxed{e}`) marked as manual review only - contains invalid choice beyond standard options

## Prerequisites
- Python 3.10+
- Install Python deps:
  - `pypdf==4.3.1`
  - `sympy==1.12`
  - `regex==2024.5.15`

```bash
python -m pip install -r Tools/CMTExtractor/requirements.txt
```

## Testing and development

For local test runs:

```bash
python -m pip install -r Tools/CMTExtractor/requirements.txt
python -m pip install pytest pytest-mock reportlab
pytest -q Tools/CMTExtractor/tests/
```

Notes:
- pytest-mock provides the mocker fixture used in [Tools/CMTExtractor/tests/test_report_agent.py](Tools/CMTExtractor/tests/test_report_agent.py).
- reportlab is required only for optional PDF report generation and for tests that patch reportlab internals. CI installs it automatically for test runs.

## Running Benchmark Suites

### Test (stub) runs
```bash
make bench-test
```
The test pipeline keeps `RUN_SYNTRA=0` and `SYNTRA_TEST_MODE=1`, so dataset loaders will serve the local stubs and no remote completions are issued.

### Live runs
```bash
make bench-live
```
This target exports `RUN_SYNTRA=1` and `SYNTRA_TEST_MODE=0` so that [`Tools/CMTExtractor/run_suite.sh`](Tools/CMTExtractor/run_suite.sh:48–119) invokes the live evaluation branch. If you launch the suite manually, set both variables explicitly:

```bash
RUN_SYNTRA=1 SYNTRA_TEST_MODE=0 make bench-arc-validation
```

Guard rails reject misconfigured runs:
- [`run_suite.sh`](Tools/CMTExtractor/run_suite.sh:48–119) now aborts if `RUN_SYNTRA=1` while `SYNTRA_TEST_MODE` is not `0`.
- Dataset loaders for ARC and GSM8K raise `RuntimeError` if stubs are requested while `RUN_SYNTRA=1` (see [`Benchmarks/ARC/bench/datasets_arc.py`](Benchmarks/ARC/bench/datasets_arc.py:233–242) and [`Benchmarks/GSM8K/bench/datasets_gsm8k.py`](Benchmarks/GSM8K/bench/datasets_gsm8k.py:197–205)).

### Post-run validation
After completing a live run:
1. Inspect `runs/<suite>/<split>/pass1.jsonl` to confirm fresh generations were captured.
2. Execute `python3 Tools/aggregate_benchmarks.py`. When `RUN_SYNTRA=1`, the aggregator now errors if no pass1 artifacts are discovered, preventing silent stub usage.
3. Review the generated summary in `runs/summary/` for accuracy deltas.

## Audit HF-CMT Benchmark

Validate gold answer integrity and compare model predictions:

```bash
python Tools/CMTExtractor/hf_cmt_audit.py
```

Outputs:
- `runs/hf_cmt/hf_cmt_audit.jsonl` - per-index records with validation results
- `runs/hf_cmt/hf_cmt_audit_summary.json` - summary stats including validation counts

Expected stable metrics for v1.0:
- `valid_gold=49`, `gold_invalid=1` (index 12 manual review), `false_positives=0`, `false_negatives=0`, `ambiguous=0`

## Grade HF-CMT Responses

Evaluate model predictions with Pass@1 scoring:

```bash
python Tools/CMTExtractor/grade_official_cmt.py \
  --responses runs/hf_cmt/syntra/hf_cmt_syntra.jsonl --answers prompts/suites/hf_cmt.fixed.jsonl --suite prompts/suites/hf_cmt.fixed.jsonl \
  --out runs/hf_cmt/syntra/hf_cmt_syntra.pass2.jsonl --report runs/hf_cmt/syntra/hf_cmt_syntra.fixed.report.md \
  --normalize-choices --float-tol 0.02
```

Report includes:
- Overall accuracy (fraction + percentage)
- Per-type breakdown table
- Gold errors section
- Top-5 disagreements with reasons (`MC_ORDER_ONLY`, `EXACT_STRING`, etc.)

## Version

Check versioning:
```bash
python Tools/CMTExtractor/hf_cmt_audit.py --version
python Tools/CMTExtractor/grade_official_cmt.py --version
```
Both should return `1.0.0`
