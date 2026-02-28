#!/usr/bin/env python3
"""
Tests for Tools.clean module.
"""
import os
import sys
import tempfile
import shutil
import unittest
import glob

# ensure project root in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from Tools.clean import clean_runs, clean_caches

class TestCleanModule(unittest.TestCase):
    def setUp(self):
        self.orig_cwd = os.getcwd()
        self.temp_dir = tempfile.mkdtemp()
        os.chdir(self.temp_dir)

        # create dummy runs dir
        self.runs_dir = os.path.join(self.temp_dir, "runs")
        os.makedirs(self.runs_dir)
        # add a dummy file
        dummy = os.path.join(self.runs_dir, "dummy.txt")
        with open(dummy, "w") as f:
            f.write("hello")

        # create cache artifacts
        self.pycache_dir = os.path.join(self.temp_dir, "__pycache__")
        os.makedirs(self.pycache_dir)
        self.cache_file = os.path.join(self.temp_dir, "test.pyc")
        with open(self.cache_file, "w") as f:
            f.write("b")

        self.pytest_cache = os.path.join(self.temp_dir, ".pytest_cache")
        os.makedirs(self.pytest_cache)

    def tearDown(self):
        os.chdir(self.orig_cwd)
        shutil.rmtree(self.temp_dir)

    def test_clean_runs(self):
        # runs dir exists initially
        self.assertTrue(os.path.isdir(self.runs_dir))
        clean_runs(self.runs_dir)
        self.assertFalse(os.path.exists(self.runs_dir))

    def test_clean_caches(self):
        # ensure cache artifacts exist
        self.assertTrue(os.path.isdir(self.pycache_dir))
        self.assertTrue(os.path.isdir(self.pytest_cache))
        self.assertTrue(os.path.isfile(self.cache_file))

        clean_caches()

        self.assertFalse(os.path.exists(self.pycache_dir))
        self.assertFalse(os.path.exists(self.pytest_cache))
        self.assertFalse(os.path.exists(self.cache_file))

if __name__ == "__main__":
    unittest.main()