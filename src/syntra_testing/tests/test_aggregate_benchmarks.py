#!/usr/bin/env python3
"""
Tests for benchmark aggregator
Validates metric extraction, merging, and output generation.
"""

import os
import sys
import json
import tempfile
import unittest
import shutil
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.dirname(__file__))  # tools/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))  # project root

from aggregate_benchmarks import (
    extract_metrics_from_pass1,
    extract_metrics_from_report,
    find_benchmark_files,
    aggregate_benchmarks,
    merge_baseline_syntra,
    write_csv,
    write_markdown
)


class TestBenchmarkAggregator(unittest.TestCase):
    """Test suite for benchmark aggregator."""

    def setUp(self):
        """Set up test environment with stub data."""
        self.test_dir = tempfile.mkdtemp()

        # Create stub runs directory structure
        self.runs_dir = os.path.join(self.test_dir, 'runs')
        os.makedirs(self.runs_dir)

        # Create stub _stubs directory
        self.stubs_dir = os.path.join(self.runs_dir, '_stubs')
        os.makedirs(self.stubs_dir)

        # Create stub CMT data
        cmt_dir = os.path.join(self.stubs_dir, 'hf_cmt')
        os.makedirs(cmt_dir)

        # Create stub pass1.jsonl for CMT baseline
        cmt_baseline_pass1 = os.path.join(cmt_dir, 'hf_cmt_baseline.pass1.jsonl')
        with open(cmt_baseline_pass1, 'w') as f:
            for i in range(10):
                record = {
                    'id': f'cmt_{i}',
                    'pass': i % 2 == 0,  # 5 correct out of 10
                    'latency_ms': 100 + i * 10
                }
                f.write(json.dumps(record) + '\n')

        # Create stub pass1.jsonl for CMT syntra
        cmt_syntra_pass1 = os.path.join(cmt_dir, 'hf_cmt_syntra.pass1.jsonl')
        with open(cmt_syntra_pass1, 'w') as f:
            for i in range(10):
                record = {
                    'id': f'cmt_{i}',
                    'pass': i % 3 == 0,  # 4 correct out of 10
                    'latency_ms': 120 + i * 8
                }
                f.write(json.dumps(record) + '\n')

        # Create stub ARC data
        arc_dir = os.path.join(self.stubs_dir, 'arc_challenge')
        os.makedirs(arc_dir)

        # Create stub pass1.jsonl for ARC syntra
        arc_syntra_pass1 = os.path.join(arc_dir, 'arc_challenge_validation_syntra.pass1.jsonl')
        with open(arc_syntra_pass1, 'w') as f:
            for i in range(5):
                record = {
                    'id': f'arc_{i}',
                    'pass': i < 3,  # 3 correct out of 5
                    'latency_ms': 200 + i * 20
                }
                f.write(json.dumps(record) + '\n')

    def tearDown(self):
        """Clean up test environment."""
        shutil.rmtree(self.test_dir)

    def test_extract_metrics_from_pass1(self):
        """Test extracting metrics from pass1.jsonl file."""
        pass1_file = os.path.join(self.stubs_dir, 'hf_cmt', 'hf_cmt_baseline.pass1.jsonl')

        metrics = extract_metrics_from_pass1(pass1_file)

        self.assertAlmostEqual(metrics['pass1'], 0.5, places=2)  # 5/10
        self.assertEqual(metrics['n'], 10)
        self.assertEqual(metrics['n_correct'], 5)
        self.assertAlmostEqual(metrics['latency_mean_ms'], 145.0, places=1)  # (100+110+...+190)/10

    def test_extract_metrics_from_report(self):
        """Test extracting metrics from eval.report.md file."""
        # Create a stub report file
        report_content = """
# ARC Evaluation Report

## Summary

- **Pass@1 Accuracy**: 85.00%
- **Total Questions**: 20
- **Latency (mean)**: 1250.3 ms
"""

        report_file = os.path.join(self.test_dir, 'test_report.md')
        with open(report_file, 'w') as f:
            f.write(report_content)

        metrics = extract_metrics_from_report(report_file)

        self.assertEqual(metrics['pass1'], 0.85)
        self.assertEqual(metrics['n'], 20)
        self.assertEqual(metrics['latency_mean_ms'], 1250.3)

    def test_find_benchmark_files(self):
        """Test finding benchmark files in runs directory."""
        # Temporarily modify the runs path for testing
        import aggregate_benchmarks as agg
        original_patterns = agg.SUITE_PATTERNS.copy()

        # Update patterns to use _stubs
        agg.SUITE_PATTERNS = {
            'hf_cmt': {
                'pattern': 'hf_cmt*pass1.jsonl',
                'benchmark': 'CMT',
                'split': 'test'
            },
            'arc_challenge': {
                'pattern': 'arc_challenge*pass1.jsonl',
                'benchmark': 'ARC-Challenge',
                'split': 'validation'
            }
        }

        try:
            files = find_benchmark_files(self.stubs_dir)

            # Should find 3 files: 2 CMT + 1 ARC
            self.assertEqual(len(files), 3)

            # Check file types
            cmt_files = [f for f in files if f['benchmark'] == 'CMT']
            arc_files = [f for f in files if f['benchmark'] == 'ARC-Challenge']

            self.assertEqual(len(cmt_files), 2)
            self.assertEqual(len(arc_files), 1)

        finally:
            agg.SUITE_PATTERNS = original_patterns

    def test_aggregate_benchmarks(self):
        """Test aggregating benchmarks from stub directory."""
        # Temporarily modify the runs path for testing
        import aggregate_benchmarks as agg
        original_patterns = agg.SUITE_PATTERNS.copy()

        # Update patterns to use _stubs
        agg.SUITE_PATTERNS = {
            'hf_cmt': {
                'pattern': 'hf_cmt*pass1.jsonl',
                'benchmark': 'CMT',
                'split': 'test'
            },
            'arc_challenge': {
                'pattern': 'arc_challenge*pass1.jsonl',
                'benchmark': 'ARC-Challenge',
                'split': 'validation'
            }
        }

        try:
            results = aggregate_benchmarks(self.stubs_dir)

            # Should have 3 results
            self.assertEqual(len(results), 3)

            # Check CMT results
            cmt_results = [r for r in results if r['benchmark'] == 'CMT']
            self.assertEqual(len(cmt_results), 2)

            baseline_cmt = next(r for r in cmt_results if r['system'] == 'baseline')
            syntra_cmt = next(r for r in cmt_results if r['system'] == 'syntra')

            self.assertAlmostEqual(baseline_cmt['pass1'], 0.5)
            self.assertAlmostEqual(syntra_cmt['pass1'], 0.4, places=2)  # 4/10 = 0.4

        finally:
            agg.SUITE_PATTERNS = original_patterns

    def test_merge_baseline_syntra(self):
        """Test merging baseline and syntra results with deltas."""
        results = [
            {
                'benchmark': 'CMT',
                'split': 'test',
                'system': 'baseline',
                'pass1': 0.5,
                'n': 10,
                'latency_mean_ms': 145.0
            },
            {
                'benchmark': 'CMT',
                'split': 'test',
                'system': 'syntra',
                'pass1': 0.4,
                'n': 10,
                'latency_mean_ms': 155.0
            }
        ]

        merged = merge_baseline_syntra(results)

        # Should have 3 results: baseline, syntra, delta
        self.assertEqual(len(merged), 3)

        delta_result = next(r for r in merged if r['system'] == 'delta')
        self.assertAlmostEqual(delta_result['pass1'], -0.1, places=2)  # 0.4 - 0.5
        self.assertAlmostEqual(delta_result['latency_mean_ms'], 10.0, places=1)  # 155 - 145

    def test_write_csv(self):
        """Test writing results to CSV."""
        results = [
            {
                'benchmark': 'CMT',
                'split': 'test',
                'system': 'baseline',
                'pass1': 0.5,
                'n': 10,
                'latency_mean_ms': 145.0
            }
        ]

        csv_file = os.path.join(self.test_dir, 'test_output.csv')
        write_csv(results, csv_file)

        self.assertTrue(os.path.exists(csv_file))

        # Check content
        with open(csv_file, 'r') as f:
            content = f.read()
            self.assertIn('benchmark,split,system,pass1,n,latency_mean_ms', content)
            self.assertIn('CMT,test,baseline,0.500,10,145.0', content)

    def test_write_markdown(self):
        """Test writing results to Markdown."""
        results = [
            {
                'benchmark': 'CMT',
                'split': 'test',
                'system': 'baseline',
                'pass1': 0.5,
                'n': 10,
                'latency_mean_ms': 145.0
            }
        ]

        md_file = os.path.join(self.test_dir, 'test_output.md')
        write_markdown(results, md_file)

        self.assertTrue(os.path.exists(md_file))

        # Check content
        with open(md_file, 'r') as f:
            content = f.read()
            self.assertIn('# Benchmark Results Overview', content)
            self.assertIn('| Benchmark | Split | System | Pass@1 | N | Latency (ms) |', content)
            self.assertIn('| CMT | test | baseline | 0.500 | 10 | 145.0 |', content)


if __name__ == "__main__":
    unittest.main()