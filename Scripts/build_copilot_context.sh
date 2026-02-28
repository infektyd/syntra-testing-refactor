#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="$ROOT/.copilot_context.md"

# Max bytes per file to avoid blowing token window (adjust as needed)
SLICE_BYTES=${SLICE_BYTES:-20000}

# Helper to append a section if file exists
append() {
  local title="$1"; shift
  local path="$1"; shift
  if [[ -f "$path" ]]; then
    echo -e "\n\n---\n## ${title}\n_Path_: ${path}\n" >> "$OUT"
    # slice to keep context lean
    head -c "$SLICE_BYTES" "$path" >> "$OUT"
    echo -e "\n" >> "$OUT"
  fi
}

# Start fresh
: > "$OUT"
echo "# SYNTRA Copilot Context (auto-generated)" >> "$OUT"
echo "_Generated: $(date '+%Y-%m-%d %H:%M:%S')_" >> "$OUT"
echo "_Purpose: Persist project state across Copilot CLI sessions._" >> "$OUT"

# Core state (add/remove sources as needed)
append "README"                    "$ROOT/README.md"
append "Makefile"                  "$ROOT/Makefile"
append "Benchmarks Overview"       "$ROOT/runs/summary/benchmarks_overview.md"
append "Benchmarks CSV"            "$ROOT/runs/summary/benchmarks_overview.csv"

# Add a small tail prompt Copilot will see first
cat >> "$OUT" << 'EOF'

---
## Session Goals (for Copilot)
- You are resuming work on the syntraTesting refactor.
- Respect repo hygiene: keep only `runs/summary/*` for artifacts.
- TEST mode: `SYNTRA_TEST_MODE=1` by default; LIVE mode toggled via `RUN_SYNTRA=1`.
- Adopt PLAN → ACTIONS → RESULT when proposing multi-file changes.

**Next tasks candidates:**
1) Verify Makefile targets still pass in TEST mode and aggregate summaries.
2) Ensure Docker runs green.
3) Normalize any path refs after reorg (Scripts/, src/, runs/).

EOF

echo "Wrote context: $OUT"