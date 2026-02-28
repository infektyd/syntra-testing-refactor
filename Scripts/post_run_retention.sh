#!/usr/bin/env bash
set -euo pipefail

mkdir -p runs/reference

# preserve latest audit
latest_audit="$(ls -t \
  runs/*/*_audit_summary.json \
  runs/*audit*.json* \
  2>/dev/null | head -n1 || true)"
[ -n "${latest_audit:-}" ] && cp -f "$latest_audit" runs/reference/audit_summary.json

# preserve latest reports
latest_syntra="$(ls -t \
  runs/*/syntra/*.report.md \
  runs/syntra/*.report.md \
  2>/dev/null | head -n1 || true)"
[ -n "${latest_syntra:-}" ] && cp -f "$latest_syntra" runs/reference/syntra_report.md

latest_base="$(ls -t \
  runs/*/baseline/*.report.md \
  runs/baseline/*.report.md \
  2>/dev/null | head -n1 || true)"
[ -n "${latest_base:-}" ] && cp -f "$latest_base" runs/reference/baseline_report.md

# clean legacy artifacts only (preserve suite-scoped outputs)
find runs -maxdepth 1 -type f -name "*pass*.jsonl" -delete || true
find runs -maxdepth 1 -type f -name "*audit*.json*" -delete || true

for legacy_dir in runs/syntra runs/baseline; do
  if [[ -d "$legacy_dir" ]]; then
    find "$legacy_dir" -maxdepth 1 -type f -name "*pass*.jsonl" -delete || true
    rm -rf "$legacy_dir/logs" || true
  fi
done

rm -rf runs/figs runs/reports || true