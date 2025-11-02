#!/usr/bin/env python3
"""
Demo Script: Semantic Alignment Improvement Cycle

This script demonstrates the complete workflow of semantic data mapping with
continuous improvement through ontology enrichment.

Workflow:
1. Validate initial ontology SKOS coverage
2. Generate mapping with alignment report (low coverage)
3. Enrich ontology with SKOS labels
4. Re-validate coverage (improved)
5. Re-generate mapping (better alignment)
6. Analyze statistics showing improvement

Requirements:
- Run from project root directory
- Package must be installed: pip install -e .
"""

import sys
import json
from pathlib import Path
from datetime import datetime, timedelta
import subprocess
import shutil

# Demo directories
DEMO_DIR = Path("examples/demo")
ONTOLOGY_DIR = DEMO_DIR / "ontology"
DATA_DIR = DEMO_DIR / "data"
REPORTS_DIR = DEMO_DIR / "alignment_reports"
OUTPUT_DIR = DEMO_DIR / "output"

# Files
INITIAL_ONTOLOGY = ONTOLOGY_DIR / "hr_ontology_initial.ttl"
ENRICHED_ONTOLOGY_1 = ONTOLOGY_DIR / "hr_ontology_enriched_1.ttl"
ENRICHED_ONTOLOGY_2 = ONTOLOGY_DIR / "hr_ontology_enriched_2.ttl"
EMPLOYEE_DATA = DATA_DIR / "employees.csv"


def print_section(title: str):
    """Print a formatted section header."""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80 + "\n")


def run_command(cmd: list[str], description: str, allow_nonzero_exit=False):
    """Run a command and print output.
    
    Args:
        cmd: Command and arguments to run
        description: Human-readable description
        allow_nonzero_exit: If True, non-zero exit codes are not treated as errors
    """
    print(f"Running: {description}")
    print(f"Command: {' '.join(cmd)}\n")
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    # Print stdout if available
    if result.stdout:
        print(result.stdout)
    
    # For validate-ontology, exit code 1 just means coverage below threshold (expected for demo)
    if result.returncode != 0 and not allow_nonzero_exit:
        if result.stderr:
            print(f"❌ Error: {result.stderr}")
        return False
    
    return True


def main():
    """Run the complete demo cycle."""
    
    print_section("SEMANTIC ALIGNMENT IMPROVEMENT DEMO")
    print("This demo shows how ontology enrichment improves semantic data mapping.\n")
    
    # Setup
    print("Setting up demo directories...")
    OUTPUT_DIR.mkdir(exist_ok=True)
    REPORTS_DIR.mkdir(exist_ok=True)
    
    # ========================================================================
    # STEP 1: Validate Initial Ontology Coverage
    # ========================================================================
    print_section("STEP 1: Validate Initial Ontology SKOS Coverage")
    print("Check how well the initial ontology is prepared for data mapping.\n")
    
    coverage_report_1 = OUTPUT_DIR / "coverage_report_initial.json"
    
    # Note: validate-ontology exits with code 1 when coverage is below threshold (expected)
    run_command([
        "rdfmap", "validate-ontology",
        "--ontology", str(INITIAL_ONTOLOGY),
        "--min-coverage", "0.7",
        "--output", str(coverage_report_1),
        "--verbose"
    ], "Validate initial ontology SKOS coverage", allow_nonzero_exit=True)
    
    input("\n⏸️  Press Enter to continue to Step 2...\n")
    
    # ========================================================================
    # STEP 2: Generate Initial Mapping
    # ========================================================================
    print_section("STEP 2: Generate Initial Mapping (Before Enrichment)")
    print("Attempt to map employee data to ontology without enrichment.\n")
    
    # Simulate timestamp for first report
    report_1_time = datetime.now() - timedelta(days=14)
    mapping_1_path = OUTPUT_DIR / "mapping_initial.yaml"
    
    if not run_command([
        "rdfmap", "generate",
        "--ontology", str(INITIAL_ONTOLOGY),
        "--spreadsheet", str(EMPLOYEE_DATA),
        "--class", "http://example.org/hr#Employee",
        "--output", str(mapping_1_path),
        "--alignment-report"
    ], "Generate initial mapping with alignment report"):
        return 1
    
    # The alignment report is auto-generated with _alignment_report.json suffix
    auto_report_path = OUTPUT_DIR / "mapping_initial_alignment_report.json"
    report_1_path = REPORTS_DIR / "alignment_report_1.json"
    
    # Move and adjust timestamp in report
    if auto_report_path.exists():
        with open(auto_report_path) as f:
            report_data = json.load(f)
        report_data['generated_at'] = report_1_time.isoformat()
        with open(report_1_path, 'w') as f:
            json.dump(report_data, f, indent=2)
        auto_report_path.unlink()  # Remove the auto-generated one
    
    input("\n⏸️  Press Enter to continue to Step 3...\n")
    
    # ========================================================================
    # STEP 3: First Enrichment Cycle
    # ========================================================================
    print_section("STEP 3: Enrich Ontology (First Cycle)")
    print("Add SKOS labels for unmapped columns based on suggestions.\n")
    
    if not run_command([
        "rdfmap", "enrich",
        "--ontology", str(INITIAL_ONTOLOGY),
        "--alignment-report", str(report_1_path),
        "--output", str(ENRICHED_ONTOLOGY_1),
        "--auto-apply", "--min-confidence", "0.7"
    ], "Enrich ontology with SKOS labels (first pass)"):
        return 1
    
    input("\n⏸️  Press Enter to continue to Step 4...\n")
    
    # ========================================================================
    # STEP 4: Re-validate Coverage
    # ========================================================================
    print_section("STEP 4: Re-validate Ontology Coverage")
    print("Check if SKOS coverage improved after enrichment.\n")
    
    coverage_report_2 = OUTPUT_DIR / "coverage_report_enriched_1.json"
    
    # Note: May still be below threshold after first enrichment
    run_command([
        "rdfmap", "validate-ontology",
        "--ontology", str(ENRICHED_ONTOLOGY_1),
        "--min-coverage", "0.7",
        "--output", str(coverage_report_2),
        "--verbose"
    ], "Validate enriched ontology", allow_nonzero_exit=True)
    
    input("\n⏸️  Press Enter to continue to Step 5...\n")
    
    # ========================================================================
    # STEP 5: Re-generate Mapping (Improved)
    # ========================================================================
    print_section("STEP 5: Re-generate Mapping (After First Enrichment)")
    print("Map employee data again with enriched ontology.\n")
    
    report_2_time = datetime.now() - timedelta(days=7)
    mapping_2_path = OUTPUT_DIR / "mapping_enriched_1.yaml"
    
    if not run_command([
        "rdfmap", "generate",
        "--ontology", str(ENRICHED_ONTOLOGY_1),
        "--spreadsheet", str(EMPLOYEE_DATA),
        "--class", "http://example.org/hr#Employee",
        "--output", str(mapping_2_path),
        "--alignment-report"
    ], "Re-generate mapping with enriched ontology"):
        return 1
    
    # The alignment report is auto-generated
    auto_report_path = OUTPUT_DIR / "mapping_enriched_1_alignment_report.json"
    report_2_path = REPORTS_DIR / "alignment_report_2.json"
    
    # Move and adjust timestamp
    if auto_report_path.exists():
        with open(auto_report_path) as f:
            report_data = json.load(f)
        report_data['generated_at'] = report_2_time.isoformat()
        with open(report_2_path, 'w') as f:
            json.dump(report_data, f, indent=2)
        auto_report_path.unlink()
    
    input("\n⏸️  Press Enter to continue to Step 6...\n")

    
    # ========================================================================
    # STEP 6: Second Enrichment Cycle
    # ========================================================================
    print_section("STEP 6: Enrich Ontology (Second Cycle)")
    print("Continue improving with remaining suggestions.\n")
    
    if not run_command([
        "rdfmap", "enrich",
        "--ontology", str(ENRICHED_ONTOLOGY_1),
        "--alignment-report", str(report_2_path),
        "--output", str(ENRICHED_ONTOLOGY_2),
        "--auto-apply", "--min-confidence", "0.6"
    ], "Enrich ontology (second pass)"):
        return 1
    
    input("\n⏸️  Press Enter to continue to Step 7...\n")
    
    # ========================================================================
    # STEP 7: Final Mapping
    # ========================================================================
    print_section("STEP 7: Generate Final Mapping")
    print("Final mapping with fully enriched ontology.\n")
    
    mapping_3_path = OUTPUT_DIR / "mapping_final.yaml"
    
    if not run_command([
        "rdfmap", "generate",
        "--ontology", str(ENRICHED_ONTOLOGY_2),
        "--spreadsheet", str(EMPLOYEE_DATA),
        "--class", "http://example.org/hr#Employee",
        "--output", str(mapping_3_path),
        "--alignment-report"
    ], "Generate final mapping"):
        return 1
    
    # The alignment report is auto-generated
    auto_report_path = OUTPUT_DIR / "mapping_final_alignment_report.json"
    report_3_path = REPORTS_DIR / "alignment_report_3.json"
    
    # Move the auto-generated report
    if auto_report_path.exists():
        auto_report_path.rename(report_3_path)
    
    input("\n⏸️  Press Enter to continue to Step 8...\n")

    
    # ========================================================================
    # STEP 8: Analyze Improvement Statistics
    # ========================================================================
    print_section("STEP 8: Analyze Improvement Over Time")
    print("View statistics showing the improvement cycle.\n")
    
    stats_output = OUTPUT_DIR / "improvement_stats.json"
    
    if not run_command([
        "rdfmap", "stats",
        "--reports-dir", str(REPORTS_DIR),
        "--output", str(stats_output),
        "--verbose"
    ], "Analyze alignment statistics over time"):
        return 1
    
    # ========================================================================
    # SUMMARY
    # ========================================================================
    print_section("DEMO COMPLETE!")
    
    print("✅ Summary of Generated Files:")
    print(f"   • Initial ontology: {INITIAL_ONTOLOGY}")
    print(f"   • Enriched ontology (1st): {ENRICHED_ONTOLOGY_1}")
    print(f"   • Enriched ontology (2nd): {ENRICHED_ONTOLOGY_2}")
    print(f"   • Employee data: {EMPLOYEE_DATA}")
    print(f"   • Alignment reports: {REPORTS_DIR}/")
    print(f"   • Mappings: {OUTPUT_DIR}/mapping_*.yaml")
    print(f"   • Statistics: {stats_output}")
    print(f"   • Coverage reports: {OUTPUT_DIR}/coverage_report_*.json")
    
    print("\n📊 Key Takeaways:")
    print("   1. Initial SKOS coverage determines mapping quality")
    print("   2. Alignment reports identify gaps and suggest improvements")
    print("   3. Ontology enrichment directly improves mapping success rates")
    print("   4. Statistics track and quantify improvement over time")
    print("   5. The process creates a virtuous cycle of continuous improvement")
    
    print("\n💡 Next Steps:")
    print("   • Examine the alignment reports to see specific improvements")
    print("   • Compare the three generated mappings")
    print("   • Review the statistics JSON for detailed metrics")
    print("   • Try the enrichment process interactively")
    
    print("\n" + "=" * 80 + "\n")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
