import pytest
import json
from pathlib import Path
import sys
sys.path.insert(0, 'src')

from syntra_testing.runners.eval_runner import read_prompts

def test_read_prompts():
    """Test prompt loading from JSONL or text."""
    # Create temporary test file
    test_file = Path('test_prompts.jsonl')
    test_data = [
        {"id": 1, "prompt": "What is 2+2?"},
        {"id": 2, "prompt": "Explain gravity."}
    ]
    with open(test_file, 'w') as f:
        for item in test_data:
            f.write(json.dumps(item) + '\n')
    
    prompts = read_prompts(str(test_file))
    assert len(prompts) == 2
    assert prompts[0]['id'] == 1
    test_file.unlink()

def test_read_prompts_fallback():
    """Test fallback for plain text lines."""
    test_file = Path('test_plain.txt')
    with open(test_file, 'w') as f:
        f.write("Test prompt one\nTest prompt two\n")
    prompts = read_prompts(str(test_file))
    assert len(prompts) == 2
    assert 'content' in prompts[0]
    test_file.unlink()

if __name__ == "__main__":
    pytest.main([__file__, "-q"])
