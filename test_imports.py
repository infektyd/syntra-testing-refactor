import sys
sys.path.insert(0, './src')
success = True
tests = [
    'from syntra_testing.tools import clean',
    'from syntra_testing.tools import grade_and_aggregate',
    'from syntra_testing.tools import gen_manifest',
    'from syntra_testing.tools.grading import grader_utils',
]
for t in tests:
    try:
        exec(t)
        print(f"OK: {t.split()[-1]}")
    except Exception as e:
        print(f"FAIL: {t} - {e}")
        success = False
if success:
    print("All key imports successful!")
else:
    print("Some imports failed (CMT/viz modules need extra deps).")
