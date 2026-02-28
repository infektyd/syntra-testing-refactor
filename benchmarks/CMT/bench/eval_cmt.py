"""CMT answer evaluation and grading.

Handles parsing model responses and comparing against gold answers.
Supports multiple answer formats:
- Multiple choice: $\boxed{a}$
- Multiple selection: $\boxed{a; b; d}$
- Numeric: $\boxed{2280}$ or $\boxed{16N_q^2}$
- Algebraic: $\boxed{O_n=E_n-E_{n-1}}$
- Coordinates/tuples: $\boxed{(2.09, 1.21); (0., 2.41)}$
- LaTeX expressions: $\boxed{U_1/2}$
"""

import re
import json
from typing import Dict, Any, Tuple, Optional
from decimal import Decimal, InvalidOperation


def extract_boxed_answer(text: str) -> str:
    """Extract answer from $\boxed{}$ LaTeX environment.

    Handles:
    - Standard: $\boxed{answer}$
    - Nested: $\\boxed{...}$ (escaped backslash)
    - Multiple lines: answer may span lines

    Args:
        text: Model response potentially containing $\boxed{}$

    Returns:
        Extracted answer without $\boxed{}$ wrapper, or empty string if not found
    """
    if not text:
        return ""

    # Try multiple patterns for robustness
    patterns = [
        r'\$\\?boxed\{([^}]*(?:\{[^}]*\}[^}]*)*)\}',  # Nested braces
        r'\\boxed\{([^}]*)\}',                          # Escaped backslash
        r'\boxed\{([^}]*)\}',                           # Plain boxed
    ]

    for pattern in patterns:
        matches = re.findall(pattern, text)
        if matches:
            return matches[0].strip()

    # Fallback: look for any boxed content
    if "boxed" in text.lower():
        # Extract everything between { and } after boxed
        boxed_match = re.search(r'boxed\s*\{([^}]+)\}', text, re.IGNORECASE)
        if boxed_match:
            return boxed_match.group(1).strip()

    return ""


def normalize_latex(text: str) -> str:
    """Normalize LaTeX expressions for comparison.

    Removes common formatting variations while preserving meaning:
    - Remove extra whitespace
    - Remove $ symbols
    - Normalize common LaTeX symbols
    """
    # Remove $ symbols
    text = text.replace("$", "").strip()

    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text)

    # Normalize common patterns
    # e.g., "N_q^2" -> "Nq2" for loose comparison
    # (keep as-is for now, exact match should work)

    return text


def normalize_numeric(text: str) -> Optional[float]:
    """Try to parse text as a number.

    Handles:
    - Integers: 2280
    - Decimals: 0.123
    - Scientific: 1.23e-5
    - Fractions: 1/2 (evaluates to 0.5)

    Args:
        text: Text potentially containing a number

    Returns:
        Parsed float, or None if not a valid number
    """
    text = text.strip()

    # Try direct float conversion
    try:
        return float(text)
    except ValueError:
        pass

    # Try removing common non-numeric characters
    cleaned = re.sub(r'[,\s]', '', text)
    try:
        return float(cleaned)
    except ValueError:
        pass

    # Try evaluating simple fractions
    if "/" in text:
        try:
            parts = text.split("/")
            if len(parts) == 2:
                return float(parts[0]) / float(parts[1])
        except (ValueError, ZeroDivisionError):
            pass

    return None


def parse_multiple_choice(answer: str) -> str:
    """Parse multiple choice answer.

    Extracts single letter A-Z (case-insensitive).
    Prioritizes letters that are standalone or after common separators.

    Args:
        answer: Potentially extracted answer

    Returns:
        Single uppercase letter (A-Z), or empty string if not found
    """
    # Look for standalone letters or letters in common formats
    # Priority: letter alone, letter after parenthesis/brackets, any letter
    patterns = [
        r'^\s*([a-zA-Z])\s*$',            # Just a letter
        r'[(\[]([a-zA-Z])[)\]]',          # Letter in parentheses or brackets
        r':\s*([a-zA-Z])',                # After colon
        r'\s([a-zA-Z])\)',                # Before closing paren
    ]

    for pattern in patterns:
        match = re.search(pattern, answer)
        if match:
            return match.group(1).upper()

    # Fallback: any letter
    match = re.search(r'[a-zA-Z]', answer)
    if match:
        return match.group(0).upper()

    return ""


def parse_multiple_selection(answer: str) -> set:
    """Parse multiple selection answer (semicolon-separated).

    Handles: a; b; d or a;b;d or a ; b ; d

    Args:
        answer: Potentially extracted answer

    Returns:
        Set of uppercase letters (A-Z)
    """
    # Split by semicolon and extract letters
    parts = answer.split(";")
    letters = set()

    for part in parts:
        # Find letter in part
        match = re.search(r'[a-zA-Z]', part.strip())
        if match:
            letters.add(match.group(0).upper())

    return letters


def grade_cmt_response(
    response: str,
    gold: str,
    item_type: Optional[str] = None
) -> Tuple[bool, Dict[str, Any]]:
    """Grade a CMT response against gold answer.

    Automatically detects answer format and applies appropriate grading logic.

    Args:
        response: Model response (may contain $\boxed{}$)
        gold: Gold answer (in $\boxed{}$ format)
        item_type: CMT problem type (HF, ED, etc.) for metadata

    Returns:
        Tuple of (is_correct, details dict) where details includes:
        - parsed_answer: Extracted answer from response
        - gold_answer: Extracted answer from gold
        - answer_format: Detected format (mc, ms, numeric, algebraic, etc.)
        - is_correct: Boolean result
    """
    # Extract answers
    parsed_response = extract_boxed_answer(response)
    parsed_gold = extract_boxed_answer(gold)

    if not parsed_response:
        parsed_response = response  # Fallback to raw response

    if not parsed_gold:
        parsed_gold = gold  # Fallback to raw gold

    details = {
        "parsed_answer": parsed_response,
        "gold_answer": parsed_gold,
        "answer_format": "unknown",
        "is_correct": False,
    }

    # Detect answer format and grade
    is_correct = False

    # Check if multiple selection (contains semicolon)
    if ";" in parsed_gold:
        details["answer_format"] = "multiple_selection"
        parsed_response_set = parse_multiple_selection(parsed_response)
        parsed_gold_set = parse_multiple_selection(parsed_gold)
        is_correct = parsed_response_set == parsed_gold_set

    # Check if multiple choice (single letter)
    elif re.match(r'^[a-zA-Z]$', parsed_gold.strip()):
        details["answer_format"] = "multiple_choice"
        parsed_response_mc = parse_multiple_choice(parsed_response)
        parsed_gold_mc = parse_multiple_choice(parsed_gold)
        is_correct = parsed_response_mc == parsed_gold_mc

    # Try numeric comparison
    else:
        response_num = normalize_numeric(parsed_response)
        gold_num = normalize_numeric(parsed_gold)

        if response_num is not None and gold_num is not None:
            details["answer_format"] = "numeric"
            # Check with relative tolerance
            if gold_num != 0:
                relative_error = abs((response_num - gold_num) / gold_num)
                is_correct = relative_error < 1e-6
            else:
                # For zero, use absolute tolerance
                is_correct = abs(response_num - gold_num) < 1e-9

        else:
            # Symbolic/algebraic comparison
            details["answer_format"] = "algebraic"

            # Normalize whitespace and symbols
            response_norm = normalize_latex(parsed_response)
            gold_norm = normalize_latex(parsed_gold)

            # Try exact match after normalization
            if response_norm == gold_norm:
                is_correct = True

            # Try removing all spaces for comparison (allows "U_1 / 2" == "U_1/2")
            if not is_correct:
                response_no_space = response_norm.replace(" ", "")
                gold_no_space = gold_norm.replace(" ", "")
                if response_no_space == gold_no_space:
                    is_correct = True

    details["is_correct"] = is_correct
    return is_correct, details


def grade_cmt_batch(
    responses: list,
    golds: list,
    item_types: Optional[list] = None
) -> Dict[str, Any]:
    """Grade multiple CMT responses.

    Args:
        responses: List of model responses
        golds: List of gold answers
        item_types: Optional list of problem types

    Returns:
        Dictionary with overall statistics and per-item results
    """
    if len(responses) != len(golds):
        raise ValueError("Response and gold lists must have same length")

    if item_types is None:
        item_types = [None] * len(responses)

    results = []
    correct_count = 0

    for i, (response, gold, item_type) in enumerate(zip(responses, golds, item_types)):
        is_correct, details = grade_cmt_response(response, gold, item_type)
        details["index"] = i
        results.append(details)

        if is_correct:
            correct_count += 1

    return {
        "total": len(responses),
        "correct": correct_count,
        "accuracy": correct_count / len(responses) if responses else 0.0,
        "results": results,
    }


__all__ = [
    "grade_cmt_response",
    "grade_cmt_batch",
    "extract_boxed_answer",
    "normalize_latex",
    "normalize_numeric",
    "parse_multiple_choice",
    "parse_multiple_selection",
]
