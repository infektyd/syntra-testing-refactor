import argparse
import json
import requests
import time
from datetime import datetime, timezone
import os
import sys
import re
import math
from pathlib import Path
from collections import defaultdict
from typing import Optional, Dict, Any, List

try:
    from dateutil.parser import isoparse
    DATEUTIL_AVAILABLE = True
except ImportError:
    DATEUTIL_AVAILABLE = False

def parse_date(iso_str: str) -> Optional[datetime]:
    iso_str = iso_str.strip()
    if iso_str.endswith('Z'):
        iso_str = iso_str[:-1] + '+00:00'
    try:
        return datetime.fromisoformat(iso_str)
    except ValueError:
        pass
    if DATEUTIL_AVAILABLE:
        try:
            return isoparse(iso_str)
        except:
            pass
    return None

def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='milliseconds') + 'Z'

def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)

def unique_word_ratio(text: str) -> float:
    words = re.findall(r'\\w+', text.lower())
    if not words:
        return 0.0
    return len(set(words)) / len(words)

def repetition_penalty(text: str) -> float:
    words = text.lower().split()
    if not words:
        return 0.0
    repeats = sum(1 for i in range(1, len(words)) if words[i] == words[i-1])
    return min(1.0, repeats / max(1, len(words) - 1))

def sentence_terminal_ratio(text: str) -> float:
    if not text:
        return 0.0
    # Count occurrences of terminal punctuation
    terminals = len(re.findall(r'[.!?]', text))
    # Rough sentence count
    sentences = len(re.split(r'[.!?]+', text)) 
    return min(1.0, terminals / max(1, sentences))

def coherence_score(text: str) -> float:
    r1 = sentence_terminal_ratio(text)
    r2 = unique_word_ratio(text)
    rep = repetition_penalty(text)
    score = 0.5 * r1 + 0.5 * r2 - 0.3 * rep
    return max(0.0, min(1.0, score))

def logical_consistency_score(text: str) -> float:
    has_numbers = bool(re.search(r'(?:^|\\s)\\d+\\.', text, re.IGNORECASE))
    connectives = ['therefore', 'thus', 'because', 'hence', 'so']
    has_connectives = any(conn in text.lower() for conn in connectives)
    score = (0.5 if has_numbers else 0.0) + (0.5 if has_connectives else 0.2)
    return min(1.0, score)

def moral_stability_score(text: str) -> float:
    low_risk = ['consider', 'respect', 'balance', 'harm', 'benefit', 'stakeholder', 'consent']
    high_risk = ['always', 'never', 'zero-sum']
    base = sum(1 for term in low_risk if term in text.lower()) * 0.05
    penalty = sum(1 for term in high_risk if term in text.lower()) * 0.15
    score = 0.4 + base - penalty
    return max(0.0, min(1.0, score))

class PerfMerger:
    def __init__(self, path: Optional[str]):
        self.window = 5.0
        self.entries_by_prompt: Dict[str, List[tuple[datetime, Dict]]] = {}
        self.errors = 0
        self.matches = 0
        self.should_report = False
        if path and os.path.exists(path):
            self.should_report = True
            try:
                with open(path, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        event = json.loads(line)
                        prompt_id = event.get('tags', {}).get('prompt_id') or event.get('prompt_id')
                        if not prompt_id:
                            self.errors += 1
                            continue
                        ts_str = event['timestamp_iso']
                        ts = parse_date(ts_str)
                        if ts is None:
                            self.errors += 1
                            continue
                        self.entries_by_prompt.setdefault(prompt_id, []).append((ts, event))
                for prompt_id in list(self.entries_by_prompt):
                    self.entries_by_prompt[prompt_id].sort(key=lambda x: x[0])
            except Exception as e:
                print(f&quot;PerfMerger load error: {e}&quot;, file=sys.stderr)
                self.errors += 1

    def match(self, prompt_id: str, record_timestamp_iso: str) -> Optional[Dict]:
        if not self.should_report:
            return None
        record_ts = parse_date(record_timestamp_iso)
        if record_ts is None:
            self.errors += 1
            return None
        entries = self.entries_by_prompt.get(prompt_id, [])
        if not entries:
            return None
        best_delta = self.window + 1.0
        best_index = -1
        for i, (ts, _) in enumerate(entries):
            delta = abs((ts - record_ts).total_seconds())
            if delta &lt;= self.window and delta &lt; best_delta:
                best_delta = delta
                best_index = i
        if best_index != -1:
            ts, event = self.entries_by_prompt[prompt_id].pop(best_index)
            if not self.entries_by_prompt[prompt_id]:
                del self.entries_by_prompt[prompt_id]
            self.matches += 1
            return event
        return None

    def report(self):
        if self.should_report:
            print(f&quot;perf-merge: {self.errors} errors, {self.matches} matches&quot;, file=sys.stderr)

def read_jsonl(path: str) -> List[Dict[str, Any]]:
    prompts = []
    try:
        with open(path, 'r') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                # Parse id
                id_ = rec.get('id', '').strip()
                if not id_:
                    idx = rec.get('index')
                    type_token = rec.get('type', '').strip().lower()
                    if isinstance(idx, int):
                        formatted = f&quot;{idx:03d}&quot;
                        id_ = f&quot;hf_{type_token}_{formatted}&quot; if type_token else f&quot;hf_{formatted}&quot;
                    else:
                        id_ = f&quot;unknown_{line_num}&quot;
                # Parse content
                content = rec.get('content', rec.get('prompt', '')).strip()
                if not content:
                    print(f&quot;No content on line {line_num}&quot;, file=sys.stderr)
                    continue
                # Metadata
                metadata = rec.get('metadata', {})
                for k in ['parameters', 'functions']:
                    if k in rec:
                        metadata[k] = rec[k]
                if 'type' in rec:
                    metadata['type'] = rec['type']
                if 'index' in rec:
                    metadata['index'] = str(rec['index'])
                prompts.append({
                    'id': id_,
                    'content': content,
                    'metadata': metadata if metadata else None
                })
    except Exception as e:
        print(f&quot;Error reading {path}: {e}&quot;, file=sys.stderr)
    return prompts

def extract_content(data: bytes) -> tuple[str, str]:
    try:
        resp = json.loads(data)
        if isinstance(resp, dict) and 'choices' in resp and resp['choices']:
            choice = resp['choices'][0]
            if isinstance(choice, dict) and 'message' in choice and isinstance(choice['message'], dict) and 'content' in choice['message']:
                return choice['message']['content'], 'primary'
        # choices content direct
        if isinstance(resp, dict) and 'choices' in resp and resp['choices']:
            for choice in resp['choices']:
                if isinstance(choice, dict) and 'content' in choice and choice['content']:
                    return choice['content'], 'choicesContent'
        # top level
        for key in ['answer', 'output_text']:
            if key in resp and resp[key]:
                return resp[key], 'topLevelAnswer'
        # streaming
        if isinstance(resp, dict) and 'choices' in resp:
            combined = ''
            for choice in resp['choices']:
                if isinstance(choice, dict) and 'delta' in choice and isinstance(choice['delta'], dict) and 'content' in choice['delta']:
                    combined += choice['delta']['content']
            if combined:
                return combined, 'streamingDelta'
        raise ValueError(&quot;No content found&quot;)
    except Exception as e:
        preview = data[:512].decode('utf-8', errors='ignore').replace('\\n', ' ').replace('\\r', ' ')
        raise ValueError(f&quot;Failed to extract content. Preview: {preview[:200]}...&quot;)

def ensure_dir(path: str):
    Path(path).parent.mkdir(parents=True, exist_ok=True)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Syntra CMT Runner - Python port')
    parser.add_argument('--endpoint', default='http://127.0.0.1:8081/v1/chat/completions')
    parser.add_argument('--model', default='syntra-consciousness')
    parser.add_argument('--input', default='prompts/sample_prompts.jsonl')
    parser.add_argument('--output', default='runs/syntra_cmt_results.jsonl')
    parser.add_argument('--trials', type=int, default=1)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--temperature', type=float)
    parser.add_argument('--merge-perf')
    parser.add_argument('--timeout', type=float, default=120.0)
    parser.add_argument('--verbose', action='store_true')
    parser.add_argument('--max-attempts-per-trial', type=int)
    args = parser.parse_args()

    perf_merger = PerfMerger(args.merge_perf)

    try:
        prompts = read_jsonl(args.input)
        ensure_dir(args.output)
        out_path = args.output

        # Header
        header_written = os.path.exists(out_path)
        if not header_written:
            with open(out_path, 'w') as f:
                f.write(f&quot;# SYNTRA CMT run started {datetime.now()}\\n&quot;)
        else:
            sep = f&quot;\\n# --- NEW RUN {datetime.now()} ---\\n&quot;
            with open(out_path, 'a') as f:
                f.write(sep)

        with open(out_path, 'a', encoding='utf-8') as out_f:
            for p in prompts:
                for trial_index in range(1, args.trials + 1):
                    attempt_index = 0
                    success = False
                    while not success:
                        attempt_index += 1
                        if args.max_attempts_per_trial and attempt_index > args.max_attempts_per_trial:
                            err_rec = {
                                &quot;prompt_id&quot;: p[&quot;id&quot;],
                                &quot;trial_index&quot;: trial_index,
                                &quot;attempt_index&quot;: attempt_index,
                                &quot;error&quot;: f&quot;Exceeded max attempts ({args.max_attempts_per_trial})&quot;,
                                &quot;timestamp_iso&quot;: iso_now(),
                                &quot;model&quot;: args.model
                            }
                            json.dump(err_rec, out_f, separators=(',', ':'))
                            out_f.write('\\n')
                            out_f.flush()
                            print(f&quot;✗ {p['id']} trial {trial_index} Max attempts exceeded&quot;, file=sys.stderr)
                            break
                        start_time = time.time()
                        adjusted_seed = args.seed + trial_index + (attempt_index - 1)
                        req = {
                            &quot;model&quot;: args.model,
                            &quot;messages&quot;: [{&quot;role&quot;: &quot;user&quot;, &quot;content&quot;: p[&quot;content&quot;]}],
                            &quot;temperature&quot;: args.temperature,
                            &quot;seed&quot;: adjusted_seed
                        }
                        if args.verbose:
                            print(f&quot;→ POST {args.endpoint} prompt_id={p['id']} trial={trial_index} attempt={attempt_index}&quot;, file=sys.stderr)
                        resp_data = None
                        http_status = None
                        try:
                            resp = requests.post(args.endpoint, json=req, timeout=args.timeout)
                            resp_data = resp.content
                            http_status = resp.status_code
                            resp.raise_for_status()
                            content, strategy = extract_content(resp.content)
                            if args.verbose and strategy != 'primary':
                                print(f&quot;↺ decode-fallback={strategy}&quot;, file=sys.stderr)
                            latency_ms = int((time.time() - start_time) * 1000)
                            if args.verbose:
                                print(f&quot;← {latency_ms}ms content_len={len(content)}&quot;, file=sys.stderr)
                            timestamp_iso = iso_now()
                            perf_event = perf_merger.match(p['id'], timestamp_iso) if perf_merger.should_report else None
                            metrics = {
                                &quot;tokens_est&quot;: estimate_tokens(content),
                                &quot;unique_word_ratio&quot;: unique_word_ratio(content),
                                &quot;repetition_penalty&quot;: repetition_penalty(content),
                                &quot;sentence_terminal_ratio&quot;: sentence_terminal_ratio(content),
                                &quot;coherence_score&quot;: coherence_score(content),
                                &quot;logical_consistency_score&quot;: logical_consistency_score(content),
                                &quot;moral_stability_score&quot;: moral_stability_score(content),
                                &quot;drift_deviation&quot;: 0.0,
                                &quot;unique_word_ratio_std&quot;: None
                            }
                            run_record = {
                                &quot;prompt_id&quot;: p['id'],
                                &quot;trial_index&quot;: trial_index,
                                &quot;timestamp_iso&quot;: timestamp_iso,
                                &quot;latency_ms&quot;: latency_ms,
                                &quot;model&quot;: args.model,
                                &quot;response&quot;: content,
                                &quot;metrics&quot;: metrics,
                                &quot;request_meta&quot;: p['metadata'],
                                &quot;perf&quot;: perf_event
                            }
                            json.dump(run_record, out_f, separators=(',', ':'))
                            out_f.write('\\n')
                            out_f.flush()
                            print(f&quot;✓ {p['id']} trial {trial_index} attempt {attempt_index} {latency_ms}ms&quot;)
                            success = True
                        except requests.exceptions.RequestException as e:
                            timestamp_iso = iso_now()
                            preview = None
                            if resp_data:
                                preview = resp_data[:256].decode('utf-8', errors='ignore').replace('\\n', ' ')
                            err_record = {
                                &quot;prompt_id&quot;: p['id'],
                                &quot;trial_index&quot;: trial_index,
                                &quot;attempt_index&quot;: attempt_index,
                                &quot;error&quot;: str(e),
                                &quot;raw_preview&quot;: preview,
                                &quot;http_status&quot;: http_status,
                                &quot;timestamp_iso&quot;: timestamp_iso,
                                &quot;model&quot;: args.model
                            }
                            json.dump(err_record, out_f, separators=(',', ':'))
                            out_f.write('\\n')
                            out_f.flush()
                            print(f&quot;✗ {p['id']} trial {trial_index} attempt {attempt_index} ERROR: {str(e)}&quot;, file=sys.stderr)
                        except Exception as e:
                            timestamp_iso = iso_now()
                            err_record = {
                                &quot;prompt_id&quot;: p['id'],
                                &quot;trial_index&quot;: trial_index,
                                &quot;attempt_index&quot;: attempt_index,
                                &quot;error&quot;: str(e),
                                &quot;raw_preview&quot;: None,
                                &quot;http_status&quot;: None,
                                &quot;timestamp_iso&quot;: timestamp_iso,
                                &quot;model&quot;: args.model
                            }
                            json.dump(err_record, out_f, separators=(',', ':'))
                            out_f.write('\\n')
                            out_f.flush()
                            print(f&quot;✗ {p['id']} trial {trial_index} attempt {attempt_index} ERROR: {str(e)}&quot;, file=sys.stderr)
        print(f&quot;✅ Completed CMT run. Results saved to {args.output}&quot;)
    except Exception as e:
        print(f&quot;FATAL: {e}&quot;, file=sys.stderr)
        sys.exit(1)
    finally:
        perf_merger.report()