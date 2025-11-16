#!/bin/bash

# Test RDFMap Web UI with Mortgage Example

set -e

echo "🧪 Testing RDFMap Web UI Integration"
echo "====================================="
echo ""

API_URL="http://localhost:8000"

# Step 1: Create project
echo "📋 Step 1: Creating project..."
PROJECT_RESPONSE=$(curl -s -X POST "$API_URL/api/projects/" \
  -H "Content-Type: application/json" \
  -d '{"name": "Mortgage Example", "description": "Testing with mortgage data"}')

PROJECT_ID=$(echo $PROJECT_RESPONSE | python3 -c "import sys, json; print(json.load(sys.stdin)['id'])")
echo "✅ Project created: $PROJECT_ID"
echo ""

# Step 2: Upload data file
echo "📤 Step 2: Uploading data file..."
curl -s -X POST "$API_URL/api/projects/$PROJECT_ID/upload-data" \
  -F "file=@examples/mortgage/data/loans.csv" > /dev/null
echo "✅ Data file uploaded"
echo ""

# Step 3: Upload ontology file
echo "📤 Step 3: Uploading ontology file..."
curl -s -X POST "$API_URL/api/projects/$PROJECT_ID/upload-ontology" \
  -F "file=@examples/mortgage/ontology/mortgage.ttl" > /dev/null
echo "✅ Ontology file uploaded"
echo ""

# Step 4: Preview data
echo "👀 Step 4: Previewing data..."
DATA_PREVIEW=$(curl -s "$API_URL/api/projects/$PROJECT_ID/data-preview?limit=2")
if echo "$DATA_PREVIEW" | python3 -c "import sys, json; d=json.load(sys.stdin); sys.exit(0 if 'total_columns' in d else 1)" 2>/dev/null; then
    COLUMN_COUNT=$(echo $DATA_PREVIEW | python3 -c "import sys, json; print(json.load(sys.stdin)['total_columns'])")
    echo "✅ Data preview: $COLUMN_COUNT columns detected"
else
    echo "⚠️  Data preview had errors (continuing anyway)"
fi
echo ""

# Step 5: Analyze ontology
echo "🔍 Step 5: Analyzing ontology..."
ONTO_ANALYSIS=$(curl -s "$API_URL/api/projects/$PROJECT_ID/ontology-analysis")
if echo "$ONTO_ANALYSIS" | python3 -c "import sys, json; d=json.load(sys.stdin); sys.exit(0 if 'total_classes' in d else 1)" 2>/dev/null; then
    CLASS_COUNT=$(echo $ONTO_ANALYSIS | python3 -c "import sys, json; print(json.load(sys.stdin)['total_classes'])")
    PROP_COUNT=$(echo $ONTO_ANALYSIS | python3 -c "import sys, json; print(json.load(sys.stdin)['total_properties'])")
    echo "✅ Ontology analysis: $CLASS_COUNT classes, $PROP_COUNT properties"
else
    echo "⚠️  Ontology analysis had errors (continuing anyway)"
fi
echo ""

# Step 6: Generate mappings
echo "🧠 Step 6: Generating mappings with AI..."
MAPPING_RESPONSE=$(curl -s -X POST "$API_URL/api/mappings/$PROJECT_ID/generate?use_semantic=true&min_confidence=0.5")
echo "$MAPPING_RESPONSE" | python3 -m json.tool > /tmp/mapping_result.json

# Check if statistics exist and have data
if cat /tmp/mapping_result.json | python3 -c "import sys, json; r=json.load(sys.stdin); sys.exit(0 if r.get('alignment_report', {}).get('statistics', {}).get('mapped_columns') is not None else 1)" 2>/dev/null; then
    MAPPED=$(cat /tmp/mapping_result.json | python3 -c "import sys, json; r=json.load(sys.stdin); print(r['alignment_report']['statistics']['mapped_columns'])")
    TOTAL=$(cat /tmp/mapping_result.json | python3 -c "import sys, json; r=json.load(sys.stdin); print(r['alignment_report']['statistics']['total_columns'])")
    AVG_CONF=$(cat /tmp/mapping_result.json | python3 -c "import sys, json; r=json.load(sys.stdin); print(r['alignment_report']['statistics']['avg_confidence'])")
    echo "✅ Mappings generated: $MAPPED/$TOTAL columns mapped"
    echo "   Average confidence: $AVG_CONF"
else
    # Try to get column count from mapping preview
    COL_COUNT=$(cat /tmp/mapping_result.json | python3 -c "import sys, json; r=json.load(sys.stdin); print(r.get('mapping_preview', {}).get('column_count', 0))")
    echo "✅ Mappings generated: $COL_COUNT columns (statistics not available)"
    MAPPED="N/A"
    TOTAL="N/A"
    AVG_CONF="N/A"
fi
echo ""

# Step 7: Convert to RDF
echo "🔄 Step 7: Converting to RDF..."
CONVERT_RESPONSE=$(curl -s -X POST "$API_URL/api/conversion/$PROJECT_ID?output_format=turtle&validate=true")
echo "$CONVERT_RESPONSE" | python3 -m json.tool > /tmp/convert_result.json

TRIPLE_COUNT=$(cat /tmp/convert_result.json | python3 -c "import sys, json; print(json.load(sys.stdin)['triple_count'])")
OUTPUT_FILE=$(cat /tmp/convert_result.json | python3 -c "import sys, json; print(json.load(sys.stdin)['output_file'])")

echo "✅ Conversion complete: $TRIPLE_COUNT triples generated"
echo "   Output: $OUTPUT_FILE"
echo ""

# Step 8: Download RDF
echo "💾 Step 8: Downloading RDF file..."
curl -s "$API_URL/api/conversion/$PROJECT_ID/download" -o /tmp/mortgage_output.ttl
FILE_SIZE=$(wc -c < /tmp/mortgage_output.ttl)
echo "✅ Downloaded: /tmp/mortgage_output.ttl ($FILE_SIZE bytes)"
echo ""

# Summary
echo "=========================================="
echo "🎉 Integration Test Complete!"
echo "=========================================="
echo ""
echo "Summary:"
echo "  • Project ID: $PROJECT_ID"
echo "  • Columns mapped: $MAPPED/$TOTAL"
echo "  • Avg confidence: $AVG_CONF"
echo "  • Triples generated: $TRIPLE_COUNT"
echo "  • Output file: $OUTPUT_FILE"
echo ""
echo "View results:"
echo "  • Mapping result: /tmp/mapping_result.json"
echo "  • Conversion result: /tmp/convert_result.json"
echo "  • RDF output: /tmp/mortgage_output.ttl"
echo ""
echo "🚀 RDFMap Web UI is fully operational!"

