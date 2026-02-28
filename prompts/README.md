# Prompts Directory

## Purpose
The `prompts/` directory stores JSONL fixture files for benchmark suites, including HF-CMT problems, gold answers, and patched versions.

## Inputs/Outputs
- **Inputs**: Raw prompt data (e.g., from official sources).
- **Outputs**: Fixed suites (e.g., hf_cmt.fixed.jsonl after gold patching), sample prompts for testing.

## Key Files
- `suites/hf_cmt.fixed.jsonl`: Patched gold answers and prompts for 50 HF-CMT items.
- `suites/hf_cmt_gold_patch.jsonl`: Log of gold fixes applied.
- `suites/hf_cmt.jsonl`: Original suite (may contain invalid golds).

Use with GraderAgent or AuditAgent via `--answers` and `--suite` flags. Version mirrored from root.
