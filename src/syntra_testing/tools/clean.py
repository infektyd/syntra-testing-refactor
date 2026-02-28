#!/usr/bin/env python3
"""
Clean runs artifacts and Python caches for a fresh start.

Usage:
    python3 -m Tools.clean [--runs-dir RUNS_DIR]

Removes the entire runs/ directory content and deletes all Python cache artifacts
(__pycache__ directories, .pyc files, .pytest_cache directories).
"""
import argparse
import os
import shutil
import glob
import sys

from Tools.common.logger import info, warn, error, debug, get_version

def clean_runs(runs_dir: str) -> None:
    if os.path.isdir(runs_dir):
        try:
            shutil.rmtree(runs_dir)
            info(f"Removed runs directory {runs_dir}")
        except Exception as e:
            error(f"Failed to remove runs directory {runs_dir}: {e}")
    else:
        info(f"No runs directory found at {runs_dir}")

def clean_caches() -> None:
    patterns = ['**/__pycache__', '**/.pytest_cache', '**/*.pyc']
    removed = 0
    for pattern in patterns:
        for path in glob.glob(pattern, recursive=True):
            try:
                if os.path.isdir(path):
                    shutil.rmtree(path)
                    info(f"Removed cache directory {path}")
                    removed += 1
                elif os.path.isfile(path):
                    os.remove(path)
                    info(f"Removed cache file {path}")
                    removed += 1
            except Exception as e:
                warn(f"Failed to remove {path}: {e}")
    if removed == 0:
        info("No Python cache artifacts found")
    else:
        info(f"Removed {removed} Python cache artifacts")

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Clean runs artifacts and Python caches for a fresh start"
    )
    parser.add_argument(
        '--runs-dir',
        default='runs',
        help='Path to runs directory (default: runs)'
    )
    parser.add_argument(
        '--version',
        action='version',
        version=get_version(),
        help='Show version and exit'
    )
    args = parser.parse_args()
    clean_runs(args.runs_dir)
    clean_caches()

if __name__ == "__main__":
    main()