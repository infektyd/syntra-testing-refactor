#!/usr/bin/env python3
"""Minimal OpenRouter baseline client."""

from __future__ import annotations

import json
import os
import sys
import time
import warnings
from typing import Any, Dict, Optional, Tuple

# Suppress urllib3 OpenSSL warning
warnings.filterwarnings("ignore", message="urllib3 v2 only supports OpenSSL 1.1.1+", category=UserWarning)

API_URL = "https://openrouter.ai/api/v1/chat/completions"
MAX_ATTEMPTS = 3
BACKOFF_SECONDS = 1.0
TIMEOUT_SECONDS = 360

try:
    import requests  # type: ignore

    _HAS_REQUESTS = True
except ImportError:  # pragma: no cover - fallback path
    requests = None
    _HAS_REQUESTS = False

if not _HAS_REQUESTS:
    from urllib.error import HTTPError, URLError  # pragma: no cover - fallback path
    from urllib.request import Request, urlopen  # pragma: no cover - fallback path


class RetryableError(RuntimeError):
    """Marker exception for retryable HTTP failures."""


def _post_with_requests(headers: Dict[str, str], payload: Dict[str, Any]) -> Tuple[int, str]:
    """Send POST using requests, returning (status_code, text)."""
    assert requests is not None  # For type checkers
    try:
        response = requests.post(API_URL, headers=headers, json=payload, timeout=TIMEOUT_SECONDS)
    except requests.exceptions.RequestException as exc:  # type: ignore[attr-defined]
        raise RetryableError(f"Network error contacting OpenRouter: {exc}") from exc
    return response.status_code, response.text


def _post_with_urllib(headers: Dict[str, str], payload: Dict[str, Any]) -> Tuple[int, str]:  # pragma: no cover - fallback path
    """Send POST using urllib, returning (status_code, text)."""
    data = json.dumps(payload).encode("utf-8")
    request = Request(API_URL, data=data, headers=headers, method="POST")
    try:
        with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            status = getattr(response, "status", response.getcode())
            text = response.read().decode("utf-8")
            return status, text
    except HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", errors="replace")
    except URLError as exc:
        raise RetryableError(f"Network error contacting OpenRouter: {exc}") from exc


def _http_post(headers: Dict[str, str], payload: Dict[str, Any]) -> Tuple[int, str]:
    """Dispatch POST via requests or urllib."""
    if _HAS_REQUESTS:
        return _post_with_requests(headers, payload)
    return _post_with_urllib(headers, payload)


def complete_openrouter(prompt: str, model: str) -> Dict[str, Optional[Any]]:
    """Send a prompt to OpenRouter and return completion metadata."""
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY is not set.")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/syntraTesting",
        "X-Title": "syntraTesting",
    }

    payload: Dict[str, Any] = {
        "model": model,
        "temperature": 0,
        "messages": [{"role": "user", "content": prompt}],
    }

    attempt = 0
    backoff = BACKOFF_SECONDS
    last_error: Optional[Exception] = None
    while attempt < MAX_ATTEMPTS:
        attempt += 1
        try:
            status_code, body_text = _http_post(headers, payload)
            if status_code in (429,) or status_code >= 500:
                raise RetryableError(f"OpenRouter returned status {status_code}: {body_text[:200]}")
            if status_code >= 400:
                raise RuntimeError(f"OpenRouter returned status {status_code}: {body_text[:200]}")
            return _parse_response(body_text)
        except RetryableError as exc:
            last_error = exc
            if attempt >= MAX_ATTEMPTS:
                raise exc
            time.sleep(backoff)
            backoff *= 2

    if last_error is not None:
        raise last_error
    raise RuntimeError("Failed to obtain completion from OpenRouter after retries.")


def _parse_response(body_text: str) -> Dict[str, Optional[Any]]:
    """Parse OpenRouter response JSON."""
    try:
        payload = json.loads(body_text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Failed to parse OpenRouter response: {exc}") from exc

    try:
        choices = payload["choices"]
        first_choice = choices[0]
        message = first_choice["message"]
        text = message["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError("OpenRouter response missing completion content.") from exc

    usage = payload.get("usage") or {}
    tokens_in = usage.get("prompt_tokens")
    tokens_out = usage.get("completion_tokens")

    return {
        "text": text,
        "tokens_in": int(tokens_in) if isinstance(tokens_in, int) else None,
        "tokens_out": int(tokens_out) if isinstance(tokens_out, int) else None,
    }


def main() -> int:
    """Read prompt from stdin and print baseline completion."""
    prompt = sys.stdin.read()
    if not prompt:
        print("ERROR: No prompt provided on STDIN.", file=sys.stderr)
        return 1

    model = os.environ.get("BASELINE_MODEL")
    if not model:
        print("ERROR: BASELINE_MODEL is not set.", file=sys.stderr)
        return 1

    try:
        result = complete_openrouter(prompt, model)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    text = result.get("text") or ""
    sys.stdout.write(text)
    if not text.endswith("\n"):
        sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
