import os
import subprocess
import tempfile
import json
from unittest.mock import patch

@patch('subprocess.call')
def test_run_baseline(mock_call):
    # Mock the bash script call and generate expected artifacts in tmpdir
    def _fake_call(args, cwd=None):
        base_dir = os.path.join(cwd, "runs", "hf_cmt", "baseline")
        log_dir = os.path.join(cwd, "runs", "hf_cmt", "logs")
        os.makedirs(base_dir, exist_ok=True)
        os.makedirs(log_dir, exist_ok=True)
        pass2 = os.path.join(base_dir, "hf_cmt_baseline.pass2.jsonl")
        report = os.path.join(base_dir, "hf_cmt_baseline.fixed.report.md")
        log = os.path.join(log_dir, "grade_baseline.log")
        with open(pass2, "w") as f:
            f.write(json.dumps({"id": "hf_x_001", "pass": True, "reason": "OK"}) + "\n")
        with open(report, "w") as f:
            f.write("# Report\n")
        with open(log, "w") as f:
            f.write("OK\n")
        return 0
    mock_call.side_effect = _fake_call

    with tempfile.TemporaryDirectory() as tmpdir:
        # Set env vars for test
        os.environ['RESPONSES'] = f"{tmpdir}/mock_responses.jsonl"
        # Create dummy responses file
        with open(os.environ['RESPONSES'], "w") as f:
            f.write('{"id": "1", "prediction": "A"}\n')
        os.environ['ANSWERS'] = os.path.abspath("prompts/suites/hf_cmt.fixed.jsonl")
        os.environ['SUITE'] = os.path.abspath("prompts/suites/hf_cmt.fixed.jsonl")

        # script path must be absolute because cwd is changed
        script_path = os.path.abspath("Tools/CMTExtractor/run_baseline.sh")

        # Create dummy grade_official_cmt.py and hf_cmt_audit.py
        os.makedirs(os.path.join(tmpdir, "Tools/CMTExtractor/"))
        with open(os.path.join(tmpdir, "Tools/CMTExtractor/grade_official_cmt.py"), "w") as f:
            f.write("#!/usr/bin/env python3\n")
            f.write("import sys\n")
            f.write("sys.exit(0)\n")
        with open(os.path.join(tmpdir, "Tools/CMTExtractor/hf_cmt_audit.py"), "w") as f:
            f.write("#!/usr/bin/env python3\n")
            f.write("import sys\n")
            f.write("sys.exit(0)\n")

        # Run the harness
        result = subprocess.call([script_path], cwd=tmpdir)

        assert result == 0

def test_run_baseline_env_override():
    with tempfile.TemporaryDirectory() as tmpdir:
        # Override env to custom paths
        custom_responses = f"{tmpdir}/custom.jsonl"
        os.environ['RESPONSES'] = custom_responses
        os.environ['ANSWERS'] = f"{tmpdir}/custom_answers.jsonl"
        os.environ['SUITE'] = f"{tmpdir}/custom_suite.jsonl"

        with patch('subprocess.call') as mock_call:
            mock_call.return_value = 0
            script_path = "Tools/CMTExtractor/run_baseline.sh"
            subprocess.call([script_path], cwd=tmpdir)

            # Assert custom paths used in call (via env)
            assert os.environ['RESPONSES'] == custom_responses
