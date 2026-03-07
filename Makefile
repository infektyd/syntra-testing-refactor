.PHONY: test test-arc test-gsm8k test-cmt test-all bench-arc-validation bench-gsm8k-test bench-cmt-test bench-aggregate bench-clean bench-all bench-live env-check run-gsm8k-live run-arc-live run-cmt-live jules-stub jules-live copilot lint

# Default modes (override on make command line)
SYNTRA_TEST_MODE ?= 1
RUN_SYNTRA       ?= 0
export SYNTRA_TEST_MODE
export RUN_SYNTRA

RUN_ID ?= $(shell date +%Y%m%d_%H%M%S)
SEED ?= 42
N ?= 50
CONCURRENCY ?= 8

# Runner helper
RUN_SUITE := bash Scripts/run_benchmark_suite.sh

# Print the current mode (LIVE vs TEST)
PRINT_MODE = @echo ">>> MODE: $(shell if [ "$(RUN_SYNTRA)" -eq "1" ] && [ "$(SYNTRA_TEST_MODE)" -eq "0" ]; then echo LIVE; else echo TEST; fi )"

test: test-all

test-arc:
	@SYNTRA_TEST_MODE=1 pytest benchmarks/Benchmarks/ARC/tests -q

test-gsm8k:
	@SYNTRA_TEST_MODE=1 pytest benchmarks/Benchmarks/GSM8K/tests -q

test-cmt:
	@SYNTRA_TEST_MODE=1 pytest benchmarks/Benchmarks/CMT/tests -q

test-all:
	@SYNTRA_TEST_MODE=1 pytest benchmarks/ -v

bench-arc-validation:
	$(PRINT_MODE)
	$(RUN_SUITE) --suite arc_challenge --split validation

bench-gsm8k-test:
	$(PRINT_MODE)
	$(RUN_SUITE) --suite gsm8k --split test

bench-cmt-test:
	$(PRINT_MODE)
	$(RUN_SUITE) --suite cmt

# Aggregate benchmark results (preserves runs/summary/* outputs)
bench-aggregate:
	python3 src/syntra_testing/visualization/aggregate_benchmarks.py || true

# Remove stale run artifacts (keeps runs/summary/* intact)
bench-clean:
	@echo "Cleaning stale benchmark artifacts (preserving summaries)..."
	@find runs -mindepth 1 -maxdepth 1 ! -name "summary" -exec rm -rf {} + 2>/dev/null || true
	@echo "✓ Cleaned. Summaries preserved in runs/summary/"

bench-all: bench-arc-validation bench-gsm8k-test bench-cmt-test bench-aggregate

# Environment and live dual-run pipeline
env-check:
	./src/syntra_testing/verify_env.sh

run-gsm8k-live: env-check
	mkdir -p "runs/gsm8k/$(RUN_ID)"
	python3 -m syntra_testing.gen_manifest --suite gsm8k --n "$(N)" --seed "$(SEED)" > "runs/gsm8k/$(RUN_ID)/manifest.jsonl"
	python3 -m syntra_testing.run_manifest --manifest "runs/gsm8k/$(RUN_ID)/manifest.jsonl" --client baseline --concurrency "$(CONCURRENCY)" > "runs/gsm8k/$(RUN_ID)/gsm8k.pass1.baseline.jsonl"
	python3 -m syntra_testing.run_manifest --manifest "runs/gsm8k/$(RUN_ID)/manifest.jsonl" --client syntra --concurrency "$(CONCURRENCY)" > "runs/gsm8k/$(RUN_ID)/gsm8k.pass2.syntra.jsonl"
	python3 -m syntra_testing.grade_and_aggregate --suite gsm8k --dir "runs/gsm8k/$(RUN_ID)"

run-arc-live: env-check
	mkdir -p "runs/arc_challenge/$(RUN_ID)"
	python3 -m syntra_testing.gen_manifest --suite arc_challenge --n "$(N)" --seed "$(SEED)" > "runs/arc_challenge/$(RUN_ID)/manifest.jsonl"
	python3 -m syntra_testing.run_manifest --manifest "runs/arc_challenge/$(RUN_ID)/manifest.jsonl" --client baseline --concurrency "$(CONCURRENCY)" > "runs/arc_challenge/$(RUN_ID)/arc.pass1.baseline.jsonl"
	python3 -m syntra_testing.run_manifest --manifest "runs/arc_challenge/$(RUN_ID)/manifest.jsonl" --client syntra --concurrency "$(CONCURRENCY)" > "runs/arc_challenge/$(RUN_ID)/arc.pass2.syntra.jsonl"
	python3 -m syntra_testing.grade_and_aggregate --suite arc_challenge --dir "runs/arc_challenge/$(RUN_ID)"

run-cmt-live: env-check
	mkdir -p "runs/cmt/$(RUN_ID)"
	python3 -m syntra_testing.gen_manifest --suite cmt --n "$(N)" --seed "$(SEED)" > "runs/cmt/$(RUN_ID)/manifest.jsonl"
	python3 -m syntra_testing.run_manifest --manifest "runs/cmt/$(RUN_ID)/manifest.jsonl" --client baseline --concurrency "$(CONCURRENCY)" > "runs/cmt/$(RUN_ID)/cmt.pass1.baseline.jsonl"
	python3 -m syntra_testing.run_manifest --manifest "runs/cmt/$(RUN_ID)/manifest.jsonl" --client syntra --concurrency "$(CONCURRENCY)" > "runs/cmt/$(RUN_ID)/cmt.pass2.syntra.jsonl"
	python3 -m syntra_testing.grade_and_aggregate --suite cmt --dir "runs/cmt/$(RUN_ID)"

# Live run with 50-sample stratified prompts (per suite)
bench-live: env-check
	@echo "Starting LIVE benchmark pipeline (50 stratified samples for baseline and syntra)"
	@RUN_SYNTRA=1 SYNTRA_TEST_MODE=0 make run-gsm8k-live run-arc-live run-cmt-live
	@echo "GSM8K summary: runs/gsm8k/$(RUN_ID)/summary.gsm8k.json"
	@echo "ARC summary: runs/arc_challenge/$(RUN_ID)/summary.arc.json"
	@echo "CMT summary: runs/cmt/$(RUN_ID)/summary.cmt.json"

bench-test:
	@echo "Starting TEST benchmark pipeline (using stubs)"
	@RUN_SYNTRA=0 SYNTRA_TEST_MODE=1 make bench-arc-validation bench-gsm8k-test bench-aggregate

# Validate prompts/answers across suites
validate-bench:
	python3 src/syntra_testing/runners/validate_bench_prompts.py --suites all

jules-stub:
	bash Scripts/jules_stub_bench.sh

jules-live:
	bash Scripts/jules_live_bench.sh

# Launch Copilot CLI with preloaded context
copilot:
	bash Scripts/copilot_boot.sh

lint:
	cd Tools && python3 -m py_compile grading/*.py runners/*.py

.PHONY: smoke-syntra-payload
smoke-syntra-payload:
	@mkdir -p runs/_debug
	@python3 src/syntra_testing/smoke_syntra_payload.py > runs/_debug/last_payload.json
	@echo "Wrote runs/_debug/last_payload.json"
	@python3 -c "import json,sys; p=json.load(open('runs/_debug/last_payload.json')); assert p['messages'][0]['content'], 'User message empty'; print('SYNTRA payload looks correct.')"
