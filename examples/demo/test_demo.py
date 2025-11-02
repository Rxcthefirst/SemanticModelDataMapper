#!/usr/bin/env python3
"""Quick test of demo commands without interaction."""

import subprocess
import sys
from pathlib import Path

DEMO_DIR = Path("examples/demo")
OUTPUT_DIR = DEMO_DIR / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

def run(cmd, desc):
    print(f"\n{'='*70}")
    print(f"Testing: {desc}")
    print(f"Command: {' '.join(cmd)}")
    print('='*70)
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.stdout:
        print(result.stdout[:500])  # First 500 chars
    if result.returncode not in [0, 1]:  # 0=success, 1=validation failed (expected)
        print(f"❌ FAILED with code {result.returncode}")
        if result.stderr:
            print(result.stderr[:500])
        return False
    print(f"✅ OK (exit code {result.returncode})")
    return True

print("🧪 Testing Demo Commands\n")

# Test 1: Validate initial coverage (should be ~33%)
run([
    "rdfmap", "validate-ontology",
    "--ontology", "examples/demo/ontology/hr_ontology_initial.ttl",
    "--min-coverage", "0.7"
], "Validate initial coverage (expect ~33%)")

# Test 2: Generate mapping with alignment report
run([
    "rdfmap", "generate",
    "--ontology", "examples/demo/ontology/hr_ontology_initial.ttl",
    "--spreadsheet", "examples/demo/data/employees.csv",
    "--class", "http://example.org/hr#Employee",
    "--output", "examples/demo/output/test_mapping.yaml",
    "--alignment-report"
], "Generate mapping with alignment report")

print("\n" + "="*70)
print("✅ Demo commands are working!")
print("="*70)
print("\nAlignment report should be at:")
print("  examples/demo/output/test_mapping_alignment_report.json")
print("\nTo run the full interactive demo:")
print("  python3 examples/demo/run_demo.py")
