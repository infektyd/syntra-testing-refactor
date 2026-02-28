# HF-CMT v1.2.1 — Identity Audit Stable

## Summary

Finalized mode-aware identity comparison with full breakdown:

- Uses `pred`-based comparison (no boxed extraction)
- Mode detection: MC vs. RAW, via `normalize_multichoice`
- Skips empties and cross-mode indices
- Adds `cross_mode_skipped` to summary for full accounting

## Key Metrics (Gold v1.1)

valid_gold=50  
gold_invalid=0  
false_negatives=0  
ambiguous=0  
identical_model_predictions=24  
shared_identity_indices=49  
mc_identity_compared=27  
raw_identity_compared=20  
cross_mode_skipped=2

## Verification

Command:

```bash
python Tools/CMTExtractor/hf_cmt_audit.py \
  --answers prompts/suites/hf_cmt.fixed.jsonl \
  --syn runs/hf_cmt/syntra/hf_cmt_syntra.pass2.jsonl \
  --base runs/hf_cmt/baseline/hf_cmt_baseline.pass2.jsonl
```

prints:

```text
[INFO] Identity metric: shared=49, identical=24, mc_compared=27, raw_compared=20
[INFO] Cross-mode skipped: 2
```

and produces a consistent summary JSON.

## Status

✅ No regressions in grading or audit
✅ All v1.1 tests pass  
✅ v1.2 AuditAgent documentation synchronized
