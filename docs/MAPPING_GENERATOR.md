# Mapping Generator Feature

## Overview

The **Mapping Generator** feature automates the creation of mapping configuration files by analyzing your ontology and spreadsheet data. This significantly reduces the manual work required to create mappings and helps ensure they are semantically correct.

## Key Features

### 1. **Ontology Analysis**
- Extracts classes and properties from OWL/RDFS ontologies
- Supports any RDFLib-compatible format (TTL, RDF/XML, JSON-LD, etc.)
- Identifies datatype properties vs. object properties
- Captures labels, comments, domains, and ranges
- **🆕 Extracts SKOS labels** (prefLabel, altLabel, hiddenLabel) for advanced matching
- Extracts namespace declarations

### 2. **Spreadsheet Analysis**
- Analyzes column data types and patterns
- Detects identifier columns (for IRI generation)
- Calculates null percentages and required fields
- Suggests appropriate XSD datatypes
- Identifies unique columns

### 3. **Intelligent Matching with SKOS Support**
- Maps columns to ontology properties by name similarity
- **🆕 Leverages SKOS labels for flexible matching:**
  - Handles abbreviations (e.g., `EMP_ID` → `employeeId` via hiddenLabel)
  - Matches synonyms (e.g., `Surname` → `lastName` via altLabel)
  - Supports business terminology variations
- Priority-based matching (prefLabel > rdfs:label > altLabel > hiddenLabel > local name)
- Suggests IRI templates based on identifier columns
- Auto-detects linked objects and relationships

### 4. **JSON Schema Export**
- Generates JSON Schema from Pydantic models
- **Can be used to validate mapping configurations**
- Useful for CI/CD pipelines and IDE autocomplete
- Documents the mapping configuration structure

---

## How It Works

```
┌──────────────┐          ┌──────────────┐
│   Ontology   │          │  Spreadsheet │
│ (TTL/RDF/...) │          │  (CSV/XLSX)  │
└───────┬──────┘          └───────┬──────┘
        │                         │
        │                         │
        ▼                         ▼
┌──────────────┐          ┌──────────────┐
│  Ontology    │          │ Spreadsheet  │
│  Analyzer    │          │  Analyzer    │
└───────┬──────┘          └───────┬──────┘
        │                         │
        │  ┌─────────────────┐   │
        └──► Mapping        ◄───┘
           │  Generator      │
           └────────┬────────┘
                    │
                    ▼
           ┌────────────────┐
           │ Generated      │
           │ Mapping Config │
           │ (YAML/JSON)    │
           └────────────────┘
```

### Step 1: Ontology Analysis

The `OntologyAnalyzer` loads the ontology and extracts:

```python
from rdfmap.generator import OntologyAnalyzer

analyzer = OntologyAnalyzer("ontology.ttl")

# Results:
# - analyzer.classes: All OWL/RDFS classes
# - analyzer.properties: All properties with domains/ranges
# - analyzer.get_namespaces(): Namespace prefixes
```

**What it extracts:**
- Class URIs, labels, and comments
- Property URIs, labels, comments, domains, and ranges
- Distinction between datatype and object properties
- Namespace prefixes

### Step 2: Spreadsheet Analysis

The `SpreadsheetAnalyzer` examines the data and infers:

```python
from rdfmap.generator import SpreadsheetAnalyzer

analyzer = SpreadsheetAnalyzer("data.csv")

# Results:
# - analyzer.columns: Analysis for each column
# - Column data types, nulls, uniqueness
# - Suggested XSD datatypes
# - Identifier columns for IRI generation
```

**What it detects:**
- Python data types (integer, float, string, date, datetime, boolean)
- XSD datatype suggestions based on content and column names
- Identifier columns (unique, ID-like names)
- Required vs. optional fields (based on null percentage)
- Patterns (numeric strings, codes, emails, URIs)

### Step 3: Intelligent Mapping

The `MappingGenerator` combines both analyses:

```python
from rdfmap.generator import MappingGenerator, GeneratorConfig

config = GeneratorConfig(
    base_iri="http://example.org/",
    include_comments=True,
    auto_detect_relationships=True,
)

generator = MappingGenerator(
    ontology_file="ontology.ttl",
    spreadsheet_file="data.csv",
    config=config,
)

# Generate mapping
mapping = generator.generate(target_class="MortgageLoan")

# Save as YAML
generator.save_yaml("mapping.yaml")
```

**Matching algorithm:**
1. **Exact label match**: Column name == property label
2. **URI local name match**: Column name == property URI fragment
3. **Partial match**: Column name contains property label or vice versa
4. **Case-insensitive**: All matches ignore case and underscores

**IRI template generation:**
- Uses identifier columns detected in spreadsheet
- Falls back to first column if no identifiers found
- Formats as: `{class_name}:{column}`

---

## SKOS Label Matching

### Overview

The generator leverages **SKOS (Simple Knowledge Organization System)** labels to handle real-world scenarios where column names don't match ontology property labels exactly. This is essential for:

- **Abbreviations**: `EMP_ID` → `employeeId`
- **Synonyms**: `Surname` → `lastName`  
- **Business terminology**: `Compensation` → `salary`
- **Database conventions**: `hire_dt` → `hireDate`

### SKOS Vocabulary Support

The generator extracts and uses these SKOS properties:

| SKOS Property | Purpose | Example |
|---------------|---------|---------|
| `skos:prefLabel` | Preferred display label | "Employee ID" |
| `skos:altLabel` | Alternative/synonym labels | "EmpID", "Staff Number" |
| `skos:hiddenLabel` | Hidden labels for matching | "EMP_ID", "emp_no", "staff_id" |

### Matching Priority

The generator follows a **priority order** when matching column names to properties:

1. **Exact match with SKOS prefLabel** - Highest priority
2. **Exact match with rdfs:label** - Standard RDF label
3. **Exact match with SKOS altLabel** - Alternative names
4. **Exact match with SKOS hiddenLabel** - Common abbreviations
5. **Exact match with local name** - Last part of URI
6. **Partial match with any label** - Fuzzy matching
7. **Fuzzy match with local name** - Most permissive

### Example Ontology with SKOS Labels

```turtle
@prefix : <http://example.org/hr#> .
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

:employeeId a owl:DatatypeProperty ;
    rdfs:label "employee identifier" ;
    skos:prefLabel "Employee ID" ;
    skos:altLabel "EmpID" ;
    skos:altLabel "Staff Number" ;
    skos:hiddenLabel "EMP_ID" ;      # Database column name
    skos:hiddenLabel "emp_no" ;      # Legacy system
    skos:hiddenLabel "staff_id" ;    # Alternative DB column
    rdfs:domain :Employee ;
    rdfs:range xsd:string .

:firstName a owl:DatatypeProperty ;
    rdfs:label "first name" ;
    skos:prefLabel "First Name" ;
    skos:altLabel "Given Name" ;
    skos:altLabel "Forename" ;
    skos:hiddenLabel "fname" ;       # Common abbreviation
    skos:hiddenLabel "first_nm" ;    # Database convention
    rdfs:domain :Employee ;
    rdfs:range xsd:string .

:salary a owl:DatatypeProperty ;
    rdfs:label "annual salary" ;
    skos:prefLabel "Annual Salary" ;
    skos:altLabel "Compensation" ;   # Business term
    skos:altLabel "Pay" ;            # Informal term
    skos:hiddenLabel "sal" ;         # Database column
    skos:hiddenLabel "annual_pay" ;
    rdfs:domain :Employee ;
    rdfs:range xsd:decimal .
```

### Example CSV with Challenging Column Names

```csv
EMP_ID,fname,lname,email_addr,phone,sal,hire_dt,active,dept_cd
E001,John,Smith,john@company.com,555-0101,75000,2020-01-15,Yes,ENG
E002,Jane,Doe,jane@company.com,555-0102,85000,2019-03-22,Yes,HR
```

### How Matching Works

| CSV Column | Matches Property | Via | Reasoning |
|------------|------------------|-----|-----------|
| `EMP_ID` | `:employeeId` | hiddenLabel | Exact match with hidden label |
| `fname` | `:firstName` | hiddenLabel | Common abbreviation |
| `lname` | `:lastName` | hiddenLabel | Common abbreviation |
| `email_addr` | `:emailAddress` | hiddenLabel | Database convention |
| `sal` | `:salary` | hiddenLabel | Business abbreviation |
| `hire_dt` | `:hireDate` | hiddenLabel | Date column convention |

### Benefits

✅ **Handles legacy systems** - Column names from old databases  
✅ **Supports abbreviations** - Common shorthand notation  
✅ **Business terminology** - Domain-specific synonyms  
✅ **No ontology changes required** - Add labels, keep URIs stable  
✅ **Better than fuzzy matching** - Explicit, controlled vocabulary  
✅ **Documentation built-in** - SKOS labels serve as docs

### When to Use SKOS Labels

**Use SKOS labels when:**
- Column names use abbreviations (e.g., `dept_cd`, `emp_no`)
- Legacy database column names don't match modern ontology
- Multiple synonyms exist in business domain
- Cross-organization data exchange (different naming conventions)
- International projects (translations via `skos:prefLabel` with language tags)

**Best Practices:**
1. Use `skos:prefLabel` for the canonical display name
2. Use `skos:altLabel` for business synonyms and variations
3. Use `skos:hiddenLabel` for technical abbreviations and legacy names
4. Keep `rdfs:label` for the formal semantic definition
5. Document rationale in `rdfs:comment`

### Testing SKOS Matching

See `tests/test_generator_workflow.py` for comprehensive test cases covering:
- SKOS label extraction from ontologies
- Priority-based matching
- Hidden label matching (abbreviations)
- Alternative label matching (synonyms)
- Full workflow with challenging column names

---

## CLI Usage

### Generate a Mapping

```bash
rdfmap generate \
  --ontology ontology.ttl \
  --spreadsheet data.csv \
  --output mapping.yaml \
  --base-iri http://example.org/ \
  --class MortgageLoan
```

**Options:**
- `--ontology, -ont`: Path to ontology file (required)
- `--spreadsheet, -s`: Path to CSV/XLSX file (required)
- `--output, -o`: Output path for mapping config (required)
- `--base-iri, -b`: Base IRI for resources (default: `http://example.org/`)
- `--class, -c`: Target ontology class (auto-detects if omitted)
- `--format, -f`: Output format: `yaml` or `json` (default: `yaml`)
- `--analyze-only`: Show analysis without generating mapping
- `--export-schema`: Export JSON Schema for validation
- `--verbose, -v`: Show detailed output

### Analyze Only (No Generation)

```bash
rdfmap generate \
  --ontology ontology.ttl \
  --spreadsheet data.csv \
  --output mapping.yaml \
  --analyze-only
```

This shows:
- Number of classes and properties in ontology
- Column data types and suggestions
- Identifier columns
- Properties available for the target class

### Export JSON Schema

```bash
rdfmap generate \
  --ontology ontology.ttl \
  --spreadsheet data.csv \
  --output mapping.yaml \
  --export-schema
```

This generates two files:
- `mapping.yaml`: The mapping configuration
- `mapping_schema.json`: JSON Schema for validation

---

## Using JSON Schema for Validation

### What is JSON Schema?

JSON Schema is a vocabulary for validating JSON/YAML documents. It describes:
- Required vs. optional fields
- Data types for each field
- Allowed values and patterns
- Nested structure

### How We Use It

The `MappingGenerator.get_json_schema()` method exports the Pydantic model as JSON Schema:

```python
from rdfmap.generator import MappingGenerator
from rdfmap.models.mapping import MappingConfig

# Generate from Pydantic model
schema = MappingConfig.model_json_schema()

# Or from generator
generator = MappingGenerator(...)
schema = generator.get_json_schema()
```

### Validation Use Cases

#### 1. **Validate Generated Mappings** (Built-in)

Pydantic automatically validates when loading:

```python
from rdfmap.models.mapping import MappingConfig
import yaml

# Load mapping
with open("mapping.yaml") as f:
    data = yaml.safe_load(f)

# Validate
try:
    config = MappingConfig.model_validate(data)
    print("✓ Valid!")
except ValidationError as e:
    print(f"✗ Invalid: {e}")
```

#### 2. **External Validation** (using jsonschema library)

Install `jsonschema`:
```bash
pip install jsonschema
```

Validate:
```python
import json
import yaml
import jsonschema

# Load schema
with open("mapping_schema.json") as f:
    schema = json.load(f)

# Load mapping
with open("mapping.yaml") as f:
    mapping = yaml.safe_load(f)

# Validate
try:
    jsonschema.validate(mapping, schema)
    print("✓ Valid!")
except jsonschema.ValidationError as e:
    print(f"✗ Invalid: {e.message}")
```

#### 3. **CI/CD Pipeline Validation**

```yaml
# .github/workflows/validate-mappings.yml
name: Validate Mappings

on: [push, pull_request]

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      
      - name: Setup Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install jsonschema pyyaml
      
      - name: Validate all mappings
        run: |
          python scripts/validate_all_mappings.py
```

Script (`scripts/validate_all_mappings.py`):
```python
import json
import yaml
import jsonschema
from pathlib import Path

# Load schema
with open("mapping_schema.json") as f:
    schema = json.load(f)

# Validate all mapping files
errors = []
for mapping_file in Path("configs").glob("*.yaml"):
    with open(mapping_file) as f:
        mapping = yaml.safe_load(f)
    
    try:
        jsonschema.validate(mapping, schema)
        print(f"✓ {mapping_file.name}")
    except jsonschema.ValidationError as e:
        errors.append((mapping_file.name, str(e)))
        print(f"✗ {mapping_file.name}: {e.message}")

if errors:
    exit(1)
```

#### 4. **IDE Autocomplete** (VS Code)

Add to `.vscode/settings.json`:
```json
{
  "yaml.schemas": {
    "./mapping_schema.json": "configs/*.yaml"
  }
}
```

Now VS Code will provide:
- Autocomplete for field names
- Inline validation errors
- Hover documentation from descriptions

---

## Python API

### Basic Usage

```python
from rdfmap.generator import MappingGenerator, GeneratorConfig

# Configure generator
config = GeneratorConfig(
    base_iri="http://example.org/",
    include_comments=True,
    auto_detect_relationships=True,
    min_confidence=0.5,
)

# Create generator
generator = MappingGenerator(
    ontology_file="ontology.ttl",
    spreadsheet_file="data.csv",
    config=config,
)

# Generate mapping
mapping = generator.generate(target_class="MortgageLoan")

# Save
generator.save_yaml("mapping.yaml")

# Or get as dict
mapping_dict = generator.mapping
```

### Advanced: Standalone Analyzers

#### Ontology Analysis

```python
from rdfmap.generator import OntologyAnalyzer

analyzer = OntologyAnalyzer("ontology.ttl")

# Get all classes
for cls in analyzer.classes.values():
    print(f"Class: {cls.label} ({cls.uri})")
    print(f"  Comment: {cls.comment}")
    print(f"  Properties: {len(cls.properties)}")

# Get properties for a class
props = analyzer.get_properties_for_class(class_uri)

# Suggest classes based on name
suggestions = analyzer.suggest_class_for_name("loan")

# Get namespaces
namespaces = analyzer.get_namespaces()
```

#### Spreadsheet Analysis

```python
from rdfmap.generator import SpreadsheetAnalyzer

analyzer = SpreadsheetAnalyzer("data.csv", sample_size=100)

# Get column analysis
for col_name, analysis in analyzer.columns.items():
    print(f"Column: {col_name}")
    print(f"  Type: {analysis.inferred_type}")
    print(f"  Suggested XSD: {analysis.suggested_datatype}")
    print(f"  Null %: {analysis.null_percentage:.1f}%")
    print(f"  Unique: {analysis.is_unique}")
    print(f"  Required: {analysis.is_required}")
    print(f"  Identifier: {analysis.is_identifier}")

# Get identifier columns
id_cols = analyzer.get_identifier_columns()

# Get required columns
required_cols = analyzer.get_required_columns()

# Summary report
print(analyzer.summary())
```

---

## Configuration Options

### GeneratorConfig

```python
class GeneratorConfig(BaseModel):
    base_iri: str  # Base IRI for generated resources
    default_class_prefix: str = "resource"  # Prefix for resource IRIs
    include_comments: bool = True  # Include property comments
    auto_detect_relationships: bool = True  # Detect object properties
    min_confidence: float = 0.5  # Minimum match confidence (0-1)
```

---

## Generated Output Structure

### Example Generated Mapping

```yaml
namespaces:
  xsd: http://www.w3.org/2001/XMLSchema#
  ex: https://example.com/mortgage#
  # ... (extracted from ontology)

defaults:
  base_iri: http://example.org/mortgage/

sheets:
- name: loans
  source: data/loans.csv
  row_resource:
    class: ex:MortgageLoan
    iri_template: "mortgage_loan:{LoanID}"
  columns:
    Principal:
      as: ex:principalAmount
      datatype: xsd:decimal
      required: true
      _comment: "The original loan amount."
    InterestRate:
      as: ex:interestRate
      datatype: xsd:decimal
      required: true
      _comment: "The annual interest rate."
  objects:
    borrower:
      predicate: ex:hasBorrower
      class: ex:Borrower
      iri_template: "borrower:{BorrowerID}"
      properties:
      - column: BorrowerName
        as: ex:name

options:
  on_error: report
  skip_empty_values: true
```

### What Gets Generated

- **Namespaces**: Extracted from ontology + xsd
- **Defaults**: Uses provided base_iri
- **Row resource**: Target class + IRI template from ID columns
- **Column mappings**: Matched properties with datatypes and comments
- **Object mappings**: Detected relationships (if enabled)
- **Options**: Sensible defaults for processing

---

## Refinement Workflow

1. **Generate initial mapping**:
   ```bash
   rdfmap generate -ont ontology.ttl -s data.csv -o mapping.yaml
   ```

2. **Review the generated mapping**:
   - Check column-to-property matches
   - Verify IRI template uses appropriate columns
   - Review datatype suggestions
   - Check detected relationships

3. **Refine manually**:
   - Adjust property mappings if needed
   - Add transformations (e.g., `to_decimal`, `to_date`)
   - Add default values for optional fields
   - Configure multi-valued columns
   - Add language tags for string literals

4. **Validate**:
   ```bash
   python -c "from rdfmap.models.mapping import MappingConfig; import yaml; MappingConfig.model_validate(yaml.safe_load(open('mapping.yaml')))"
   ```

5. **Test with dry run**:
   ```bash
   rdfmap convert --mapping mapping.yaml --dry-run --verbose
   ```

6. **Run conversion**:
   ```bash
   rdfmap convert --mapping mapping.yaml -f ttl -o output.ttl --validate
   ```

---

## Benefits

### 1. **Time Savings**
- Reduces initial mapping creation from hours to minutes
- Automates tedious column-to-property matching
- Eliminates manual namespace copying

### 2. **Accuracy**
- Uses actual ontology structure (not guesswork)
- Suggests appropriate XSD datatypes based on data
- Detects identifier columns automatically

### 3. **Consistency**
- Follows ontology semantics
- Uses standard namespace prefixes
- Consistent IRI patterns

### 4. **Documentation**
- Includes comments from ontology
- JSON Schema documents the structure
- Clear audit trail from ontology to mapping

### 5. **Validation**
- JSON Schema ensures structural correctness
- Pydantic validates at runtime
- Early error detection

---

## Limitations

### Current Limitations

1. **Single sheet/file**: Currently generates for one sheet at a time
2. **Single class**: One target class per mapping (can be extended manually)
3. **Simple matching**: Uses name-based matching (no ML/NLP)
4. **No custom transforms**: Generated mappings use default transforms only
5. **Basic relationship detection**: Only detects direct object properties

### Workarounds

- **Multiple sheets**: Generate separately, then merge YAML files
- **Multiple classes**: Generate for each class, combine in one config
- **Complex matching**: Review and adjust matches manually
- **Custom transforms**: Add manually after generation
- **Complex relationships**: Define linked objects manually

---

## Examples

### Example 1: Simple Datatype Properties

**Ontology** (`ontology.ttl`):
```turtle
@prefix ex: <https://example.com/> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .

ex:Person a owl:Class ;
    rdfs:label "Person" .

ex:name a owl:DatatypeProperty ;
    rdfs:label "name" ;
    rdfs:domain ex:Person ;
    rdfs:range xsd:string .

ex:age a owl:DatatypeProperty ;
    rdfs:label "age" ;
    rdfs:domain ex:Person ;
    rdfs:range xsd:integer .
```

**Spreadsheet** (`people.csv`):
```csv
PersonID,Name,Age
P001,John Doe,30
P002,Jane Smith,25
```

**Generate**:
```bash
rdfmap generate \
  --ontology ontology.ttl \
  --spreadsheet people.csv \
  --output mapping.yaml \
  --class Person
```

**Result**: Automatically matches `Name` → `ex:name` and `Age` → `ex:age`

### Example 2: With Relationships

**Ontology**:
```turtle
ex:Company a owl:Class .
ex:Employee a owl:Class .

ex:employs a owl:ObjectProperty ;
    rdfs:domain ex:Company ;
    rdfs:range ex:Employee .

ex:employeeName a owl:DatatypeProperty ;
    rdfs:domain ex:Employee .
```

**Spreadsheet** (`companies.csv`):
```csv
CompanyID,CompanyName,EmployeeID,EmployeeName
C001,Acme Corp,E001,John Doe
C001,Acme Corp,E002,Jane Smith
```

**Generate**:
```bash
rdfmap generate \
  --ontology ontology.ttl \
  --spreadsheet companies.csv \
  --output mapping.yaml \
  --class Company
```

**Result**: Auto-detects `Employee` as linked object via `ex:employs`

---

## See Also

- [README.md](../README.md) - Main documentation
- [QUICKSTART.md](../QUICKSTART.md) - Getting started guide
- [VALIDATION_GUARDRAILS.md](./VALIDATION_GUARDRAILS.md) - Validation features
- [ALGORITHM_OVERVIEW.md](../ALGORITHM_OVERVIEW.md) - For business stakeholders
