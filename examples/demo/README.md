# Semantic Alignment Improvement Demo

This demo showcases the complete workflow of semantic data mapping with continuous improvement through ontology enrichment.

## Overview

The demo demonstrates how **SKOS label coverage** in ontologies directly impacts **mapping success rates** when converting spreadsheet data to RDF. It shows a virtuous cycle:

```
Low Coverage → Poor Mapping → Generate Suggestions → Enrich Ontology →
Better Coverage → Better Mapping → Track Improvement → Repeat
```

## Demo Components

### 1. HR Ontology (`ontology/hr_ontology_initial.ttl`)

A realistic HR management ontology with:
- **4 Classes**: Person, Employee, Organization, Position
- **23 Properties**: Personal info, employment details, organizational data
- **Initial SKOS Coverage**: ~50% (deliberately incomplete for demo)

Missing SKOS labels include:
- Hidden labels for common abbreviations (emp_num, mgr_id, dept_code)
- Alternative labels for synonyms
- Preferred labels for several properties

### 2. Employee Dataset (`data/employees.csv`)

27 employee records with **intentionally messy column names** that reflect real-world data:
- `emp_num` instead of `employeeNumber`
- `fname`, `lname` instead of `firstName`, `lastName`
- `dept_code` instead of `organizationCode`
- `mgr_id` instead of `manager`
- `hire_dt` instead of `hireDate`
- `annual_comp` instead of `salary`

This reflects actual corporate data where columns don't match ontology property names.

### 3. Demo Script (`run_demo.py`)

Automated demonstration of the complete 8-step improvement cycle.

## The Improvement Cycle

### Step 1: Validate Initial Coverage

Check SKOS label coverage of the original ontology:

```bash
rdfmap validate-ontology \
  --ontology ontology/hr_ontology_initial.ttl \
  --min-coverage 0.7 \
  --verbose
```

**Expected Result**: Coverage around 50-60% - below the 70% threshold.

### Step 2: Generate Initial Mapping

Attempt to map employee data with limited SKOS coverage:

```bash
rdfmap generate \
  --ontology ontology/hr_ontology_initial.ttl \
  --data data/employees.csv \
  --target-class http://example.org/hr#Employee \
  --output output/mapping_initial.yaml \
  --alignment-report alignment_reports/report_1.json
```

**Expected Result**: 
- **Success Rate**: 40-50%
- **Unmapped Columns**: emp_num, mgr_id, dept_code, annual_comp, etc.
- **SKOS Suggestions**: 6-8 suggestions for hidden labels

### Step 3: First Enrichment

Apply SKOS suggestions automatically:

```bash
rdfmap enrich \
  --ontology ontology/hr_ontology_initial.ttl \
  --alignment-report alignment_reports/report_1.json \
  --output ontology/hr_ontology_enriched_1.ttl \
  --auto-apply \
  --min-confidence 0.7
```

**What Happens**:
- Adds `skos:hiddenLabel "emp_num"` to `employeeNumber`
- Adds `skos:hiddenLabel "mgr_id"` to `hasManager`
- Adds `skos:altLabel` for common synonyms
- Preserves provenance with `dcterms:modified` and `prov:wasGeneratedBy`

### Step 4: Re-validate Coverage

Check improved coverage:

```bash
rdfmap validate-ontology \
  --ontology ontology/hr_ontology_enriched_1.ttl \
  --min-coverage 0.7
```

**Expected Result**: Coverage improves to 65-75%

### Step 5: Re-generate Mapping

Map with enriched ontology:

```bash
rdfmap generate \
  --ontology ontology/hr_ontology_enriched_1.ttl \
  --data data/employees.csv \
  --target-class http://example.org/hr#Employee \
  --output output/mapping_enriched_1.yaml \
  --alignment-report alignment_reports/report_2.json
```

**Expected Result**:
- **Success Rate**: 70-80% (significant improvement!)
- **Unmapped Columns**: 2-4 remaining
- **Higher Confidence**: More matches use exact SKOS labels

### Step 6: Second Enrichment

Continue improving:

```bash
rdfmap enrich \
  --ontology ontology/hr_ontology_enriched_1.ttl \
  --alignment-report alignment_reports/report_2.json \
  --output ontology/hr_ontology_enriched_2.ttl \
  --auto-apply \
  --min-confidence 0.6
```

### Step 7: Final Mapping

Generate final mapping:

```bash
rdfmap generate \
  --ontology ontology/hr_ontology_enriched_2.ttl \
  --data data/employees.csv \
  --target-class http://example.org/hr#Employee \
  --output output/mapping_final.yaml \
  --alignment-report alignment_reports/report_3.json
```

**Expected Result**:
- **Success Rate**: 85-95%
- **Unmapped Columns**: 0-2
- **High Confidence**: Most matches are exact

### Step 8: Analyze Statistics

View improvement metrics:

```bash
rdfmap stats \
  --reports-dir alignment_reports/ \
  --output output/improvement_stats.json \
  --verbose
```

**Expected Output**:
```
TREND ANALYSIS
----------------------------------------------------------------------
Overall Trend: 📈 IMPROVING
Success Rate: 45.0% → 90.0% (+45.0%)
Avg Confidence: 0.52 → 0.88 (+0.36)

MOST IMPROVED COLUMNS
----------------------------------------------------------------------
1. emp_num
   Current Success Rate: 100.0%
   Appearances: 3

2. mgr_id
   Current Success Rate: 100.0%
   Appearances: 3
```

## Running the Demo

### Automated Mode

Run the complete demo script:

```bash
cd /path/to/SemanticModelDataMapper
python3 examples/demo/run_demo.py
```

The script will:
1. Run all 8 steps automatically
2. Pause between steps for observation
3. Generate all output files
4. Display comprehensive summary

### Manual Mode

Run each step individually to explore:

```bash
cd examples/demo

# Step 1: Validate initial ontology coverage
rdfmap validate-ontology --ontology ontology/hr_ontology_initial.ttl --verbose

# Step 2: Generate initial mapping with alignment report
rdfmap generate --ontology ontology/hr_ontology_initial.ttl \
  --spreadsheet data/employees.csv \
  --class http://example.org/hr#Employee \
  --output output/mapping_initial.yaml \
  --alignment-report

# The alignment report will be auto-generated as:
# output/mapping_initial_alignment_report.json

# Step 3: Enrich ontology using alignment report
rdfmap enrich \
  --ontology ontology/hr_ontology_initial.ttl \
  --alignment-report output/mapping_initial_alignment_report.json \
  --output output/hr_ontology_enriched_1.ttl

# And so on...
```

### Interactive Enrichment Mode

For hands-on exploration, use interactive mode:

```bash
rdfmap enrich \
  --ontology ontology/hr_ontology_initial.ttl \
  --alignment-report alignment_reports/report_1.json \
  --interactive
```

You'll be prompted to approve each SKOS label addition.

## What to Look For

### 1. Alignment Reports

Compare the three reports:
- `alignment_reports/report_1.json` - Initial state
- `alignment_reports/report_2.json` - After first enrichment
- `alignment_reports/report_3.json` - After second enrichment

Notice:
- Decreasing `unmapped_columns` list
- Increasing `mapping_success_rate`
- Decreasing `skos_enrichment_suggestions`
- Improving `average_confidence`

### 2. Enriched Ontologies

Compare:
```bash
diff ontology/hr_ontology_initial.ttl ontology/hr_ontology_enriched_1.ttl
```

You'll see new SKOS labels added with provenance metadata.

### 3. Generated Mappings

Compare mapping quality:
- `output/mapping_initial.yaml` - Sparse, many missing
- `output/mapping_enriched_1.yaml` - Better coverage
- `output/mapping_final.yaml` - Comprehensive mapping

### 4. Statistics Report

The `improvement_stats.json` file contains:
- **Timeline**: Success rates over time
- **Trend Analysis**: Quantitative improvement metrics
- **Column History**: Which columns improved
- **SKOS Impact**: Number of suggestions applied

## Key Metrics to Track

| Metric | Initial | After 1st | After 2nd | Improvement |
|--------|---------|-----------|-----------|-------------|
| **SKOS Coverage** | ~50% | ~70% | ~85% | +35% |
| **Mapping Success** | ~45% | ~75% | ~90% | +45% |
| **Avg Confidence** | 0.52 | 0.72 | 0.88 | +0.36 |
| **Unmapped Columns** | 8 | 3 | 1 | -7 |
| **High Conf Matches** | 2 | 8 | 12 | +10 |

## Educational Value

This demo teaches:

1. **SKOS Importance**: Shows concrete impact of SKOS labels on mapping quality
2. **Continuous Improvement**: Demonstrates iterative refinement process
3. **Automation vs Manual**: Shows both auto-apply and interactive enrichment
4. **Metrics-Driven**: Uses quantitative data to track progress
5. **Real-World Patterns**: Uses realistic messy data and ontology gaps

## Customization

### Using Your Own Data

Replace the demo data with your own:

```bash
# Your ontology (Turtle or RDF/XML)
cp my_ontology.ttl examples/demo/ontology/

# Your spreadsheet data
cp my_data.csv examples/demo/data/

# Run with your files
rdfmap generate \
  --ontology examples/demo/ontology/my_ontology.ttl \
  --data examples/demo/data/my_data.csv \
  --target-class http://example.org#MyClass \
  --alignment-report my_report.json
```

### Adjusting Thresholds

Experiment with different confidence thresholds:

```bash
# More aggressive enrichment (lower threshold)
rdfmap enrich --min-confidence 0.5 ...

# Conservative enrichment (higher threshold)
rdfmap enrich --min-confidence 0.85 ...
```

## Troubleshooting

### No Suggestions Generated

If you get no SKOS suggestions:
- Check that columns are actually unmapped (review alignment report)
- Lower the confidence threshold
- Ensure ontology has properties matching your data domain

### Poor Matching Quality

If mappings are still poor after enrichment:
- Check that enriched labels were actually added (inspect enriched ontology)
- Verify target class is correct
- Ensure spreadsheet has valid data
- Review weak matches in alignment report

### Script Errors

If the demo script fails:
- Ensure package is installed: `pip install -e .`
- Run from project root directory
- Check that all demo files exist
- Verify Python 3.9+

## Next Steps

After completing the demo:

1. **Try with Your Data**: Apply the process to your actual datasets
2. **Explore Other Commands**: Check out `rdfmap convert`, `rdfmap validate`
3. **Read the Docs**: Review `/docs` for advanced features
4. **Contribute**: Share improvements or report issues on GitHub

## Questions?

- Review the main README.md
- Check documentation in `/docs`
- Examine test files in `/tests` for more examples
- Read the SEMANTIC_ALIGNMENT_STRATEGY.md for methodology

---

**Demo Version**: 1.0  
**Last Updated**: November 2025  
**Estimated Runtime**: 5-10 minutes (automated mode)
