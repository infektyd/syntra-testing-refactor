#!/usr/bin/env bash
# Verify that required environment variables for live runs are set.

# Source .env file from project root if it exists
if [ -f "$(dirname "$0")/../.env" ]; then
  echo "Sourcing .env file..."
  set -o allexport
  # shellcheck source=/dev/null
  source "$(dirname "$0")/../.env"
  set +o allexport
fi

# Provide defaults for sampling parameters
: "${SEED:=42}"
: "${N:=50}"
export SEED
export N

# Check for required variables
missing_vars=()
[[ -z "$OPENROUTER_API_KEY" ]] && missing_vars+=("OPENROUTER_API_KEY")
[[ -z "$LLM_MODEL" ]] && missing_vars+=("LLM_MODEL")

if [ ${#missing_vars[@]} -gt 0 ]; then
  echo "Missing required environment variables:" >&2
  for var in "${missing_vars[@]}"; do
    echo "  - $var" >&2
  done
  echo "" >&2
  echo "Set the following environment variables:" >&2
  echo "  export OPENROUTER_API_KEY='sk-or-v1-...'" >&2
  echo "  export LLM_MODEL='anthropic/claude-3.5-sonnet'" >&2
  echo "" >&2
  echo "Or create a .env file in the project root with these variables." >&2
  exit 1
fi

echo "✓ Environment variables verified."
echo "  OPENROUTER_API_KEY: (set)"
echo "  LLM_MODEL: $LLM_MODEL"
echo ""
echo "Hardcoded configuration:"
echo "  OpenRouter API: https://openrouter.ai/api/v1"
echo "  SYNTRA Server: http://127.0.0.1:8081/v1/chat/completions"
exit 0
