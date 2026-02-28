import gradio as gr
import json
import requests
import numpy as np
from pathlib import Path
import random

# Load sample prompts (in Space, download from dataset or local)
SAMPLE_PROMPTS_PATH = &quot;prompts/CMT prompts.jsonl&quot;  # Adjust after untar

try:
    with Path(SAMPLE_PROMPTS_PATH).open() as f:
        prompts_list = [json.loads(line) for line in f]
except:
    prompts_list = []  # Fallback

def compute_metrics(response: str) -&gt; dict:
    if not response.strip():
        return {}
    words = response.lower().split()
    unique_ratio = len(set(words)) / len(words) if words else 0
    # Simple repetition penalty
    rep_count = sum(1 for i in range(1, len(words)) if words[i] == words[i-1])
    rep_penalty = 1.0 / (1 + rep_count / max(len(words), 1))
    # Sentences
    sentences = [s.strip() for s in response.split('.') if s.strip()]
    terminal_ratio = sum(1 for s in sentences if s[-1] in '.!?') / len(sentences) if sentences else 0
    coherence = np.mean([unique_ratio, terminal_ratio]) * rep_penalty
    return {
        &quot;unique_word_ratio&quot;: round(unique_ratio, 3),
        &quot;repetition_penalty&quot;: round(rep_penalty, 3),
        &quot;sentence_terminal_ratio&quot;: round(terminal_ratio, 3),
        &quot;coherence_score&quot;: round(coherence, 3)
    }

def load_prompt(idx):
    if 0 &lt;= idx &lt; len(prompts_list):
        ex = prompts_list[int(idx)]
        return ex[&quot;prompt&quot;], ex.get(&quot;solution&quot;, &quot;&quot;)
    return &quot;No prompt&quot;, &quot;&quot;

def run_trial(prompt, endpoint, model, temperature=0.7, max_tokens=1024):
    headers = {
        &quot;Content-Type&quot;: &quot;application/json&quot;,
        # &quot;Authorization&quot;: &quot;Bearer YOUR_API_KEY&quot;  # Add if needed
    }
    data = {
        &quot;model&quot;: model,
        &quot;messages&quot;: [{&quot;role&quot;: &quot;user&quot;, &quot;content&quot;: prompt}],
        &quot;temperature&quot;: temperature,
        &quot;max_tokens&quot;: max_tokens
    }
    try:
        resp = requests.post(f&quot;{endpoint}/v1/chat/completions&quot;, headers=headers, json=data, timeout=60)
        if resp.status_code == 200:
            content = resp.json()[&quot;choices&quot;][0][&quot;message&quot;][&quot;content&quot;]
            metrics = compute_metrics(content)
            return content, metrics
        else:
            return f&quot;Error {resp.status_code}: {resp.text[:200]}&quot;, {}
    except Exception as e:
        return f&quot;Request failed: {str(e)}&quot;, {}

with gr.Blocks(title=&quot;SyntraTesting Bench Demo&quot;) as demo:
    gr.Markdown(&quot;# SyntraTesting Benchmark Runner UI&quot;)
    gr.Markdown(&quot;Select prompt, set endpoint, run eval.&quot;)
    
    prompt_slider = gr.Slider(minimum=0, maximum=len(prompts_list)-1 if prompts_list else 0, step=1, label=&quot;Prompt Index&quot;)
    prompt_text = gr.Textbox(label=&quot;Prompt&quot;, lines=6, interactive=False)
    gold_text = gr.Textbox(label=&quot;Gold Solution&quot;, lines=2, interactive=False)
    
    with gr.Row():
        endpoint_input = gr.Textbox(value=&quot;http://127.0.0.1:8081&quot;, label=&quot;OpenAI-compatible Endpoint&quot;)
        model_input = gr.Textbox(value=&quot;syntra-consciousness&quot;, label=&quot;Model&quot;)
        temp_slider = gr.Slider(0.0, 1.0, 0.7, label=&quot;Temperature&quot;)
    
    run_btn = gr.Button(&quot;Run Trial&quot;, variant=&quot;primary&quot;)
    
    response_text = gr.Textbox(label=&quot;Model Response&quot;, lines=8)
    metrics_json = gr.JSON(label=&quot;Computed Metrics&quot;)
    
    prompt_slider.change(
        fn=load_prompt,
        inputs=prompt_slider,
        outputs=[prompt_text, gold_text]
    )
    
    run_btn.click(
        fn=run_trial,
        inputs=[prompt_text, endpoint_input, model_input, temp_slider],
        outputs=[response_text, metrics_json]
    )

if __name__ == &quot;__main__&quot;:
    demo.launch()
