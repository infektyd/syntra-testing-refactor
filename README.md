# SyntraTesting: Benchmark Suite &amp; Dataset for Syntra AI Models

## Package (Python CLI)
Migrated from Swift. See usage in original README section below.

## HF Dataset
Prepped for Hugging Face Datasets: prompts, sample runs, benchmarks.

**Dataset Config:** `syntra-evals`
- **prompts**: CMT/physics/math prompts (JSONL)
- **runs**: Sample model outputs &amp; stats (JSONL/MD)
- **benchmarks**: Per-task dirs (ARC, CMT, GSM8K)

Data compressed as TAR.GZ in `data/splits/`.

### Load Dataset
```bash
# Untar first
cd data/splits
tar xzf prompts.tar.gz
tar xzf runs.tar.gz
tar xzf benchmarks.tar.gz
```

```python
from datasets import load_dataset

# Local after untar
ds = load_dataset(&quot;json&quot;, data_files={&quot;train&quot;: &quot;data/splits/prompts/prompts/CMT prompts.jsonl&quot;})

# Or HF repo (after upload)
ds = load_dataset(&quot;syntraTesting/syntra-testing-evals&quot;, &quot;syntra-evals&quot;)
prompt = ds[&quot;prompts&quot;][0][&quot;prompt&quot;]
```

See [card.yaml](card.yaml) for metadata.

### Gradio Demo (Bench Run UI)
Standalone Space: [link after upload]

Run locally:
```bash
cd demos
pip install -r requirements_space.txt
python app.py
```

Select prompt from CMT suite, input local Syntra endpoint (e.g. http://127.0.0.1:8081), run trial, get metrics.

## Upload to HF Datasets
```bash
huggingface-cli login  # token with write access

# Create dataset repo at https://huggingface.co/new-dataset?repo-type=dataset (e.g. syntraTesting/syntra-testing-evals)

# From project root
huggingface-cli upload syntraTesting/syntra-testing-evals data/ card.yaml README.md Makefile pyproject.toml Sources/ --repo-type dataset --include=&quot;data/*&quot; --exclude=&quot;data/splits/*.tar.gz/*&quot;  # or specific

# Better: git clone https://huggingface.co/datasets/syntraTesting/syntra-testing-evals
# cp -r data/ card.yaml README.md ...
# git add . &amp;&amp; git commit -m &quot;Add data&quot; &amp;&amp; git push
```

## Original Package Usage
[Original content...]

# Migrated syntraTesting Python Version
... (paste original README content)
