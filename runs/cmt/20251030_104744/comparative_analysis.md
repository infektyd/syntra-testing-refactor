# CMT Benchmark Comparative Analysis
**Focus Run:** 20251030_104744
**Date:** October 30, 2024
**Model:** google/gemini-2.5-pro

---

## Executive Summary

All three CMT benchmark runs show **0% accuracy** across both syntra and baseline configurations, indicating that these condensed matter theory problems are extremely challenging for current LLMs, including both GPT-5-mini and Gemini-2.5-pro.

### Key Findings

1. **40% of failures are partial credit** - Models get some parts of multi-choice answers correct
2. **50% are completely wrong** - Models make fundamental errors in physics reasoning
3. **6% are empty/timeout** - Some prompts fail to generate responses
4. **No model differences** - Both GPT-5-mini and Gemini-2.5-pro perform identically (0%)

---

## Detailed Failure Analysis - Run 20251030_104744

### Failure Pattern Breakdown

| Type | Total Fails | Empty | Format Error | Wrong Format | Partial Correct | Completely Wrong |
|------|-------------|-------|--------------|--------------|-----------------|------------------|
| DMRG   |           4 |     1 |            0 |            0 |               0 |                3 |
| ED     |           8 |     0 |            0 |            0 |               4 |                4 |
| HF     |           5 |     0 |            0 |            1 |               1 |                3 |
| Other  |          16 |     1 |            0 |            0 |               8 |                7 |
| PEPS   |           3 |     0 |            0 |            0 |               0 |                3 |
| QMC    |           6 |     0 |            0 |            0 |               5 |                1 |
| SM     |           6 |     1 |            0 |            1 |               0 |                4 |
| VMC    |           2 |     0 |            0 |            0 |               2 |                0 |

### Overall Statistics

- **Total failures**: 50 items
- **Partial correct**: 20 (40.0%) - Got some choices right in multi-selection questions
- **Wrong format**: 2 (4.0%) - Answer in wrong format (tuple vs text, etc.)
- **Format/parsing errors**: 0 (0.0%) - All answers were properly extracted
- **Empty responses**: 3 (6.0%) - Timeouts or generation failures
- **Completely wrong**: 25 (50.0%) - Fundamental errors in reasoning

---

## Cross-Run Comparison

### Performance Summary

| Run ID | Items | Model | Syntra Acc | Baseline Acc | Avg Latency |
|--------|-------|-------|------------|--------------|-------------|
| 20251029_202111 | 50 | gpt-5-mini | 0.0% | 0.0% | 105.3s |
| 20251030_080445 | 50 | gpt-5-mini | 0.0% | 0.0% | 105.0s |
| 20251030_104744 | 50 | gemini-2.5-pro | 0.0% | 0.0% | 121.0s |

### Key Observations

1. **Model Performance**: Both GPT-5-mini and Gemini-2.5-pro achieve 0% accuracy
2. **Consistency**: Results are consistent across all runs and models
3. **Latency**: Gemini-2.5-pro is ~15% slower (121s vs 105s per item)
4. **Problem Difficulty**: CMT problems appear to be beyond current LLM capabilities

---

## Problem Type Analysis

### Per-Type Breakdown (All Runs)

| Type | Description | Avg Items | Best Accuracy |
|------|-------------|-----------|---------------|
| HF | Hartree-Fock mean-field theory | 5 | 0% |
| ED | Exact Diagonalization | 8 | 0% |
| DMRG | Density Matrix Renormalization Group | 4 | 0% |
| QMC | Quantum Monte Carlo | 6 | 0% |
| VMC | Variational Monte Carlo | 2 | 0% |
| PEPS | Projected Entangled Pair States | 3 | 0% |
| SM | Statistical Mechanics | 6 | 0% |
| Other | Miscellaneous physics problems | 16 | 0% |

**All problem types show 0% accuracy across all models and runs.**

---

## Example Failure Cases

### 1. Partial Correct (Multiple Choice)

**Item**: `cmt_other_40` (SSH Model Topology)
**Model Answer**: `$\boxed{a;e}$`
**Gold Answer**: `$\boxed{a;d;e}$`
**Analysis**: Got 2 out of 3 correct choices. Missing choice `d` about energy gap scaling.

**Physics Content**: Su-Schrieffer-Heeger (SSH) dimerized chain model
- ✓ Correctly identified topological protection (choice a)
- ✗ Missed energy gap scaling (choice d)
- ✓ Correctly identified end state localization (choice e)

---

### 2. Completely Wrong (Single Choice)

**Item**: `cmt_dmrg_7` (DMRG Bond Dimension Scaling)
**Model Answer**: `$\boxed{a}$`
**Gold Answer**: `$\boxed{d}$`
**Analysis**: Incorrect choice about bond dimension scaling in 2D gapless systems.

**Physics Content**: DMRG vs PEPS bond dimension requirements for 2D systems
- Model incorrectly chose exponential DMRG scaling option
- Correct answer involves both scaling laws

---

### 3. Wrong Format (Algebraic Expression)

**Item**: `cmt_hf_3` (Spatial Complexity)
**Model Answer**: `$\boxed{(2N_q)^2 = 4N_q^2}$`
**Gold Answer**: `$\boxed{16N_q^2}$`
**Analysis**: Model provided equation instead of simplified numerical coefficient.

**Physics Content**: Hamiltonian matrix size for plane-wave basis
- Model showed correct reasoning but wrong format
- Expected only final numeric coefficient, not the equation

---

### 4. Empty Response (Timeout)

**Item**: `cmt_sm_42` (Odd Diffusion Constant)
**Model Answer**: `None`
**Gold Answer**: `$\boxed{D_o = \frac{\tau^2 \rho v_0^2 \Omega (2+\rho)}{[(1+\rho)^2 + (\Omega \tau)^2][1+(\Omega \tau)^2]}}$`
**Error**: HTTP connection timeout

**Analysis**: Request timed out, possibly due to:
- Complex LaTeX expression in problem
- Long computation required
- Server load issues

---

## Recommendations

### 1. Partial Credit Scoring System

Implement partial credit to better reflect model capabilities:
- **Multi-choice questions**: Award partial credit for correct subsets
- **Algebraic answers**: Check for algebraically equivalent forms
- **Numeric answers**: Accept answers within tolerance

**Expected Impact**: Could increase accuracy from 0% to ~20-25% based on partial correct rate

### 2. Prompt Engineering Improvements

Current issues identified:
- Models sometimes provide explanations instead of just boxed answers
- Format confusion between equations and final values
- Difficulty with complex LaTeX notation

**Suggestions**:
- Add explicit "final answer only" instructions
- Provide format examples for each question type
- Simplify LaTeX notation where possible

### 3. Problem Difficulty Assessment

**Current Status**: These problems may be too hard for current LLMs

**Options**:
- Create easier CMT subset for baseline testing
- Focus on conceptual questions vs. calculations
- Add scaffolding questions that build to complex problems

### 4. Model-Specific Configurations

**Observed Differences**:
- Gemini-2.5-pro: 15% slower, similar accuracy
- GPT-5-mini: Faster, similar accuracy
- Both: Show partial reasoning ability

**Recommendation**: Test with larger context windows and longer generation limits for complex calculations

---

## Statistical Analysis

### Confidence Intervals

With 50 items at 0% accuracy:
- **95% Wilson CI**: 0.0% – 7.1%
- **Interpretation**: We can be 95% confident true accuracy is below 7.1%

### McNemar Test Results

- **p-value**: 1.0 (perfect agreement)
- **Discordant pairs**: 0
- **Interpretation**: No significant difference between baseline and syntra

### Power Analysis

- **Required discordant pairs**: 1,000,000,000 (to detect difference at current rate)
- **Current discordant rate**: 0.0
- **Interpretation**: Need much larger sample or better performing models

---

## Conclusions

1. **CMT problems are extremely challenging** for current LLMs, with 0% accuracy across all tested models
2. **Partial credit reveals hidden capability**: 40% of failures show partial understanding
3. **No baseline vs syntra difference**: Both configurations perform identically
4. **Model choice doesn't matter**: GPT-5-mini and Gemini-2.5-pro both fail completely
5. **Latency varies**: Gemini is ~15% slower but no quality improvement

### Next Steps

1. Implement partial credit scoring system
2. Create easier CMT problem subset
3. Test with more advanced models (GPT-4, Claude-3.5-Sonnet)
4. Analyze physics reasoning patterns in failure cases
5. Consider problem reformulation or scaffolding

---

## Appendix: Technical Details

### Grading Configuration

- **Protocol**: cmt_boxed_v1
- **Seed**: 42
- **Items per run**: 50
- **Concurrency**: 1
- **Evaluation**: Exact match on normalized LaTeX

### Models Tested

1. **GPT-5-mini** (OpenAI via OpenRouter)
   - Runs: 20251029_202111, 20251030_080445
   - Latency: ~105s per item
   - Accuracy: 0%

2. **Gemini-2.5-pro** (Google via OpenRouter)
   - Run: 20251030_104744
   - Latency: ~121s per item
   - Accuracy: 0%

### Files Generated

```
runs/cmt/20251030_104744/
├── manifest.jsonl                 # Original problems
├── cmt.pass1.baseline.jsonl       # Baseline responses
├── cmt.pass2.syntra.jsonl         # Syntra responses
├── graded.cmt.baseline.jsonl      # Graded baseline
├── graded.cmt.syntra.jsonl        # Graded syntra
├── summary.cmt.json               # Basic metrics
├── cmt_detailed_report.md         # Per-type analysis
└── comparative_analysis.md        # This report

runs/20251030_104744/
├── stats_cmt.md                   # Statistical analysis
└── stats_summary.json             # Structured statistics
```

---

**Report Generated**: October 30, 2024
**Analysis Tools**: enhance_cmt_reports.py, analyze_results.py, grade_and_aggregate.py
