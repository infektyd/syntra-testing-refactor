#!/usr/bin/env python3
"""Local payload smoke test for SYNTRA chat payload composition (no network).

Builds a fake manifest row and uses the same composition logic as Tools/run_manifest.py
to produce the outbound payload. Prints the JSON payload to STDOUT and performs
assertions on its structure.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def main() -> int:
    # Ensure we can import Tools.run_manifest (two levels up from this file's dir)
    here = Path(__file__).resolve()
    project_root = here.parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    # Import composition helper and constants
    from Tools.run_manifest import (  # type: ignore
        compose_syntra_payload,
        MODEL_SYNTRA_DEFAULT,
    )

    manifest = {
        "suite": "gsm8k",
        "item_id": "test001",
        "protocol": "gsm8k_short_ans_v1",
        "prompt": "2+2. Output only: Final Answer: 4",
    }

    # No env override: pass model=None-like by empty string
    payload = compose_syntra_payload(manifest["prompt"], model="")

    # Assertions
    assert payload["model"] == MODEL_SYNTRA_DEFAULT, "Default model mismatch"
    assert isinstance(payload["messages"], list) and len(payload["messages"]) == 1, "Expect exactly one message"
    assert payload["messages"][0]["role"] == "user", "Single message must be user"
    assert payload["messages"][0]["content"] == manifest["prompt"], "User content must equal manifest prompt"

    # Print JSON payload to STDOUT
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


