#!/usr/bin/env bash
# Run: chmod +x Tools/smoke.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

if ! command -v jq >/dev/null 2>&1; then
  echo "ERROR: jq is required for smoke test verification." >&2
  exit 1
fi

RUN_ID="smoke_$(date +%Y%m%d_%H%M%S)"

OPENROUTER_API_KEY="smoke_key" \
BASELINE_MODEL="smoke_baseline" \
SYNTRA_URL="http://localhost:8080/v1/chat/completions" \
MODEL_SYNTRA="smoke_syntra" \
RUN_ID="$RUN_ID" \
SEED=1 \
N=2 \
FAKE_RUN=1 \
make -C "$REPO_ROOT" bench-live

GSM_DIR="$REPO_ROOT/runs/gsm8k/$RUN_ID"
ARC_DIR="$REPO_ROOT/runs/arc_challenge/$RUN_ID"

expected_files=(
  "$GSM_DIR/gsm8k.pass1.baseline.jsonl"
  "$GSM_DIR/gsm8k.pass2.syntra.jsonl"
  "$GSM_DIR/summary.gsm8k.json"
  "$ARC_DIR/arc.pass1.baseline.jsonl"
  "$ARC_DIR/arc.pass2.syntra.jsonl"
  "$ARC_DIR/summary.arc.json"
  "$GSM_DIR/graded.gsm8k.baseline.jsonl"
  "$GSM_DIR/graded.gsm8k.syntra.jsonl"
  "$ARC_DIR/graded.arc.baseline.jsonl"
  "$ARC_DIR/graded.arc.syntra.jsonl"
)

for path in "${expected_files[@]}"; do
  if [[ ! -f "$path" ]]; then
    echo "ERROR: Expected file missing: $path" >&2
    exit 1
  fi
done

jq '.' "$GSM_DIR/summary.gsm8k.json" >/dev/null
jq '.' "$ARC_DIR/summary.arc.json" >/dev/null

echo "Smoke test completed successfully for RUN_ID=$RUN_ID"
