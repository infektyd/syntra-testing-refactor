#!/usr/bin/env bash
set -euo pipefail

export RUN_SYNTRA=1
export ENDPOINT="http://127.0.0.1:8081/v1/chat/completions"
make bench-arc-validation
make bench-gsm8k-test
make bench-aggregate