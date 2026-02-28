"""
Utility helpers for working with JSONL benchmark files.
"""

from __future__ import annotations

import json
from json import JSONDecodeError
from pathlib import Path
from typing import IO, Any, Dict, Iterator, Union

JsonlSource = Union[str, Path, IO[str]]


def iter_jsonl(source: JsonlSource) -> Iterator[Dict[str, Any]]:
    """
    Iterate over JSON Lines records while skipping blank lines and comments.

    A comment is any line whose first non-whitespace character is '#'.
    The iterator accepts either an open text file handle or a filesystem path.
    """
    if isinstance(source, (str, Path)):
        with Path(source).open("r", encoding="utf-8") as handle:
            yield from iter_jsonl(handle)
        return

    for raw_line in source:
        line = raw_line.strip()

        if not line:
            continue

        # Remove UTF-8 BOM while preserving rest of content
        if line.startswith("\ufeff"):
            line = line.lstrip("\ufeff")

        if not line or line.startswith("#"):
            continue

        # Allow trailing commas for friendliness with JSON arrays split into lines
        if line.endswith(","):
            line = line.rstrip(",")

        try:
            yield json.loads(line)
        except JSONDecodeError:
            continue
