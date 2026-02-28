---
license: mit
task_categories:
  - text-generation
  - evaluation
tags:
  - ai-evals
  - benchmark
  - reasoning
  - syntra
  - arc
  - gsm8k
  - condensed-matter-theory
---

# SyntraTesting Evals v4

Complete benchmark suite for evaluating AI models on advanced reasoning tasks.

## Contents

| Split | File | Description |
|-------|------|-------------|
| prompts | `data/splits/prompts.tar.gz` (~60KB) | CMT prompts, coherence structures, drift resilience, logic, ethics |
| benchmarks | `data/splits/benchmarks.tar.gz` (~36KB) | ARC, CMT, GSM8K benchmark data and utilities |
| runs | `data/splits/runs.tar.gz` (~4.4MB) | Sample evaluation runs with graded results |
| resources | `data/splits/resources.tar.gz` (~500KB) | Official CMT answers, type maps, utilities |

## Key Files (after extraction)

- `prompts/suites/hf_cmt.jsonl` - Main CMT benchmark prompts
- `prompts/suites/official_cmt.jsonl` - Official CMT evaluation set  
- `resources/official_cmt_answers.jsonl` - Gold standard answers
- `Tools/grading/` - Grading scripts for evaluating model outputs

## Usage

```bash
# Download and extract
huggingface-cli download Infektyd/syntra-testing-evals-v4 --repo-type dataset --local-dir syntra-evals
cd syntra-evals/data/splits
tar xzf prompts.tar.gz
tar xzf benchmarks.tar.gz
tar xzf resources.tar.gz
```

## Related

- **GitHub**: https://github.com/infektyd/syntra-testing-refactor
- **Author**: Hans Axelsson
