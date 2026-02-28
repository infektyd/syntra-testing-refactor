#!/usr/bin/env python3
"""
Global logging utility for SYNTRA CMT tools.

Purpose: Provide consistent logging across scripts with prefixed output ([INFO], [WARN], [ERR], [DBG]).

Inputs: Log level and message string.

Outputs: Prints to stderr/stdout with timestamps and prefixes.

Example:
    from logger import info, warn, error, debug
    info("Processing started")
    warn("Potential issue detected")
"""
import sys
from datetime import datetime
from pathlib import Path

def _log(level: str, message: str) -> None:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [{level}] {message}", file=sys.stderr)

def info(message: str) -> None:
    _log("INFO", message)

def warn(message: str) -> None:
    _log("WARN", message)

def error(message: str) -> None:
    _log("ERR", message)

def debug(message: str) -> None:
    _log("DBG", message)


def get_version() -> str:
    """Read version from VERSION file in parent dir."""
    version_path = Path(__file__).resolve().parent.parent / "VERSION"
    try:
        return version_path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return "unknown"
