#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CTX="$ROOT/.copilot_context.md"

# Build context
bash "$ROOT/Scripts/build_copilot_context.sh"

echo "=== Copilot context ready: $CTX ==="
echo

# Prefer GitHub CLI Copilot chat if available
if command -v gh >/dev/null 2>&1; then
  if ! gh extension list | grep -q "github/gh-copilot"; then
    echo "Installing gh copilot extension..."
    gh extension install github/gh-copilot
  fi

  echo "Launching Copilot chat with preloaded context..."
  # Try stdin mode first (keeps formatting); fallback to -p if needed
  if gh copilot chat --help 2>&1 | grep -q -- "--stdin"; then
    gh copilot chat --stdin < "$CTX"
  else
    gh copilot chat -p "$(cat "$CTX")"
  fi
else
  echo "⚠️  GitHub CLI not found. Open the context manually:"
  echo "---------------------------------------------------"
  echo "less $CTX"
  echo
  echo "Copy & paste the content above into your Copilot Chat (VS Code/JetBrains) to seed memory."
fi