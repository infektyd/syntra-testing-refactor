
# Tools Directory

## Purpose

The `Tools/` directory contains scripts and utilities for HF-CMT extraction, grading, auditing, visualization, and baseline runs. It focuses on Python-based agents for deterministic evaluation.

## Inputs/Outputs

- **Inputs**: Model responses (JSONL), prompt suites (e.g., `hf_cmt.fixed.jsonl`), audit summaries.
- **Outputs**: Graded `pass2.jsonl`, reports (`.md`), audit summaries (`.json`), figures (`.png`), and logs.

## Key Subdirs & Scripts

- `CMTExtractor/`: Core Python tools.
  - `grade_official_cmt.py`: Grades responses (CLI: `--responses`, `--answers`, `--out`).
  - `hf_cmt_audit.py`: Validates gold/dataset (CLI: `--syn`, `--base`, `--out`).
  - `viz_hf_cmt.py`: Generates plots (CLI: `--syn`, `--base`, `--audit`, `--outdir`).
  - `fix_gold_entries.py`: Patches invalid golds (CLI: `--input`, `--output`).
  - `run_baseline.sh`: Runs reference model harness.
  - `clean.py`: Cleans run artifacts and Python caches (CLI: `--runs-dir`, `--version`).

- `common/`: Shared utilities (e.g., `logger.py` for consistent `[INFO]` logging).

All scripts support `--version`. Use with subagents (GraderAgent, AuditAgent, etc.). Version is mirrored from the repository root.
