#!/usr/bin/env python3
"""
Utilities for robust CMT grading: extraction, normalization, comparison, and sanity checks.
"""
from __future__ import annotations

import re
from typing import Union


def extract_last_boxed(text: str) -> str | None:
    """Extracts the content of the last `\\boxed{...}` block in a string.

    This function ignores any earlier `\\boxed{...}` blocks and handles nested
    braces within the target block.

    Args:
        text: The input string to search.

    Returns:
        The content of the last `\\boxed{...}` block, or None if not found.
    """
    if not isinstance(text, str):
        return None
    # Find the last occurrence of \boxed{ and parse for balanced braces
    last_start = None
    idx = 0
    while True:
        idx = text.find(r'\boxed{', idx)
        if idx == -1:
            break
        last_start = idx
        idx += len(r'\boxed{')
    if last_start is None:
        return None
    # Now, parse from last_start + len('\boxed{') for balanced braces
    start = last_start + len(r'\boxed{')
    brace_count = 1
    i = start
    n = len(text)
    while i < n:
        if text[i] == '{':
            brace_count += 1
        elif text[i] == '}':
            brace_count -= 1
            if brace_count == 0:
                # Extract content between start and i
                return text[start:i]
        i += 1
    # If we get here, braces were not balanced
    return None


def strip_math_wrappers(s: str) -> str:
    """Strips outer math wrappers from a string.

    This function removes common LaTeX math delimiters like `$`, `\\(`, `\\)`,
    `\\[`, `\\]`, `\\boxed{...}`, and text commands like `\\text{...}`.

    Args:
        s: The input string.

    Returns:
        The string with math wrappers removed.
    """
    if not isinstance(s, str):
        return ""
    s = s.strip()
    # Remove \boxed{} and other wrappers, but preserve inner content
    # First, handle \boxed{...} by extracting content
    s = re.sub(r'\\boxed{(.*?)}', r'\1', s)
    # Remove math delimiters that do not use braces
    s = re.sub(r'\$\$|\$|\\\[|\\\]|\\\(|\\\)', '', s)
    # Remove LaTeX text commands but keep their content
    s = re.sub(r'\\text\{(.*?)\}|\\mathrm\{(.*?)\}|\\operatorname\{(.*?)\}', r'\1\2\3', s)
    s = re.sub(r'\s+', ' ', s)  # Collapse whitespace
    return s.strip()


def looks_multichoice(s: str) -> bool:
    """Checks if a string appears to be a multiple-choice answer.

    This heuristic looks for semicolon-separated tokens consisting only of
    single letters from 'a' to 'j' (case-insensitive).

    Args:
        s: The input string.

    Returns:
        True if the string looks like a multiple-choice answer, False otherwise.
    """
    if not isinstance(s, str):
        return False
    s = s.lower().strip()
    if not s:
        return False
    parts = [p.strip() for p in s.split(';') if p.strip()]
    return all(re.match(r'^[a-j]$', p) for p in parts) and parts


def normalize_multichoice(s: str) -> str:
    """Normalizes a multiple-choice answer string.

    The normalization process includes lowercasing, splitting by semicolon,
    removing duplicates, sorting alphabetically, and rejoining with semicolons.

    Args:
        s: The multiple-choice answer string.

    Returns:
        The normalized string.
    """
    if not isinstance(s, str) or not looks_multichoice(s):
        return s
    s = s.lower()
    parts = [p.strip() for p in s.split(';') if p.strip()]
    sorted_parts = sorted(set(parts))
    return ';'.join(sorted_parts)


def parse_numeric_list(s: str) -> list[float] | list[tuple[float, ...]] | None:
    """Parses a string into a list of numbers or tuples of numbers.

    The string can be in the format 'x; y; z' or '(x,y); (a,b)'.

    Args:
        s: The input string.

    Returns:
        A list of floats, a list of tuples of floats, or None if parsing fails.
    """
    if not isinstance(s, str):
        return None
    s = s.strip()
    if not s:
        return None
    parts = [p.strip() for p in s.split(';') if p.strip()]
    if not parts:
        return None
    floats = []
    tuples = []
    for p in parts:
        nums = []
        if '(' in p and ')' in p:
            inside = re.sub(r'[()]', '', p).strip()
            num_strs = [ns.strip() for ns in inside.split(',') if ns.strip()]
            for ns in num_strs:
                try:
                    nums.append(float(ns))
                except ValueError:
                    return None
            if nums:
                tuples.append(tuple(nums))
        else:
            try:
                nums = [float(p)]
            except ValueError:
                return None
            floats.extend(nums)
    if tuples and floats:
        # Mixed, not supported
        return None
    if tuples:
        return tuples
    if floats:
        return floats
    return None


def numeric_equal(a: Union[float, int, list[float], list[tuple[float, ...]]],
                   b: Union[float, int, list[float], list[tuple[float, ...]]],
                   tol: float) -> bool:
    """Compares two numeric values or lists/tuples of values for equality within a tolerance.

    Args:
        a: The first numeric value or list/tuple.
        b: The second numeric value or list/tuple.
        tol: The absolute tolerance for the comparison.

    Returns:
        True if the values are equal within the tolerance, False otherwise.
    """
    if type(a) != type(b):
        return False
    if isinstance(a, (list, tuple)):
        if len(a) != len(b):
            return False
        return all(numeric_equal(x, y, tol) for x, y in zip(a, b))
    if isinstance(a, (float, int)) and isinstance(b, (float, int)):
        return abs(float(a) - float(b)) <= tol
    return False


def allowed_choice_set_from_prompt(prompt: str) -> set[str] | None:
    """Extracts the set of allowed multiple-choice answers from a prompt.

    This function looks for patterns like '(a)', 'a)', 'a.', '[a]', '{a}',
    or '$a;b;c;d$'.

    Args:
        prompt: The prompt text.

    Returns:
        A set of allowed choices, or None if no choices are found.
    """
    if not isinstance(prompt, str):
        return None

    explicit_pattern = re.compile(
        r"""
        (?:[\(\[\{]\s*([A-Za-z])\s*[\)\]\}])            # (a) [a] {a}
        |
        (?:^|[\s:])([A-Za-z])\s*(?:\)|\.)(?=[\s,;:]|$)  # a) a. with trailing space/punctuation/end
        """,
        re.VERBOSE,
    )
    matches = explicit_pattern.findall(prompt)
    letters = {(m[0] or m[1]).lower() for m in matches if (m[0] or m[1])}
    if letters:
        return letters

    # Fallback: look for semicolon-separated letters like $a;b;c;d$
    fallback_matches = re.findall(r'\b([a-jA-J])\b', prompt)
    fallback_letters = {m.lower() for m in fallback_matches}
    return fallback_letters or None


LATEX_SPACE_CMDS = re.compile(r'\\(?:,|;|:|!|\s)')


def canon_symbol(s: str) -> str:
    """Canonicalizes a symbolic answer string.

    This function strips math wrappers, whitespace, LaTeX spacing commands,
    and leading variable assignments (e.g., 'alpha=...').

    Args:
        s: The symbolic answer string.

    Returns:
        The canonicalized string.
    """
    if not isinstance(s, str):
        return ""
    stripped = strip_math_wrappers(s)
    stripped = LATEX_SPACE_CMDS.sub("", stripped)
    stripped = re.sub(r'\\left|\\right', '', stripped)
    stripped = re.sub(r'\s+', '', stripped)
    stripped = re.sub(r'^[A-Za-z\\]+=', '', stripped)
    return stripped.lower()


def gold_valid_against_allowed(gold: str, allowed: set[str]) -> bool:
    """Checks if a gold multiple-choice answer is valid against a set of allowed choices.

    This function only validates multiple-choice answers; it returns True for
    numeric, symbolic, or text answers.

    Args:
        gold: The gold answer string.
        allowed: A set of allowed choices.

    Returns:
        True if the gold answer is valid, False otherwise.
    """
    if not allowed or not isinstance(gold, str):
        return True
    if looks_multichoice(gold):
        tokens = [t.strip().lower() for t in gold.split(';') if t.strip()]
        return set(tokens).issubset({c.lower() for c in allowed})
    return True
