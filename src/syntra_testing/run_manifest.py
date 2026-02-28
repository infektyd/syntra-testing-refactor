#!/usr/bin/env python3
"""Execute manifest prompts against baseline or SYNTRA clients."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
import warnings
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional, Sequence, Tuple

# Suppress urllib3 OpenSSL warning
warnings.filterwarnings("ignore", message="urllib3 v2 only supports OpenSSL 1.1.1+", category=UserWarning)

try:
    import requests  # type: ignore

    _HAS_REQUESTS = True
except ImportError:  # pragma: no cover - fallback path
    requests = None
    _HAS_REQUESTS = False

if not _HAS_REQUESTS:
    from urllib.error import HTTPError, URLError  # pragma: no cover - fallback path
    from urllib.request import Request, urlopen  # pragma: no cover - fallback path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from Tools.baseline_client import complete_openrouter  # type: ignore
from Benchmarks.CMT.bench.format_cmt import compose_cmt_prompt  # type: ignore

# Hardcoded URLs
SYNTRA_URL = "http://127.0.0.1:8081/v1/chat/completions"
OPENROUTER_API_BASE = "https://openrouter.ai/api/v1"

REQUEST_TIMEOUT_SECONDS = 500


def get_config(client: str) -> Tuple[str, str]:
    """Load configuration from environment variables.

    Returns:
        (api_key, model_name)

    Raises:
        RuntimeError if required env vars not set
    """
    model = os.getenv("LLM_MODEL")
    if not model:
        raise RuntimeError(
            "LLM_MODEL environment variable not set.\n"
            "Please set: export LLM_MODEL='anthropic/claude-3.5-sonnet'"
        )

    api_key = os.getenv("OPENROUTER_API_KEY", "")
    if client == "baseline" and not api_key:
        raise RuntimeError(
            "OPENROUTER_API_KEY environment variable not set.\n"
            "The baseline client requires an OpenRouter key.\n"
            "Please set: export OPENROUTER_API_KEY='sk-or-v1-...'"
        )

    return api_key, model


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a manifest against baseline or SYNTRA clients.")
    parser.add_argument("--manifest", required=True, help="Path to JSONL manifest file.")
    parser.add_argument("--client", choices=["syntra", "baseline"], required=True, help="Client to execute.")
    parser.add_argument(
        "--concurrency",
        type=int,
        default=4,
        help="Concurrency for baseline client (default: 4).",
    )
    return parser.parse_args(argv)


def load_manifest(path: Path) -> Iterator[Dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                record = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path} line {line_number}: {exc}") from exc
            yield record


def prepare_prompts(records: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Construct final prompts, injecting protocol requirements for CMT."""
    prepared: List[Dict[str, Any]] = []
    for record in records:
        suite = str(record.get("suite") or "").lower()
        if suite == "cmt":
            prompt_text = record.get("prompt", "")
            parameters = record.get("parameters", "")
            functions = record.get("functions", "")
            allowed_symbols = record.get("allowed_symbols")
            composite = compose_cmt_prompt(prompt_text, parameters, functions, allowed_symbols)
            updated = dict(record)
            updated.setdefault("prompt_stem", prompt_text)
            updated["prompt"] = composite
            prepared.append(updated)
        else:
            prepared.append(record)
    return prepared


def http_post_json(url: str, headers: Dict[str, str], payload: Dict[str, Any]) -> Tuple[int, str]:
    if _HAS_REQUESTS:
        assert requests is not None  # For type checkers
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=REQUEST_TIMEOUT_SECONDS)
        except requests.exceptions.RequestException as exc:  # type: ignore[attr-defined]
            raise RuntimeError(f"HTTP request to {url} failed: {exc}") from exc
        return response.status_code, response.text

    data = json.dumps(payload).encode("utf-8")
    req = Request(url, data=data, headers=headers, method="POST")  # type: ignore[name-defined]
    try:
        with urlopen(req, timeout=REQUEST_TIMEOUT_SECONDS) as resp:  # type: ignore[name-defined]
            status = getattr(resp, "status", resp.getcode())
            text = resp.read().decode("utf-8")
            return status, text
    except HTTPError as exc:  # type: ignore[name-defined]
        return exc.code, exc.read().decode("utf-8", errors="replace")
    except URLError as exc:  # type: ignore[name-defined]
        raise RuntimeError(f"HTTP request to {url} failed: {exc}") from exc


def compose_syntra_payload(user_prompt: str, model: str) -> Dict[str, Any]:
    """Compose an OpenAI Chat Completions payload for SYNTRA.

    Raises RuntimeError if the prompt is empty or the model is empty.
    """
    if user_prompt is None or str(user_prompt).strip() == "":
        raise RuntimeError("Empty user prompt")

    resolved_model = (model or "").strip()
    if not resolved_model:
        raise RuntimeError("LLM_MODEL is empty")

    return {
        "model": resolved_model,
        "messages": [{"role": "user", "content": user_prompt}],
        "temperature": 0,
    }


def call_syntra(row: Dict[str, Any], model: str, url: str) -> Dict[str, Optional[Any]]:
    """Call the OpenAI-compatible SYNTRA server with proper Chat Completions schema."""
    item_id = row.get("item_id")
    user_prompt = row.get("prompt", "")

    if user_prompt is None or str(user_prompt).strip() == "":
        raise RuntimeError(f"Empty user prompt for item_id={item_id}")

    # Compose payload (will validate model)
    payload = compose_syntra_payload(str(user_prompt), model)

    full_url = url or SYNTRA_URL

    # OpenAI-compatible headers
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer no-key",
    }

    # Optional debug: write outbound payload
    if os.getenv("DEBUG_SYNTRA") == "1":
        try:
            os.makedirs("runs/_debug", exist_ok=True)
            debug_path = os.path.join("runs/_debug", f"syntra_payload_{item_id}.json")
            with open(debug_path, "w", encoding="utf-8") as dbg:
                json.dump(payload, dbg, ensure_ascii=False, indent=2)
        except Exception:
            pass

    start = time.perf_counter()
    status_code, response_text = http_post_json(full_url, headers, payload)
    end = time.perf_counter()
    if status_code >= 400:
        raise RuntimeError(f"SYNTRA endpoint returned status {status_code}: {response_text[:200]}")

    tokens_in: Optional[int] = None
    tokens_out: Optional[int] = None
    text_out: str = (response_text or "").strip()

    try:
        parsed = json.loads(response_text)
    except json.JSONDecodeError:
        parsed = None

    if isinstance(parsed, str):
        text_out = parsed.strip()
    elif isinstance(parsed, dict):
        usage = parsed.get("usage")
        if isinstance(usage, dict):
            prompt_tokens = usage.get("prompt_tokens")
            completion_tokens = usage.get("completion_tokens")
            if isinstance(prompt_tokens, int):
                tokens_in = prompt_tokens
            if isinstance(completion_tokens, int):
                tokens_out = completion_tokens

        choices = parsed.get("choices")
        if isinstance(choices, list) and choices:
            first = choices[0]
            if isinstance(first, dict):
                message = first.get("message")
                if isinstance(message, dict) and "content" in message:
                    text_out = str(message.get("content", "")).strip()
                elif "text" in first:
                    text_out = str(first.get("text", "")).strip()
        elif "content" in parsed:
            text_out = str(parsed.get("content", "")).strip()
        elif "text" in parsed:
            text_out = str(parsed.get("text", "")).strip()
        else:
            # As a last resort, stringify the dict
            text_out = json.dumps(parsed, ensure_ascii=False)
    elif parsed is not None:
        text_out = str(parsed)

    # Fail-fast if response is clearly only priming or empty
    lower_text = text_out.lower().strip()
    if not lower_text:
        raise RuntimeError("Priming-only content; likely missing user message.")

    return {
        "text": text_out,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "latency_ms": (end - start) * 1000,
    }


def parse_gsm8k_answer(text: str) -> Optional[str]:
    matches = re.findall(r"Final Answer:\s*([+-]?\d+(?:\.\d+)?)", text, flags=re.IGNORECASE)
    if not matches:
        return None
    return matches[-1]


def parse_arc_answer(text: str) -> Optional[str]:
    matches = re.findall(r"Final Answer:\s*([A-D])", text, flags=re.IGNORECASE)
    if not matches:
        return None
    return matches[-1].upper()


def parse_cmt_answer(text: str) -> Optional[str]:
    """Extract the first \\boxed{} block from the response."""
    try:
        from Benchmarks.CMT.bench.eval_cmt import extract_boxed_answer  # type: ignore
        content = extract_boxed_answer(text)
        if not content:
            return None
        return f"\\boxed{{{content}}}"
    except (ImportError, Exception):
        return None


def parse_answer(suite: str, text: str) -> Optional[str]:
    text = text or ""
    if suite == "gsm8k":
        return parse_gsm8k_answer(text)
    if suite == "arc_challenge":
        return parse_arc_answer(text)
    if suite == "cmt":
        return parse_cmt_answer(text)
    return None


def fake_completion(client: str, suite: str) -> Dict[str, Optional[Any]]:
    if suite == "gsm8k":
        text = f"{client} FAKE_RUN stub\nFinal Answer: 7"
    elif suite == "arc_challenge":
        text = f"{client} FAKE_RUN stub\nFinal Answer: C"
    else:
        text = f"{client} FAKE_RUN stub\n\\boxed{{OK}}"
    return {"text": text, "tokens_in": 0, "tokens_out": 0}


def run_manifest(path: Path, client: str, api_key: str, model: str, concurrency: int) -> Iterable[Dict[str, Any]]:
    fake_mode = os.getenv("FAKE_RUN") == "1"
    prompts = prepare_prompts(load_manifest(path))
    prompt_index = {str(p.get("item_id")): p for p in prompts}

    results_iterator: Iterable[Dict[str, Any]]

    if fake_mode:
        # Fake mode runs sequentially as it's for testing, not performance.
        def fake_iterator() -> Iterable[Dict[str, Any]]:
            for record in prompts:
                start = time.perf_counter()
                result = fake_completion(client, record.get("suite", "unknown"))
                end = time.perf_counter()
                yield {
                    **record,
                    "response": str(result.get("text") or "").strip(),
                    "tokens_in": result.get("tokens_in"),
                    "tokens_out": result.get("tokens_out"),
                    "latency_ms": (end - start) * 1000,
                    "run_id": os.getenv("RUN_ID", "unknown"),
                    "model": model,
                }
        results_iterator = fake_iterator()
    elif client == "baseline":
        baseline_prompts = [(p["item_id"], p["prompt"]) for p in prompts]
        results_iterator = run_baseline_concurrent(baseline_prompts, model, concurrency)
    elif client == "syntra":
        results_iterator = run_syntra_concurrent(prompts, model, SYNTRA_URL, concurrency)
    else:
        raise ValueError(f"Unsupported client: {client}")

    for result in results_iterator:
        item_id = result.get("item_id")
        # For baseline client, we need to merge back the original record info
        if client == "baseline":
            record = prompt_index.get(str(item_id), {})
            final_record = {**record, **result}
        else:
            final_record = result

        response_text = str(final_record.get("text") or "").strip()
        parsed = parse_answer(str(final_record.get("suite") or ""), response_text)

        yield {
            "item_id": final_record.get("item_id"),
            "suite": final_record.get("suite"),
            "protocol": final_record.get("protocol"),
            "model": model,
            "prompt": final_record.get("prompt"),
            "prompt_stem": final_record.get("prompt_stem"),
            "parameters": final_record.get("parameters"),
            "functions": final_record.get("functions"),
            "allowed_symbols": final_record.get("allowed_symbols"),
            "response": response_text,
            "parsed_answer": parsed,
            "gold": final_record.get("gold"),
            "tokens_in": final_record.get("tokens_in"),
            "tokens_out": final_record.get("tokens_out"),
            "latency_ms": result.get("latency_ms", 0),
            "run_id": os.getenv("RUN_ID", "unknown"),
        }


def run_syntra_concurrent(
    prompts: Iterable[Dict[str, Any]], model: str, url: str, max_concurrency: int
) -> Iterable[Dict[str, Any]]:
    """Run SYNTRA completions with concurrency."""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    with ThreadPoolExecutor(max_workers=max_concurrency) as executor:
        future_to_prompt = {executor.submit(call_syntra, p, model, url): p for p in prompts}
        for future in as_completed(future_to_prompt):
            prompt_info = future_to_prompt[future]
            item_id = prompt_info.get("item_id", "unknown")
            try:
                result = future.result()
                print(f"✓ Completed syntra for item: {item_id}", file=sys.stderr)
                yield {**prompt_info, **result}
            except Exception as exc:
                print(f"✗ Error processing syntra for item {item_id}: {exc}", file=sys.stderr)
                yield {**prompt_info, "text": f"ERROR: {exc}", "tokens_in": 0, "tokens_out": 0}


def run_baseline_concurrent(
    prompts: Iterable[Tuple[str, str]], model: str, max_concurrency: int
) -> Iterable[Dict[str, Any]]:
    """Run baseline completions with concurrency."""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    with ThreadPoolExecutor(max_workers=max_concurrency) as executor:
        future_to_prompt = {
            executor.submit(complete_openrouter, prompt, model): (item_id, prompt)
            for item_id, prompt in prompts
        }
        for future in as_completed(future_to_prompt):
            item_id, prompt = future_to_prompt[future]
            try:
                result = future.result()
                print(f"✓ Completed baseline for item: {item_id}", file=sys.stderr)
                yield {"item_id": item_id, "prompt": prompt, **result}
            except Exception as exc:
                print(f"✗ Error processing baseline for item {item_id}: {exc}", file=sys.stderr)
                yield {"item_id": item_id, "prompt": prompt, "text": f"ERROR: {exc}", "tokens_in": 0, "tokens_out": 0}


def main(argv: Sequence[str]) -> int:
    args = parse_args(argv)
    manifest_path = Path(args.manifest)
    if not manifest_path.exists():
        print(f"ERROR: Manifest not found: {manifest_path}", file=sys.stderr)
        return 1

    try:
        api_key, model = get_config(args.client)
        results = run_manifest(
            manifest_path, args.client, api_key, model, args.concurrency
        )
        for result in results:
            print(json.dumps(result, ensure_ascii=False))
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
