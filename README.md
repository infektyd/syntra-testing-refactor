# Syntra Testing Refactor

Syntra Testing Refactor is a Python framework for benchmarking, testing, and evaluating LLM-based systems. It provides tools for running standardized evaluations (GSM8K, ARC, CMT), dataset handling, prompt management, and performance analysis.

## Features

- Standardized benchmark runners for multiple datasets
- Modular tool and prompt management system
- Automated evaluation and grading pipelines
- Dataset caching and subsampling utilities
- Comprehensive logging and reporting
- Docker and CLI support for reproducible runs

## Architecture

The framework is organized into:

- `src/`: Core Python packages for testing and tools
- `Tools/`: Benchmark and evaluation tools
- `prompts/`: Standardized prompt suites
- `benchmarks/`: Evaluation scripts and metrics
- `runs/`: Output directory (excluded from git)

## Installation

```bash
pip install -e .
# or
pip install -r requirements.txt
```

## Usage

Run benchmarks using the Makefile or Python CLI:

```bash
make benchmark-gsm8k
# or
python -m src.syntra_testing.run_benchmark --dataset gsm8k
```

See `BENCHMARKS.md` for detailed evaluation results and methodology.

## License

See LICENSE file.
