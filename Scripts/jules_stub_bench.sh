#!/usr/bin/env bash
set -euo pipefail

export SYNTRA_TEST_MODE=1
make bench-arc-validation
make bench-gsm8k-test
make bench-aggregate

echo "## Stub Benchmark Summary"
echo ""
cat runs/summary/benchmarks_overview.md