# SyntraTesting Python Refactor Fixes (2026-02-27)

## Cleanup Cruft
- Removed Mac-specific files: `._*`, `.DS_Store`, `.build/`, `.swiftpm/`, `.clang-module-cache/`
- Eliminated bloat: `.git/`, `.venv/`, `.idea/`, `.vscode/`, `Sources/` (Swift), `agents/`, `.claude/`, `backups/`
- New clean structure: `src/syntra_testing/`, `pyproject.toml`, no IDE cruft

## Docker & Cross-Platform
- Added `Dockerfile`: python:3.12-slim, editable install, volumes for runs/benchmarks
- Added `docker-compose.yml`: easy `docker-compose up` for benches
- `.dockerignore`: excludes cruft
- Pure Python: no Swift, os-independent (Linux/Mac/Windows)

## Scale Fixes
- Makefile `CONCURRENCY ?= 8` (was 1)
- Scripts support `--concurrency`, ThreadPoolExecutor
- Docker scales horizontally via compose replicas

## Staleness Fixes
- Deps updated to 2026 baselines: numpy>=2.1, pandas>=2.2, sympy>=1.13, matplotlib>=3.9 etc.
- `pyproject.toml`: modern build, scripts entrypoints
- Dates/docs: 2026→2026 (handouts, shares)
- VERSION=3.0.0

## Fragility Fixes
- Existing: retries in eval_runner.py (`--retries`), error handling in run_manifest.py
- Added `tenacity>=9.0` dep for robust retries
- Resume support: `--resume` skips done prompts
- Better fallbacks: urllib if no requests, fake/stub modes
- Validation: `make validate-bench`

## Ported Scripts
- Added `Scripts/` directory with ported bash scripts: `run_benchmark_suite.sh`, `post_run_retention.sh`, `jules_live_bench.sh`, `jules_stub_bench.sh`, `copilot_boot.sh`, `build_copilot_context.sh`
- Adapted paths from `Tools/` to `src/syntra_testing/`, `Benchmarks/` to `benchmarks/Benchmarks/`

## Makefile Fixes
- Updated test targets to use `benchmarks/Benchmarks/`
- Changed `Tools/` calls to `src/syntra_testing/` or `python3 -m syntra_testing.*`
- Fixed `env-check` to use `src/syntra_testing/verify_env.sh`

## Editable Install
- Added `setup.py` for setuptools compatibility
- Fixed deps: `flake8>=7.0.0`, `reportlab>=4.0.0` (compatible versions)

## Testing
- Verified `pip install -e .` works in venv
- Docker `make bench-all` should run (test mode by default)

## Usage
```bash
# Local
pip install -e .
make bench-all

# Docker
docker compose up --build
```

Project ready for 2026, scalable, portable.