#!/usr/bin/env python3
"""
Unit tests for grader_utils.
Run with: python -m unittest test_grader_utils.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import unittest
from grader_utils import (
    extract_last_boxed, strip_math_wrappers, looks_multichoice, normalize_multichoice,
    parse_numeric_list, numeric_equal, allowed_choice_set_from_prompt, gold_valid_against_allowed
)


class TestGraderUtils(unittest.TestCase):

    def test_extract_last_boxed(self):
        self.assertEqual(extract_last_boxed("\\boxed{a}"), "a")
        self.assertEqual(extract_last_boxed("first \\boxed{old} more \\boxed{new}"), "new")
        self.assertIsNone(extract_last_boxed("no box"))
        self.assertEqual(extract_last_boxed("\\boxed{\\frac12} text"), "\\frac12")
        self.assertEqual(extract_last_boxed("\\boxed{c} \\boxed{d}"), "d")

    def test_extract_nested_boxed(self):
        boxed = r"noise \boxed{(\alpha,\{\beta\})}"
        self.assertEqual(extract_last_boxed(boxed), r"(\alpha,\{\beta\})")

    def test_strip_math_wrappers(self):
        self.assertEqual(strip_math_wrappers("\\text{frac 1}"), "frac 1")
        self.assertEqual(strip_math_wrappers("$expr$"), "expr")
        self.assertEqual(strip_math_wrappers("normal text"), "normal text")
        self.assertEqual(strip_math_wrappers("  spaced  "), "spaced")
        self.assertEqual(strip_math_wrappers("\\sqrt{x^{2}}"), "\\sqrt{x^{2}}")

    def test_looks_multichoice(self):
        self.assertTrue(looks_multichoice("a"))
        self.assertTrue(looks_multichoice("a;b;c"))
        self.assertTrue(looks_multichoice("b; A; c"))
        self.assertFalse(looks_multichoice("abc"))
        self.assertFalse(looks_multichoice("x;y"))
        self.assertFalse(looks_multichoice("1;2"))

    def test_normalize_multichoice(self):
        self.assertEqual(normalize_multichoice("c; A; b"), "a;b;c")
        self.assertEqual(normalize_multichoice("b;a;b"), "a;b")
        self.assertEqual(normalize_multichoice("a;b;c;d;e"), "a;b;c;d;e")
        self.assertEqual(normalize_multichoice("x;y"), "x;y")  # No change since doesn't look multichoice

    def test_mc_normalization(self):
        self.assertEqual(normalize_multichoice("c;A;b"), "a;b;c")

    def test_parse_numeric_list(self):
        self.assertEqual(parse_numeric_list("1.23"), [1.23])
        self.assertEqual(parse_numeric_list("1;2;3"), [1, 2, 3])
        self.assertEqual(parse_numeric_list("(1.2,3.4); (5,6)"), [(1.2, 3.4), (5, 6)])
        self.assertIsNone(parse_numeric_list("abc"))
        self.assertIsNone(parse_numeric_list("(1;2)"))  # Mixed not supported

    def test_numeric_equal(self):
        self.assertTrue(numeric_equal([1.0, 2.0], [1.0, 2.0], 0.1))
        self.assertTrue(numeric_equal([(1.0, 2.0)], [(1.0, 2.0)], 0.01))
        self.assertFalse(numeric_equal([1.0], [1.1], 0.05))
        self.assertTrue(numeric_equal([1.0], [1.01], 0.02))

    def test_allowed_choice_set_from_prompt(self):
        prompt = "Choose (a) opt1 (b) opt2 (c) opt3"
        self.assertEqual(allowed_choice_set_from_prompt(prompt), {'a', 'b', 'c'})
        self.assertIsNone(allowed_choice_set_from_prompt("no choices"))

    def test_allowed_choice_set_from_prompt_variants(self):
        p = "Choose one: (A) option; (b) option; c) option; d. option; [e]"
        got = allowed_choice_set_from_prompt(p)
        self.assertEqual(got, {"a","b","c","d","e"})

    def test_allowed_choice_set_from_parameters_format(self):
        # Test fallback for parameters like "$a;b;c;d$"
        params = "$a;b;c;d$"
        got = allowed_choice_set_from_prompt(params)
        self.assertEqual(got, {"a","b","c","d"})

    def test_gold_valid_against_allowed(self):
        # Only validates multi-choice, returns True for non-multi-choice
        self.assertTrue(gold_valid_against_allowed("", None))  # No allowed, True
        # Multi-choice validation still works
        self.assertTrue(gold_valid_against_allowed("a;b;c", {'a', 'b', 'c', 'd'}))
        self.assertFalse(gold_valid_against_allowed("a;b;e", {'a', 'b', 'c'}))

    def test_gold_valid_multi_choice_ok(self):
        allowed = {"a","b","c","d"}
        assert gold_valid_against_allowed("a;c", allowed) is True

    def test_gold_valid_multi_choice_out_of_range(self):
        allowed = {"a","b","c","d"}
        assert gold_valid_against_allowed("e", allowed) is False

    def test_gold_valid_numeric_skips_allowlist(self):
        allowed = {"a","b","c","d"}
        assert gold_valid_against_allowed(r"\frac{1}{2}", allowed) is True
        assert gold_valid_against_allowed("0.50", allowed) is True
        assert gold_valid_against_allowed("(1.0, 2.0); (3.0, 4.0)", allowed) is True

    def test_gold_validation(self):
        allowed = {"a", "b", "c", "d"}
        assert gold_valid_against_allowed("a;c", allowed)
        assert not gold_valid_against_allowed("e", allowed)
        assert gold_valid_against_allowed(r"\frac{1}{2}", allowed)

    def test_allowed_choice_extraction(self):
        prompt = "Choose: (A) foo, (b) bar; c) baz; d. qux [e]"
        self.assertEqual(allowed_choice_set_from_prompt(prompt), {"a", "b", "c", "d", "e"})

    def test_numeric_list_tolerance(self):
        self.assertTrue(numeric_equal([0.50, 1.0], [0.5, 1.00], tol=0.02))
        self.assertTrue(numeric_equal([(1.0, 2.0)], [(1.00, 2.01)], tol=0.02))


if __name__ == "__main__":
    unittest.main()
