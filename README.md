# Syntra Testing Refactor

A complete Python benchmarking and evaluation framework for LLM systems. Supports GSM8K, ARC, CMT, and custom datasets with grading, visualization, and PDF report generation.

## Features

- Prompt and dataset loading (JSONL/ Hugging Face)
- Automated evaluation runners with concurrency
- Grading and metric calculation
- Visualization (matplotlib) and PDF reports (reportlab + pypdf)
- CMT extraction from PDFs
- Reproducible benchmark pipelines

## Quick Start

1. **Clone and install**
   ```bash
   cd syntra-testing-refactor
   python3 -m venv venv
   source venv/bin/activate  # or venv\Scripts\activate on Windows
   pip install -r requirements.txt
   pip install -e .
   ```

2. **Configure (optional)**
   ```bash
   export OPENAI_API_KEY="sk-..."
   export HF_TOKEN="hf_..."  # for datasets
   mkdir -p data/ runs/
   ```

3. **Run a benchmark**
   ```bash
   # Run full evaluation
   python -m src.syntra_testing.runners.eval_runner --dataset gsm8k --output runs/gsm8k/

   # Generate visualizations and PDF report
   python -m src.syntra_testing.tools.visualization.viz_hf_cmt --input runs/ --output runs/report.pdf
   ```

4. **Run tests**
   ```bash
   pytest tests/ -q
   ```

## Project Layout

- `src/syntra_testing/`: Core package
- `Tools/`: Benchmark and visualization tools
- `prompts/`: Prompt templates
- `benchmarks/`: Configuration and results
- `runs/`: Output directory (gitignored)

## API Keys

Set environment variables for providers:
- `OPENAI_API_KEY`
- `ANTHROPIC_API_KEY` 
- `HF_TOKEN` (for datasets)

See `FIXES.md` for troubleshooting.

## License
MIT
