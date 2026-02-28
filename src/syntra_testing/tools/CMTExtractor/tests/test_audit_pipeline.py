#!/usr/bin/env python3
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from grader_utils import (
    allowed_choice_set_from_prompt,
    gold_valid_against_allowed,
    parse_numeric_list,
)
from hf_cmt_audit import compare_predictions, normalize_answer


class TestAuditPipeline(unittest.TestCase):
    def test_parameter_fallback_for_allowed_options(self):
        prompt = "Determine the correct response."
        params = "Options: a) kinetic; b) potential"
        allowed = allowed_choice_set_from_prompt(prompt)
        if allowed is None:
            allowed = allowed_choice_set_from_prompt(params)
        self.assertEqual(allowed, {"a", "b"})
        self.assertTrue(gold_valid_against_allowed("a;b", allowed))

    def test_numeric_tolerance_on_lists(self):
        gold_norm = normalize_answer("0.50; 1.0")
        pred_norm = normalize_answer("0.5; 1.01")
        gold_parsed = parse_numeric_list(gold_norm)
        pred_parsed = parse_numeric_list(pred_norm)
        result = compare_predictions(gold_norm, pred_norm, gold_parsed, pred_parsed)
        self.assertTrue(result["numeric_equal"])
        self.assertTrue(result["overall"])

    def test_mc_order_normalization(self):
        gold_norm = normalize_answer("c;A;b")
        pred_norm = normalize_answer("b;c;a")
        result = compare_predictions(gold_norm, pred_norm, None, None)
        self.assertTrue(result["mc_equal"])
        self.assertTrue(result["overall"])


if __name__ == "__main__":
    unittest.main()
