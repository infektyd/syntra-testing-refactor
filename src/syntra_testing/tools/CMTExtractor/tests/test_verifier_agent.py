import json
import os
from unittest.mock import patch, mock_open
import sys
import verify_outputs

# Add parent dir to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from verify_outputs import validate_schema, check_numerical_coherence, diff_baseline, main

def test_validate_schema_valid():
    mock_audit = {
        'total_items': 50,
        'valid_gold': 50,
        'gold_invalid': 0,
        'identical_model_predictions': 24,
        'shared_identity_indices': 50,
        'mc_identity_compared': 20,
        'raw_identity_compared': 20,
        'cross_mode_skipped': 10
    }
    with patch('builtins.open', mock_open(read_data=json.dumps(mock_audit))) as m:
        assert validate_schema('mock_path') is True
        m.assert_called_once_with('mock_path', 'r')

def test_validate_schema_missing_key():
    mock_audit = {'total_items': 50}  # Missing others
    with patch('builtins.open', mock_open(read_data=json.dumps(mock_audit))):
        assert validate_schema('mock_path') is False

def test_validate_schema_non_numeric():
    mock_audit = {'total_items': 'fifty'}  # String instead of int
    with patch('builtins.open', mock_open(read_data=json.dumps(mock_audit))):
        assert validate_schema('mock_path') is False

def test_check_numerical_coherence_valid():
    audit = {
        'shared_identity_indices': 50,
        'mc_identity_compared': 20,
        'raw_identity_compared': 20,
        'cross_mode_skipped': 10
    }
    assert check_numerical_coherence(audit) is True

def test_check_numerical_coherence_invalid():
    audit = {
        'shared_identity_indices': 50,
        'mc_identity_compared': 20,
        'raw_identity_compared': 20,
        'cross_mode_skipped': 11  # Sum 51 != 50
    }
    assert check_numerical_coherence(audit) is False

def test_diff_baseline_within_tolerance():
    audit = {'identical_model_predictions': 24, 'valid_gold': 50}
    expected = {'identical_model_predictions': 24, 'valid_gold': 50}
    with patch('builtins.open', mock_open(read_data=json.dumps(expected))):
        assert diff_baseline(audit, 'mock_expected') is True

def test_diff_baseline_exceeds_tolerance():
    audit = {'identical_model_predictions': 20, 'valid_gold': 50}  # 20% diff
    expected = {'identical_model_predictions': 25, 'valid_gold': 50}
    with patch('builtins.open', mock_open(read_data=json.dumps(expected))):
        assert diff_baseline(audit, 'mock_expected') is False

def test_diff_baseline_missing_file():
    audit = {}
    with patch('builtins.open', side_effect=FileNotFoundError):
        assert diff_baseline(audit, 'missing_path') is True  # Warn but pass

def test_main_success():
    mock_args = ['--audit', 'mock_audit.json', '--suite', 'hf_cmt']
    with patch('sys.argv', mock_args), \
         patch('builtins.open', mock_open(read_data='{}')),\
         patch('verify_outputs.validate_schema', return_value=True), \
         patch('verify_outputs.check_numerical_coherence', return_value=True), \
         patch('verify_outputs.diff_baseline', return_value=True):
        assert main() == 0

if __name__ == '__main__':
    import pytest
    pytest.main([__file__])
