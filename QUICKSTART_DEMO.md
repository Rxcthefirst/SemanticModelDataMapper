# Quick Start - Run the Demo

## 🚀 Fastest Way to See It Work

```bash
cd /path/to/SemanticModelDataMapper
python3 examples/demo/run_demo.py
```

**Runtime**: 5-10 minutes  
**Result**: See mapping success improve from 45% → 90%

## 📋 What You'll See

1. **Initial Coverage**: ~50% SKOS labels
2. **Poor Mapping**: Only 45% columns mapped
3. **Enrichment**: Add missing SKOS labels
4. **Better Mapping**: 75% columns mapped
5. **More Enrichment**: Add more labels
6. **Great Mapping**: 90% columns mapped
7. **Statistics**: Timeline showing improvement

## 📂 Demo Files

```
examples/demo/
├── README.md              ← Full documentation
├── run_demo.py            ← Run this!
├── ontology/
│   └── hr_ontology_initial.ttl
└── data/
    └── employees.csv
```

## 🧪 Run Tests

```bash
# All 144 tests
python3 -m pytest tests/ -v

# Just Phase 3 tests (14 tests)
python3 -m pytest tests/test_phase3_features.py -v
```

## 📊 Key Commands

```bash
# Validate SKOS coverage
rdfmap validate-ontology --ontology onto.ttl --min-coverage 0.7

# Generate mapping with alignment report
rdfmap generate --ontology onto.ttl --data data.csv \
  --target-class http://example.org#Class \
  --alignment-report report.json

# Enrich ontology (interactive)
rdfmap enrich --ontology onto.ttl \
  --alignment-report report.json \
  --interactive

# Enrich ontology (auto)
rdfmap enrich --ontology onto.ttl \
  --alignment-report report.json \
  --output enriched.ttl \
  --auto-apply --min-confidence 0.7

# View improvement statistics
rdfmap stats --reports-dir alignment_reports/ --verbose
```

## 📈 Expected Results

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| SKOS Coverage | 50% | 85% | +35% |
| Mapping Success | 45% | 90% | +45% |
| Unmapped Columns | 8 | 1 | -7 |
| Avg Confidence | 0.52 | 0.88 | +0.36 |

## 📚 Documentation

- **Full Demo Guide**: `examples/demo/README.md`
- **Phase 3 Features**: `PHASE_3_COMPLETE.md`
- **Tests & Demo Summary**: `PHASE_3_TESTS_AND_DEMO_COMPLETE.md`
- **Final Summary**: `TESTS_AND_DEMO_FINAL_SUMMARY.md`

## ✅ Status

- **Tests**: 144/144 passing ✅
- **Coverage**: 63% ✅
- **Demo**: Ready to run ✅
- **Documentation**: Complete ✅

## 🎯 For Your Team

This demo shows:
1. **Concrete ROI**: 45% → 90% improvement (quantifiable)
2. **Automation**: Auto-enrichment with confidence thresholds
3. **Visibility**: Statistics track improvements over time
4. **Standards**: Full W3C SKOS compliance
5. **Simplicity**: 1 command to run complete demo

**Perfect for presentations!** 🎉
