#!/usr/bin/env python3

import os
import sys
import json
import time
import argparse
import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Optional
import re

# Try requests, fall back to urllib
try:
    import requests  # type: ignore
    _HAS_REQUESTS = True
except Exception:
    _HAS_REQUESTS = False
    import urllib.request as _urllib_request
    import urllib.error as _urllib_error


def read_prompts(path: str) -> List[Dict[str, Any]]:
    prompts = []
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                j = json.loads(line)
                prompts.append(j)
            except json.JSONDecodeError:
                # fallback to raw content lines
                prompts.append({'id': None, 'content': line})
    return prompts


def resolve_prompt_id(record: Dict[str, Any], idx: int, suite: str) -> str:
    """Derives a stable prompt identifier for downstream grading."""

    for key in ("prompt_id", "id"):
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, (int, float)):
            return str(int(value))

    index = record.get("index")
    if isinstance(index, int):
        prompt_type = record.get("type")
        if isinstance(prompt_type, str) and prompt_type.strip():
            prefix = f"{suite.strip().lower()}_{prompt_type.strip().lower()}"
        else:
            prefix = suite.strip().lower() or "prompt"
        return f"{prefix}_{index:03d}"

    if isinstance(index, str) and index.isdigit():
        return f"{suite.strip().lower()}_{int(index):03d}"

    fallback = record.get("idx")
    if isinstance(fallback, (int, float)):
        return str(int(fallback))
    if isinstance(fallback, str) and fallback.strip():
        return fallback.strip()

    return f"{suite.strip().lower()}_{idx:03d}"


def call_server_requests(server: str, payload: Dict[str, Any], timeout: Optional[float]):
    url = server.rstrip('/') + '/v1/chat/completions'
    headers = {'Content-Type': 'application/json'}
    resp = requests.post(url, json=payload, headers=headers, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def call_server_urllib(server: str, payload: Dict[str, Any], timeout: Optional[float]):
    url = server.rstrip('/') + '/v1/chat/completions'
    data = json.dumps(payload).encode('utf-8')
    req = _urllib_request.Request(url, data=data, headers={'Content-Type': 'application/json'})
    with _urllib_request.urlopen(req, timeout=timeout) as resp:
        body = resp.read()
        return json.loads(body.decode('utf-8'))


def extract_assistant_text(resp_json: Dict[str, Any]) -> str:
    # Handle OpenAI-like chat completions
    if not isinstance(resp_json, dict):
        return str(resp_json)
    choices = resp_json.get('choices')
    if choices and isinstance(choices, list) and len(choices) > 0:
        first = choices[0]
        # Chat message style
        if 'message' in first and isinstance(first['message'], dict):
            content = first['message'].get('content') or first['message'].get('text')
            if content:
                return content
        # Legacy completions style
        if 'text' in first:
            return first.get('text', '')
    # Fallbacks
    if 'message' in resp_json and isinstance(resp_json['message'], dict):
        return resp_json['message'].get('content', '')
    # Last resort: try 'output_text' or 'output'
    return str(resp_json.get('output_text') or resp_json.get('output') or '')


def normalize_arc(text: str) -> str:
    if not text:
        return ''
    # Look for single letter A-D
    m = re.search(r'([A-Da-d])\b', text)
    if m:
        return m.group(1).upper()
    # Try first character that is a letter
    m2 = re.search(r'[A-Za-z]', text)
    if m2:
        c = m2.group(0).upper()
        if c in 'ABCD':
            return c
    return text.strip()


def normalize_gsm8k(text: str) -> str:
    if not text:
        return ''
    # Find numeric tokens, prefer last
    nums = re.findall(r'[-+]?\d[\d,\.]*', text)
    if not nums:
        # No numeric token found; return stripped text
        return text.strip()
    last = nums[-1]
    cleaned = last.replace(',', '')
    return cleaned


def normalize_cmt(text: str) -> str:
    return text.strip()


def worker(idx: int, record: Dict[str, Any], server: str, timeout: Optional[float], model_name: Optional[str], suite: str, split: str):
    content = record.get('content') or record.get('prompt') or record.get('text') or ''
    rid = resolve_prompt_id(record, idx, suite)
    payload = {
        "messages": [{"role": "user", "content": content}]
    }
    if model_name:
        payload['model'] = model_name

    start = time.time()
    try:
        if _HAS_REQUESTS:
            resp_json = call_server_requests(server, payload, timeout)
        else:
            resp_json = call_server_urllib(server, payload, timeout)

        elapsed = (time.time() - start) * 1000.0
        text = extract_assistant_text(resp_json)

    except Exception as e:
        elapsed = (time.time() - start) * 1000.0
        text = f"__ERROR__ {e}"

    # Normalize
    if suite.startswith('arc'):
        norm = normalize_arc(text)
    elif suite.startswith('gsm8k'):
        norm = normalize_gsm8k(text)
    else:
        norm = normalize_cmt(text)

    meta = {
        "suite": suite,
        "split": split,
        "backend": os.environ.get('SYNTRA_BACKEND', server),
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z"
    }

    out = {
        "id": rid,
        "prompt_id": rid,
        "pred": norm,
        "raw": text,
        "response": text,
        "latency_ms": float(elapsed),
        "meta": meta
    }

    return out, elapsed


def main():
    parser = argparse.ArgumentParser(description="Evaluate runner prompts against SyntraVaporServer and produce pass1.jsonl")
    parser.add_argument('--suite', required=True)
    parser.add_argument('--split', required=True)
    parser.add_argument('--prompts', required=True)
    parser.add_argument('--out', required=True)
    parser.add_argument('--server', default='http://127.0.0.1:8081')
    parser.add_argument('--concurrency', type=int, default=4)
    parser.add_argument('--timeout', type=float, default=30.0)
    parser.add_argument('--retries', type=int, default=0, help='Retries per prompt on error/timeout')
    parser.add_argument('--resume', action='store_true', help='Skip prompts already present in output file')
    parser.add_argument('--model-name', type=str, default=None)

    args = parser.parse_args()

    prompts = read_prompts(args.prompts)
    if not prompts:
        print("No prompts found in", args.prompts)
        sys.exit(1)

    # Resume support: collect existing ids from output file if present
    existing_ids = set()
    if args.resume and os.path.exists(args.out):
        try:
            with open(args.out, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        j = json.loads(line)
                        eid = j.get('id') or j.get('prompt_id')
                        if isinstance(eid, (str, int, float)):
                            existing_ids.add(str(eid))
                    except Exception:
                        continue
        except Exception:
            pass

    # Build list of (index, record) to evaluate, skipping those already completed
    eval_items = []
    for i, rec in enumerate(prompts):
        rid = resolve_prompt_id(rec, i, args.suite)
        if args.resume and rid in existing_ids:
            continue
        eval_items.append((i, rec))

    total = len(eval_items)
    skipped = len(prompts) - total
    print(f"Evaluating {total} prompts with concurrency={args.concurrency} server={args.server} (skipped {skipped} already done)")

    results = []
    latencies = []

    def do_one(i: int, rec: Dict[str, Any]):
        attempts = max(0, int(args.retries)) + 1
        last = None
        for attempt in range(attempts):
            out, elapsed = worker(i, rec, args.server, args.timeout, args.model_name, args.suite, args.split)
            last = (out, elapsed)
            # Treat responses beginning with __ERROR__ as retryable
            if isinstance(out.get('raw'), str) and out['raw'].startswith('__ERROR__'):
                if attempt < attempts - 1:
                    # Simple backoff: 2^attempt seconds, capped
                    import time as _t
                    _t.sleep(min(8.0, 2.0 ** attempt))
                    continue
            break
        return last

    with ThreadPoolExecutor(max_workers=args.concurrency) as ex:
        futures = {ex.submit(do_one, i, rec): i for (i, rec) in eval_items}

        with open(args.out, 'w', encoding='utf-8') as out_f:
            for fut in as_completed(futures):
                i = futures[fut]
                try:
                    out_record, elapsed = fut.result()
                except Exception as e:
                    print(f"[{i+1}/{total}] Error during evaluation: {e}")
                    out_record = {"id": i, "pred": "", "raw": f"__ERROR__ {e}", "latency_ms": 0.0, "meta": {"suite": args.suite, "split": args.split, "backend": args.server, "timestamp": datetime.datetime.utcnow().isoformat() + "Z"}}
                    elapsed = 0.0

                out_f.write(json.dumps(out_record, ensure_ascii=False) + "\n")
                out_f.flush()
                results.append(out_record)
                latencies.append(float(elapsed))

                print(f"[{len(results)}/{total}] id={out_record.get('id')} latency_ms={elapsed:.1f} pred={str(out_record.get('pred'))[:80]}")

    # Summary
    count = len(results)
    mean_latency = sum(latencies) / count if count else 0.0
    print(f"Completed {count} evaluations. Mean latency_ms={mean_latency:.1f}")


if __name__ == '__main__':
    main()
