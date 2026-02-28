#!/usr/bin/env bash
set -euo pipefail

# OrganizerAgent: Orchestrate suite-aware pipeline
# Usage: bash run_suite.sh [--suite hf_cmt|arc_challenge|gsm8k] [--split validation|test]

# --- Configuration ---
SUITE_NAME="hf_cmt"
SPLIT="validation"
PYTHON_BIN="${PYTHON_BIN:-python3}"
RUN_SYNTRA="${RUN_SYNTRA:-0}"
SYNTRA_TEST_MODE="${SYNTRA_TEST_MODE:-1}"
SYNTRA_SERVER="${SYNTRA_SERVER:-http://127.0.0.1:8081}"
# Optional sampling controls
LIMIT="${LIMIT:-}"
SUBSAMPLE="${SUBSAMPLE:-0}"       # 1 to enable random subsampling after formatting
SAMPLE_SEED="${SAMPLE_SEED:-}"     # optional seed for deterministic sampling

# --- Helper Functions ---
function list_suites() {
  echo "Static Suites (from prompts/suites):"
  find prompts/suites -name "*.jsonl" -not -name "*.fixed.jsonl" -not -name "*_patch.jsonl" | \
    sed 's|.*/||; s|\.jsonl$||' | sort -u
  echo -e "\nDynamic Suites (HuggingFace):"
  echo "  arc_challenge"
  echo "  arc_easy"
  echo "  gsm8k"
}

function resolve_suite_path() {
  local suite="$1"
  case "$suite" in
    arc_challenge|arc_easy|gsm8k)
      echo "runs/${suite}/${suite}_${SPLIT}.jsonl"
      ;;
    *)
      echo "prompts/suites/${suite}.fixed.jsonl"
      ;;
  esac
}

# --- Argument Parsing ---
while [[ $# -gt 0 ]]; do
  case "$1" in
    --suite) SUITE_NAME="$2"; shift 2 ;;
    --split) SPLIT="$2"; shift 2 ;;
    --limit) LIMIT="$2"; shift 2 ;;
    --subsample) SUBSAMPLE=1; shift 1 ;;
    --list-suites) list_suites; exit 0 ;;
    *) echo "Unknown option: $1"; exit 1 ;;
  esac
done

# --- Mode Sanity Checks ---
if [[ "$RUN_SYNTRA" -eq 1 && "$SYNTRA_TEST_MODE" -ne 0 ]]; then
  echo "ERROR: RUN_SYNTRA=1 requires SYNTRA_TEST_MODE=0 to execute LIVE benchmarks."
  echo "Set SYNTRA_TEST_MODE=0 or run 'make bench-live' which configures both variables."
  exit 2
fi

# --- Main Logic ---
SUITE_PATH=$(resolve_suite_path "$SUITE_NAME")
SUITE_RUN_DIR="runs/${SUITE_NAME}"
LOG_DIR="${SUITE_RUN_DIR}/logs"
BASE_DIR="${SUITE_RUN_DIR}/baseline"
SYN_DIR="${SUITE_RUN_DIR}/syntra"
FIG_DIR="${SUITE_RUN_DIR}/figs"
REPORT_DIR="${SUITE_RUN_DIR}/reports"

mkdir -p "$LOG_DIR" "$BASE_DIR" "$SYN_DIR" "$FIG_DIR" "$REPORT_DIR"

PROMPTS_FILE="${SUITE_RUN_DIR}/${SUITE_NAME}_prompts.jsonl"

# Ensure static suites have a local prompts copy for downstream tools (runner/grader)
if [[ -f "$SUITE_PATH" && ! -f "$PROMPTS_FILE" ]]; then
  cp "$SUITE_PATH" "$PROMPTS_FILE"
fi

# Print mode banner
if [[ "$RUN_SYNTRA" -eq 1 && "$SYNTRA_TEST_MODE" -eq 0 ]]; then
  echo "=============================="
  echo "MODE: LIVE"
  echo "Server: ${SYNTRA_SERVER}"
  echo "=============================="
else
  echo "=============================="
  echo "MODE: TEST (using stubs)"
  echo "=============================="
fi

# --- Suite Execution ---
case "$SUITE_NAME" in
  arc_challenge|arc_easy)
    ARC_SUBSET="${SUITE_NAME#arc_}"
    "$PYTHON_BIN" benchmarks/Benchmarks/ARC/bench/format_arc.py \
      --subset "$ARC_SUBSET" --split "$SPLIT" \
      $([[ "${SUBSAMPLE}" -eq 0 && -n "${LIMIT}" ]] && echo --limit "${LIMIT}") \
      --output-runner "${SUITE_RUN_DIR}/${SUITE_NAME}_prompts.jsonl" \
      --output-reference "${SUITE_RUN_DIR}/${SUITE_NAME}_reference.jsonl"
    ;;
  gsm8k)
    "$PYTHON_BIN" benchmarks/Benchmarks/GSM8K/bench/format_gsm8k.py \
      --split "$SPLIT" \
      $([[ "${SUBSAMPLE}" -eq 0 && -n "${LIMIT}" ]] && echo --limit "${LIMIT}") \
      --output-runner "${SUITE_RUN_DIR}/${SUITE_NAME}_prompts.jsonl" \
      --output-reference "${SUITE_RUN_DIR}/${SUITE_NAME}_reference.jsonl"
    ;;
esac

# If running live, check for stub usage in logs or outputs and abort if found
if [[ "$RUN_SYNTRA" -eq 1 && "$SYNTRA_TEST_MODE" -eq 0 ]]; then
  # Search for "Using stub data" in run directory and logs
  if grep -R --line-number -I "Using stub data" "$SUITE_RUN_DIR" "$LOG_DIR" >/dev/null 2>&1; then
    echo "ERROR: Detected 'Using stub data' in run artifacts while in LIVE mode. Aborting to avoid accidental stub evaluation."
    echo "Check loaders and ensure RUN_SYNTRA/SYNTRA_TEST_MODE are set correctly."
    exit 2
  fi
fi

# --- Optional random subsampling (post-format) ---
if [[ -n "${LIMIT}" && "${SUBSAMPLE}" -eq 1 ]]; then
  SUB_OUT="${SUITE_RUN_DIR}/${SUITE_NAME}_prompts.sub${LIMIT}.jsonl"
  echo "Applying random subsample: n=${LIMIT}${SAMPLE_SEED:+ seed=${SAMPLE_SEED}}"
  # Try shuf first (may not exist on macOS), else Python
  if command -v shuf >/dev/null 2>&1; then
    shuf -n "${LIMIT}" "${PROMPTS_FILE}" > "${SUB_OUT}" || true
  fi
  if [[ ! -s "${SUB_OUT}" ]]; then
    "$PYTHON_BIN" - "$PROMPTS_FILE" "$SUB_OUT" "$LIMIT" "$SAMPLE_SEED" << 'PY'
import sys, random
src, dst, n_str, seed = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
try:
    n = int(n_str)
except Exception:
    n = 50
lines = [ln for ln in open(src, 'r', encoding='utf-8') if ln.strip()]
if seed:
    try:
        random.seed(int(seed))
    except Exception:
        random.seed(seed)
if n >= len(lines):
    sample = lines
else:
    sample = random.sample(lines, n)
with open(dst, 'w', encoding='utf-8') as f:
    for ln in sample:
        f.write(ln if ln.endswith('\n') else ln + '\n')
PY
  fi
  if [[ -s "${SUB_OUT}" ]]; then
    PROMPTS_FILE="${SUB_OUT}"
  else
    echo "Random subsample failed; using first-${LIMIT} fallback"
    head -n "${LIMIT}" "${PROMPTS_FILE}" > "${SUB_OUT}" || true
    [[ -s "${SUB_OUT}" ]] && PROMPTS_FILE="${SUB_OUT}"
  fi
fi

# --- Evaluation Phase: call eval_runner.py in LIVE mode to generate pass1.jsonl ---
if [[ "$RUN_SYNTRA" -eq 1 && "$SYNTRA_TEST_MODE" -eq 0 ]]; then
  OUT_DIR="${SUITE_RUN_DIR}/${SPLIT}"
  mkdir -p "${OUT_DIR}"
  PASS1_OUT="${OUT_DIR}/pass1.jsonl"
  # Evaluator tunables
  EVAL_TIMEOUT="${EVAL_TIMEOUT:-}"
  EVAL_CONCURRENCY="${EVAL_CONCURRENCY:-}"
  EVAL_RETRIES="${EVAL_RETRIES:-}"
  EVAL_RESUME="${EVAL_RESUME:-1}"

  echo "Starting LIVE evaluation: writing pass1 to ${PASS1_OUT}"
  "$PYTHON_BIN" src/syntra_testing/runners/eval_runner.py \
    --suite "${SUITE_NAME}" \
    --split "${SPLIT}" \
    --prompts "${PROMPTS_FILE}" \
    --out "${PASS1_OUT}" \
    --server "${SYNTRA_SERVER}" \
    $([[ -n "${EVAL_TIMEOUT}" ]] && echo --timeout "${EVAL_TIMEOUT}") \
    $([[ -n "${EVAL_CONCURRENCY}" ]] && echo --concurrency "${EVAL_CONCURRENCY}") \
    $([[ -n "${EVAL_RETRIES}" && "${EVAL_RETRIES}" -gt 0 ]] && echo --retries "${EVAL_RETRIES}") \
    $([[ "${EVAL_RESUME}" -eq 1 ]] && echo --resume)
fi

# --- Post-run Retention ---
if [[ -f Scripts/post_run_retention.sh ]]; then
  bash Scripts/post_run_retention.sh
fi

echo "Pipeline complete for suite: $SUITE_NAME"