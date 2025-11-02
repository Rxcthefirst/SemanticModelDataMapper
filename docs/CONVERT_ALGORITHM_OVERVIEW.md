# Algorithm Overview for Business Stakeholders

## Executive Summary

This application converts tabular data (spreadsheets) into **RDF (Resource Description Framework)** triples—a standardized format for representing knowledge graphs and semantic data. The conversion is driven by a configuration file that maps spreadsheet columns to ontology concepts, ensuring the output data is semantically rich and aligned with domain-specific knowledge models.

---

## What Problem Does This Solve?

Organizations often have valuable data locked in spreadsheets (CSV/Excel files) that needs to be:
- **Integrated** with other data sources
- **Semantically enriched** with meaning and relationships
- **Validated** against business rules and data quality standards
- **Published** in standard formats for knowledge graphs and linked data applications

This tool automates that transformation while ensuring data quality and semantic correctness.

---

## High-Level Process Flow

```
┌─────────────────┐
│   Spreadsheet   │
│  (CSV/XLSX)     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Mapping Config  │◄──────┐
│   (YAML/JSON)   │       │ Business defines
└────────┬────────┘       │ how data maps to
         │                │ domain concepts
         ▼                │
┌─────────────────┐       │
│  Data Parser    │       │
│  & Transformer  │       │
└────────┬────────┘       │
         │                │
         ▼                │
┌─────────────────┐       │
│  RDF Generator  │       │
│   (Triples)     │       │
└────────┬────────┘       │
         │                │
         ▼                │
┌─────────────────┐       │
│   Validators    │       │
│ (SHACL/Ontology)│◄──────┘
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  RDF Output     │
│ (Multiple       │
│  Formats)       │
└─────────────────┘
```

---

## Step-by-Step Algorithm

### Step 1: Load and Parse Spreadsheet Data

**What Happens:**
- The application reads CSV or Excel files using the **pandas** library (industry-standard data processing tool)
- Each row becomes a record to process
- Column headers are identified and mapped

**Business Value:**
- Handles both CSV and Excel formats automatically
- Supports large datasets (tested with 100,000+ rows)
- Detects and reports data quality issues early

---

### Step 2: Load Mapping Configuration

**What Happens:**
- Reads a YAML or JSON configuration file that defines:
  - Which spreadsheet columns map to which ontology properties
  - How to generate unique identifiers (IRIs) for each entity
  - Data transformations (e.g., date formatting, data type conversions)
  - Validation rules

**Configuration Validation:**
- ✅ Ensures all namespace prefixes are declared
- ✅ Checks for required fields in IRI templates
- ✅ Validates data type specifications

**Business Value:**
- Non-technical users can modify mappings without changing code
- Configuration is reusable across similar datasets
- Built-in validation prevents common mistakes

**Example:**
```yaml
resources:
  Loan:
    iri_template: "loan:{LoanID}"
    class: "ex:MortgageLoan"
    properties:
      - column: "Principal"
        predicate: "ex:principalAmount"
        datatype: "xsd:decimal"
```

---

### Step 3: Load Ontology (Optional but Recommended)

**What Happens:**
- Loads the domain ontology that defines:
  - Valid classes (e.g., "MortgageLoan", "Property")
  - Valid properties (e.g., "principalAmount", "interestRate")
  - Relationships between concepts
  - Data constraints

**Format Support:**
The application uses **RDFLib**, a mature Python library that automatically detects and handles multiple ontology formats:
- **Turtle (.ttl)** - Human-readable RDF format
- **RDF/XML (.rdf)** - XML-based RDF format
- **JSON-LD (.jsonld)** - JSON-based linked data format
- **N-Triples (.nt)** - Line-based RDF format
- **And 12+ more formats**

**Business Value:**
- Ensures data conforms to organizational knowledge models
- Catches errors like typos in property names
- Supports any standard ontology format without configuration

---

### Step 4: Transform and Generate RDF Triples

**What Happens:**
For each row in the spreadsheet:

1. **Generate Unique Identifiers (IRIs)**
   - Creates a unique identifier for the entity using the IRI template
   - Example: `loan:LOAN001` for a loan with ID "LOAN001"
   - Detects and warns about duplicate identifiers

2. **Apply Data Transformations**
   - Converts data types (strings to numbers, dates, etc.)
   - Formats dates and times correctly
   - Handles null/missing values
   - Pre-validates data types before creating RDF literals

3. **Create RDF Triples**
   - Each triple has three parts:
     - **Subject**: The entity (e.g., `loan:LOAN001`)
     - **Predicate**: The property (e.g., `ex:principalAmount`)
     - **Object**: The value (e.g., `350000.00`)
   - Uses **RDFLib** to create standardized RDF structures

**Supported Transformations:**
- ✅ Date/time parsing and formatting
- ✅ Numeric type conversion (integers, decimals)
- ✅ Boolean value normalization
- ✅ String cleaning and formatting
- ✅ Currency and percentage handling
- ✅ Custom transformation functions

**Built-in Quality Checks:**
- ✅ **Duplicate IRI Detection**: Warns if multiple rows generate the same identifier
- ✅ **Datatype Validation**: Ensures values match their declared types (e.g., numbers are valid numbers)
- ✅ **Required Field Validation**: Warns if IRI templates use optional fields
- ✅ **Namespace Validation**: Ensures all prefixes are properly declared

**Business Value:**
- Automatic data quality monitoring
- Detailed error reporting with row numbers
- Configurable error handling (fail-fast or continue with warnings)

---

### Step 5: Validation Layers

The application provides **six layers of validation** to ensure data quality:

#### Layer 1: Configuration Validation (Pre-flight)
- Validates namespace prefixes are declared
- Checks for required fields in IRI templates
- **When**: Before processing any data
- **Benefit**: Catches configuration errors early

#### Layer 2: Datatype Validation (During Processing)
- Validates XSD datatypes (11 types supported):
  - `xsd:integer`, `xsd:decimal`, `xsd:float`, `xsd:double`
  - `xsd:date`, `xsd:dateTime`, `xsd:time`
  - `xsd:boolean`, `xsd:anyURI`, `xsd:string`
- **When**: Before creating each RDF literal
- **Benefit**: Ensures data type correctness

#### Layer 3: Duplicate IRI Detection (During Processing)
- Tracks all generated IRIs
- Reports when multiple rows create the same identifier
- **When**: During IRI generation
- **Benefit**: Prevents data collisions and ambiguity

#### Layer 4: Ontology Validation (Post-processing)
- Checks if all properties exist in the ontology
- Checks if all classes exist in the ontology
- **When**: After RDF generation (if `--ontology` specified)
- **Benefit**: Catches typos and ensures semantic correctness

#### Layer 5: SHACL Validation (Post-processing)
- Validates business rules and constraints
- Examples:
  - Required properties
  - Value ranges (min/max)
  - Data patterns (regex)
  - Cardinality constraints (min/max count)
- **When**: After RDF generation (if `--validate` flag used)
- **Benefit**: Enforces business rules and data quality standards

#### Layer 6: Processing Errors
- Captures transformation failures
- Reports row-level errors
- **When**: During data processing
- **Benefit**: Identifies problematic data with specific row numbers

**Business Value:**
- Comprehensive data quality assurance
- Early detection of issues
- Detailed reporting for troubleshooting
- Configurable validation levels

---

### Step 6: Generate Output

**What Happens:**
- Serializes the RDF graph to the desired format
- Uses **RDFLib** for format conversion
- Writes to specified output file(s)

**Supported Output Formats:**
The application leverages **RDFLib's built-in serializers**, providing out-of-the-box support for:
- **Turtle (ttl)** - Human-readable, compact format
- **RDF/XML (xml)** - XML-based, widely compatible
- **JSON-LD (jsonld)** - JSON-based, web-friendly
- **N-Triples (nt)** - Simple line-based format
- **N-Quads (nq)** - N-Triples with graph support
- **TriG (trig)** - Turtle with graph support
- **And more...**

**Business Value:**
- No format conversion tools needed
- Standards-compliant output
- Compatible with any RDF-consuming system
- Same data, multiple formats with one command

---

## Technology Components

### Core Libraries (Industry Standards)

1. **RDFLib** (v7.3.0)
   - Industry-standard Python library for RDF
   - **14+ years of development**, actively maintained
   - Used by major organizations and research institutions
   - Provides:
     - Automatic format detection for ontology files
     - Built-in support for 16+ RDF formats
     - Standards-compliant RDF generation
     - Graph operations and querying

2. **pandas** (v2.3.3)
   - De facto standard for data processing in Python
   - Used by millions of data professionals worldwide
   - Handles both CSV and Excel formats
   - Optimized for large datasets

3. **pySHACL** (v0.30.1)
   - Standard SHACL (Shapes Constraint Language) validator
   - W3C specification compliant
   - Used for business rule validation

4. **Pydantic** (v2.12.3)
   - Modern data validation library
   - Type-safe configuration handling
   - Runtime validation of configuration data structures

**Business Value:**
- Battle-tested, production-ready components
- Active community support
- Regular security and feature updates
- Standards compliance

---

## Performance Characteristics

### Scalability
- **Small datasets** (< 1,000 rows): Sub-second processing
- **Medium datasets** (1,000 - 10,000 rows): Seconds
- **Large datasets** (10,000 - 100,000 rows): Minutes
- **Memory efficient**: Processes data in chunks

### Reliability
- Comprehensive error handling
- Detailed error reporting with row numbers
- Configurable error handling (fail-fast or continue)
- Transaction-like processing (all or nothing)

---

## Business Benefits Summary

### 1. Automation
- Eliminates manual data transformation
- Reduces human error
- Saves time and resources

### 2. Quality Assurance
- Six layers of validation
- Automated quality checks
- Detailed error reporting

### 3. Flexibility
- Configuration-driven (no code changes needed)
- Supports multiple input formats (CSV, Excel)
- Supports multiple output formats (16+ RDF formats)
- Reusable configurations

### 4. Standards Compliance
- Uses W3C standards (RDF, OWL, SHACL)
- Compatible with any RDF-consuming system
- Future-proof data representation

### 5. Transparency
- Clear audit trail
- Detailed validation reports
- Row-level error tracking

### 6. Maintainability
- Built on industry-standard libraries
- Modular architecture
- Well-documented
- Comprehensive test coverage

---

## Real-World Use Cases

### Financial Services
- Convert loan data to semantic format
- Integrate with risk analysis systems
- Ensure regulatory compliance

### Healthcare
- Transform patient records to FHIR RDF
- Link clinical data with research ontologies
- Support interoperability

### Supply Chain
- Convert inventory data to linked data
- Integrate with supplier systems
- Track product provenance

### Government
- Transform public datasets to open data formats
- Enable data federation
- Support transparency initiatives

---

## Getting Started

### Simple Three-Step Process

1. **Prepare your spreadsheet** (CSV or Excel)
2. **Create a mapping configuration** (YAML or JSON)
3. **Run the conversion**:
   ```bash
   rdfmap convert \
     --mapping config.yaml \
     --ontology ontology.ttl \
     --format ttl \
     --output output.ttl \
     --validate
   ```

### Example Output

Input (CSV):
```
LoanID,Principal,InterestRate
LOAN001,350000,3.5
```

Output (RDF Triples):
```turtle
loan:LOAN001 a ex:MortgageLoan ;
    ex:principalAmount "350000.00"^^xsd:decimal ;
    ex:interestRate "3.5"^^xsd:decimal .
```

---

## Summary

This application provides a **robust, scalable, and standards-compliant** solution for converting tabular data to semantic RDF format. By leveraging industry-standard libraries like **RDFLib** and **pandas**, it offers:

- ✅ **Automatic format detection** for ontologies (no configuration needed)
- ✅ **Out-of-the-box support** for 16+ RDF formats
- ✅ **Six layers of validation** for comprehensive data quality
- ✅ **Configuration-driven** approach for business flexibility
- ✅ **Production-ready** components with proven track records

The result is high-quality, semantically-enriched data that can be integrated into knowledge graphs, linked data platforms, and semantic web applications.

---

## Next Steps

1. **Review the Quick Start Guide**: `QUICKSTART.md`
2. **Explore the Mortgage Example**: `examples/mortgage/README.md`
3. **Understand Validation Features**: `docs/VALIDATION_GUARDRAILS.md`
4. **Learn Configuration Options**: `README.md` (Configuration Reference section)

For technical details, see `DEVELOPMENT.md` and `WALKTHROUGH.md`.
