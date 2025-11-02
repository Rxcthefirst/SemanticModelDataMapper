# Semantic Alignment Strategy: Closing the Gap Between Data and Ontology

## Executive Summary

**The Problem**: Column headers in spreadsheets rarely match ontology property labels perfectly. Current fuzzy matching has limitations.

**The Solution**: A **feedback-driven semantic alignment system** that:
1. Detects alignment gaps during generation
2. Reports unmapped columns with suggestions
3. Guides users to enrich ontologies with SKOS labels
4. Creates a virtuous cycle of continuous improvement

**The Vision**: Transform data mapping from a one-time struggle into an **iterative learning process** where the system gets smarter with each dataset.

---

## W3C Standards Arsenal

### 1. **SKOS (Simple Knowledge Organization System)** ⭐ Primary

**What it is**: W3C standard for representing knowledge organization systems (taxonomies, thesauri, classification schemes).

**Key Properties for Our Use:**

| Property | Purpose | Use Case |
|----------|---------|----------|
| `skos:prefLabel` | Preferred label | Canonical display name |
| `skos:altLabel` | Alternative labels | Synonyms, business terms |
| `skos:hiddenLabel` | Hidden search labels | Abbreviations, misspellings, legacy names |
| `skos:definition` | Formal definition | Help users understand meaning |
| `skos:example` | Usage examples | Show typical values |
| `skos:scopeNote` | Usage guidance | When to use this property |
| `skos:changeNote` | Change history | Track why labels were added |
| `skos:editorialNote` | Editorial notes | Document gaps or issues |

**Why SKOS is Perfect:**
- ✅ Designed for **controlled vocabularies** (exactly our use case)
- ✅ Explicit separation of display labels vs. search terms
- ✅ `hiddenLabel` is **made for abbreviations and variants**
- ✅ Built-in documentation properties
- ✅ Wide tool support (Protégé, TopBraid, etc.)

### 2. **RDFS (RDF Schema)** - Foundation

**What it adds:**

| Property | Purpose | Use Case |
|----------|---------|----------|
| `rdfs:label` | Human-readable label | Formal semantic label |
| `rdfs:comment` | Description | Explain property meaning |
| `rdfs:seeAlso` | Related resources | Link to documentation |
| `rdfs:isDefinedBy` | Defining resource | Ontology provenance |

### 3. **Dublin Core Terms** - Metadata

**What it adds:**

| Property | Purpose | Use Case |
|----------|---------|----------|
| `dcterms:created` | Creation date | Track when labels added |
| `dcterms:modified` | Modification date | Track alignment evolution |
| `dcterms:creator` | Creator | Who added the label |
| `dcterms:source` | Source reference | Document where term came from |

### 4. **PROV-O (Provenance Ontology)** - Change Tracking

**What it adds:**

| Property | Purpose | Use Case |
|----------|---------|----------|
| `prov:wasGeneratedBy` | Generation activity | Track automated suggestions |
| `prov:wasAttributedTo` | Attribution | Who approved alignment |
| `prov:generatedAtTime` | Timestamp | When alignment was created |
| `prov:wasDerivedFrom` | Derivation | Track from data column to property |

### 5. **SHACL (Shapes Constraint Language)** - Validation

**What it adds:**

| Feature | Purpose | Use Case |
|---------|---------|----------|
| `sh:message` | Custom error messages | Guide users on missing labels |
| `sh:severity` | Violation severity | Warning vs. error |
| `sh:result` | Validation result | Report alignment gaps |

### 6. **OWL (Web Ontology Language)** - Annotations

**What it adds:**

| Property | Purpose | Use Case |
|----------|---------|----------|
| `owl:deprecated` | Deprecation flag | Mark old column names |
| `owl:versionInfo` | Version info | Track ontology versions |

---

## Proposed Architecture: The Alignment Feedback Loop

```
┌─────────────────────────────────────────────────────────────────┐
│                     DATA MAPPING WORKFLOW                        │
└─────────────────────────────────────────────────────────────────┘

┌─────────────┐
│ Spreadsheet │
│   (CSV)     │
└──────┬──────┘
       │
       ▼
┌──────────────────────────────────────────────────────────────┐
│  STEP 1: Generate Mapping with Alignment Report              │
│                                                               │
│  $ rdfmap generate --ontology onto.ttl --spreadsheet data.csv│
│                     --output mapping.yaml                     │
│                     --alignment-report gaps.json              │
└──────┬───────────────────────────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────────────────────────┐
│  ALIGNMENT REPORT (gaps.json)                                │
│                                                               │
│  {                                                            │
│    "unmapped_columns": [                                      │
│      {                                                        │
│        "column": "emp_num",                                   │
│        "suggested_properties": [                              │
│          {                                                    │
│            "property": "ex:employeeId",                       │
│            "confidence": 0.65,                                │
│            "reason": "Partial match: 'emp' in 'employee'",   │
│            "suggested_label": "skos:hiddenLabel 'emp_num'"   │
│          }                                                    │
│        ],                                                     │
│        "sample_values": ["E001", "E002", "E003"],            │
│        "data_type": "string",                                 │
│        "null_percentage": 0.0,                                │
│        "is_unique": true                                      │
│      }                                                        │
│    ],                                                         │
│    "weak_matches": [ /* columns matched but low confidence */ ],│
│    "suggested_skos_additions": { /* ready-to-add RDF */ }   │
│  }                                                            │
└──────┬───────────────────────────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────────────────────────┐
│  STEP 2: Review Report (Human Decision)                      │
│                                                               │
│  Data Engineer + Ontologist review:                           │
│  - Which unmapped columns are legitimate?                     │
│  - Which suggestions are correct?                             │
│  - What business context is needed?                           │
└──────┬───────────────────────────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────────────────────────┐
│  STEP 3: Enrich Ontology (Semi-Automated)                    │
│                                                               │
│  $ rdfmap ontology enrich                                     │
│      --ontology onto.ttl                                      │
│      --alignment-report gaps.json                             │
│      --interactive                                            │
│                                                               │
│  Interactive prompts:                                         │
│  > Add 'emp_num' as hiddenLabel to ex:employeeId? [Y/n]      │
│  > Add business definition? [optional]                        │
│  > Add example values? [optional]                             │
│                                                               │
│  Generates: onto_enriched.ttl with provenance                 │
└──────┬───────────────────────────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────────────────────────┐
│  STEP 4: Re-generate with Enriched Ontology                  │
│                                                               │
│  $ rdfmap generate --ontology onto_enriched.ttl ...           │
│                                                               │
│  Result: Better mappings, fewer gaps!                         │
└──────┬───────────────────────────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────────────────────────┐
│  STEP 5: Track Improvements Over Time                         │
│                                                               │
│  $ rdfmap alignment-stats --report-dir reports/               │
│                                                               │
│  Shows:                                                       │
│  - Mapping success rate over time                             │
│  - Most problematic columns                                   │
│  - Ontology coverage improvements                             │
└───────────────────────────────────────────────────────────────┘
```

---

## Alignment Report Structure

### JSON Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "Semantic Alignment Report",
  "type": "object",
  "properties": {
    "metadata": {
      "type": "object",
      "properties": {
        "generated_at": {"type": "string", "format": "date-time"},
        "ontology_file": {"type": "string"},
        "spreadsheet_file": {"type": "string"},
        "total_columns": {"type": "integer"},
        "mapped_columns": {"type": "integer"},
        "unmapped_columns": {"type": "integer"},
        "mapping_success_rate": {"type": "number"}
      }
    },
    "unmapped_columns": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "column": {"type": "string"},
          "sample_values": {"type": "array"},
          "data_type": {"type": "string"},
          "null_percentage": {"type": "number"},
          "is_unique": {"type": "boolean"},
          "cardinality": {"type": "integer"},
          "suggested_properties": {
            "type": "array",
            "items": {
              "type": "object",
              "properties": {
                "property_uri": {"type": "string"},
                "property_label": {"type": "string"},
                "confidence": {"type": "number"},
                "match_reason": {"type": "string"},
                "suggested_skos_addition": {
                  "type": "object",
                  "properties": {
                    "label_type": {"enum": ["prefLabel", "altLabel", "hiddenLabel"]},
                    "label_value": {"type": "string"},
                    "rationale": {"type": "string"}
                  }
                }
              }
            }
          }
        }
      }
    },
    "weak_matches": {
      "type": "array",
      "description": "Columns that were mapped but with low confidence",
      "items": {
        "type": "object",
        "properties": {
          "column": {"type": "string"},
          "mapped_to": {"type": "string"},
          "confidence": {"type": "number"},
          "recommendation": {"type": "string"}
        }
      }
    },
    "ontology_coverage": {
      "type": "object",
      "properties": {
        "classes": {
          "type": "array",
          "items": {
            "type": "object",
            "properties": {
              "class_uri": {"type": "string"},
              "class_label": {"type": "string"},
              "properties_with_skos": {"type": "integer"},
              "properties_without_skos": {"type": "integer"},
              "skos_coverage_percentage": {"type": "number"}
            }
          }
        }
      }
    },
    "suggested_skos_enrichment": {
      "type": "object",
      "description": "Ready-to-add SKOS triples in Turtle format",
      "properties": {
        "turtle": {"type": "string"},
        "triples_count": {"type": "integer"}
      }
    }
  }
}
```

### Example Report

```json
{
  "metadata": {
    "generated_at": "2025-11-01T10:30:00Z",
    "ontology_file": "hr_ontology.ttl",
    "spreadsheet_file": "employees.csv",
    "total_columns": 12,
    "mapped_columns": 9,
    "unmapped_columns": 3,
    "mapping_success_rate": 0.75
  },
  "unmapped_columns": [
    {
      "column": "emp_num",
      "sample_values": ["E001", "E002", "E003", "E004", "E005"],
      "data_type": "string",
      "null_percentage": 0.0,
      "is_unique": true,
      "cardinality": 1000,
      "suggested_properties": [
        {
          "property_uri": "http://example.org/hr#employeeId",
          "property_label": "employee identifier",
          "confidence": 0.72,
          "match_reason": "Partial match: 'emp' matches 'employee', unique identifier pattern",
          "suggested_skos_addition": {
            "label_type": "hiddenLabel",
            "label_value": "emp_num",
            "rationale": "Common abbreviation in legacy HR systems"
          }
        },
        {
          "property_uri": "http://example.org/hr#staffNumber",
          "property_label": "staff number",
          "confidence": 0.45,
          "match_reason": "Both are unique identifiers",
          "suggested_skos_addition": null
        }
      ]
    },
    {
      "column": "mgr",
      "sample_values": ["E005", "E003", null, "E007", "E002"],
      "data_type": "string",
      "null_percentage": 0.15,
      "is_unique": false,
      "cardinality": 50,
      "suggested_properties": [
        {
          "property_uri": "http://example.org/hr#reportsTo",
          "property_label": "reports to",
          "confidence": 0.85,
          "match_reason": "Ontology has altLabel 'Manager', high confidence match",
          "suggested_skos_addition": {
            "label_type": "hiddenLabel",
            "label_value": "mgr",
            "rationale": "Standard abbreviation for manager in databases"
          }
        }
      ]
    },
    {
      "column": "compensation_bucket",
      "sample_values": ["L1", "L2", "L3", "L4", "L5"],
      "data_type": "string",
      "null_percentage": 0.0,
      "is_unique": false,
      "cardinality": 5,
      "suggested_properties": [
        {
          "property_uri": "http://example.org/hr#salaryBand",
          "property_label": "salary band",
          "confidence": 0.55,
          "match_reason": "Semantic similarity: compensation relates to salary",
          "suggested_skos_addition": {
            "label_type": "altLabel",
            "label_value": "Compensation Bucket",
            "rationale": "Business terminology used in HR department"
          }
        }
      ]
    }
  ],
  "weak_matches": [
    {
      "column": "hire_date",
      "mapped_to": "http://example.org/hr#hireDate",
      "confidence": 0.62,
      "recommendation": "Consider adding 'hire_date' as skos:hiddenLabel to improve confidence"
    }
  ],
  "ontology_coverage": {
    "classes": [
      {
        "class_uri": "http://example.org/hr#Employee",
        "class_label": "Employee",
        "properties_with_skos": 8,
        "properties_without_skos": 5,
        "skos_coverage_percentage": 0.615
      }
    ]
  },
  "suggested_skos_enrichment": {
    "turtle": "@prefix : <http://example.org/hr#> .\n@prefix skos: <http://www.w3.org/2004/02/skos/core#> .\n\n:employeeId skos:hiddenLabel \"emp_num\"@en .\n:reportsTo skos:hiddenLabel \"mgr\"@en .\n:salaryBand skos:altLabel \"Compensation Bucket\"@en .\n",
    "triples_count": 3
  }
}
```

---

## Implementation: New CLI Commands

### 1. Generate with Alignment Report

```bash
rdfmap generate \
  --ontology hr.ttl \
  --spreadsheet employees.csv \
  --output mapping.yaml \
  --alignment-report alignment_report.json \
  --min-confidence 0.6 \
  --verbose
```

**Output:**
```
✓ Analyzed ontology: 15 classes, 87 properties
✓ Analyzed spreadsheet: 12 columns, 1000 rows
✓ Generated mapping: 9/12 columns mapped (75% success rate)

⚠ Alignment Issues:
  - 3 unmapped columns
  - 1 weak match (confidence < 0.6)

See alignment_report.json for details and suggestions.
Tip: Run 'rdfmap ontology enrich' to improve alignment.
```

### 2. Interactive Ontology Enrichment

```bash
rdfmap ontology enrich \
  --ontology hr.ttl \
  --alignment-report alignment_report.json \
  --output hr_enriched.ttl \
  --interactive
```

**Interactive Session:**
```
Semantic Alignment Enrichment Wizard
=====================================

Found 3 suggested SKOS additions:

[1/3] Column: emp_num
  Suggested property: ex:employeeId (confidence: 0.72)
  Sample values: E001, E002, E003, E004, E005
  Pattern: Unique identifier (0% nulls)
  
  Action: Add skos:hiddenLabel "emp_num" to ex:employeeId?
  
  [Y]es / [n]o / [e]dit / [s]kip all / [?]help: y
  
  ✓ Added skos:hiddenLabel "emp_num"
  
  Add business definition? [optional]: Employee number from legacy payroll system
  ✓ Added skos:scopeNote
  
  Add example? [optional]: E001
  ✓ Added skos:example

[2/3] Column: mgr
  Suggested property: ex:reportsTo (confidence: 0.85)
  Sample values: E005, E003, E007, E002
  
  Action: Add skos:hiddenLabel "mgr" to ex:reportsTo?
  [Y]es / [n]o / [e]dit / [s]kip all / [?]help: y
  
  ✓ Added skos:hiddenLabel "mgr"

[3/3] Column: compensation_bucket
  Suggested property: ex:salaryBand (confidence: 0.55)
  Sample values: L1, L2, L3, L4, L5
  
  ⚠ Low confidence match. Review carefully.
  
  Action: Add skos:altLabel "Compensation Bucket" to ex:salaryBand?
  [Y]es / [n]o / [e]dit / [s]kip all / [?]help: e
  
  Edit label: Comp Level
  ✓ Added skos:altLabel "Comp Level"

Summary:
========
✓ Added 3 SKOS labels
✓ Added 1 scopeNote
✓ Added 1 example
✓ Enriched ontology saved to: hr_enriched.ttl

Provenance tracking:
- All changes attributed to: user@example.com
- Timestamp: 2025-11-01T10:35:00Z
- Source: alignment_report.json

Next steps:
- Re-run mapping generation with enriched ontology
- Commit hr_enriched.ttl to version control
- Share with ontology team for review
```

### 3. Non-Interactive Batch Enrichment

```bash
rdfmap ontology enrich \
  --ontology hr.ttl \
  --alignment-report alignment_report.json \
  --output hr_enriched.ttl \
  --auto-apply-high-confidence \
  --confidence-threshold 0.8
```

Automatically applies suggestions with confidence >= 0.8.

### 4. Alignment Statistics

```bash
rdfmap alignment stats \
  --reports alignment_reports/ \
  --output stats.json
```

**Output:**
```json
{
  "timeline": [
    {
      "date": "2025-10-01",
      "mapping_success_rate": 0.65,
      "unmapped_columns": 5
    },
    {
      "date": "2025-10-15",
      "mapping_success_rate": 0.78,
      "unmapped_columns": 3
    },
    {
      "date": "2025-11-01",
      "mapping_success_rate": 0.92,
      "unmapped_columns": 1
    }
  ],
  "most_problematic_columns": [
    {"column": "comp_bucket", "failed_mappings": 12},
    {"column": "org_code", "failed_mappings": 8}
  ],
  "skos_coverage_improvement": {
    "initial": 0.35,
    "current": 0.87,
    "improvement": 0.52
  }
}
```

### 5. Validate Ontology SKOS Coverage

```bash
rdfmap ontology validate \
  --ontology hr.ttl \
  --check-skos-coverage \
  --min-coverage 0.7
```

**Output:**
```
SKOS Coverage Analysis
======================

Class: ex:Employee
  Properties: 13
  With SKOS labels: 9 (69%)
  Missing SKOS: ex:middleName, ex:suffix, ex:preferredName, ex:nickname

Class: ex:Department
  Properties: 5
  With SKOS labels: 5 (100%) ✓

Overall Coverage: 78%
Recommendation: Add SKOS labels to 4 properties to reach 85% coverage
```

---

## Provenance Tracking

Every SKOS addition should be tracked with provenance:

```turtle
@prefix : <http://example.org/hr#> .
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .
@prefix prov: <http://www.w3.org/ns/prov#> .
@prefix dcterms: <http://purl.org/dc/terms/> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

:employeeId a owl:DatatypeProperty ;
    rdfs:label "employee identifier" ;
    skos:prefLabel "Employee ID" ;
    skos:hiddenLabel "emp_num" , "EMP_ID" , "emp_no" ;
    skos:changeNote """Added 'emp_num' on 2025-11-01 based on alignment report 
                       from employees_2025_q4.csv. Rationale: Legacy payroll 
                       system uses this column name."""@en ;
    dcterms:modified "2025-11-01T10:35:00Z"^^xsd:dateTime ;
    dcterms:contributor <http://example.org/users/jane.doe> ;
    prov:wasAttributedTo <http://example.org/users/jane.doe> .

# Separate provenance graph (optional)
<urn:alignment:emp_num:addition> a prov:Activity ;
    prov:wasAssociatedWith <http://example.org/users/jane.doe> ;
    prov:generated :employeeId_emp_num_label ;
    prov:used :alignment_report_2025_11_01 ;
    prov:startedAtTime "2025-11-01T10:35:00Z"^^xsd:dateTime ;
    rdfs:comment "Semi-automated SKOS enrichment via rdfmap CLI" .

:employeeId_emp_num_label a skos:Label ;
    rdf:value "emp_num" ;
    prov:wasGeneratedBy <urn:alignment:emp_num:addition> .
```

---

## Additional W3C Standards to Consider

### 7. **VOID (Vocabulary of Interlinked Datasets)**

**Use case**: Document dataset statistics and linkage quality

```turtle
:employeeDataset a void:Dataset ;
    void:triples 10000 ;
    void:properties 45 ;
    void:distinctSubjects 1000 ;
    :alignmentQuality [
        :mappingSuccessRate 0.92 ;
        :lastAlignmentDate "2025-11-01"^^xsd:date
    ] .
```

### 8. **DCAT (Data Catalog Vocabulary)**

**Use case**: Catalog data sources and mapping configurations

```turtle
:employeesMappingConfig a dcat:Dataset ;
    dcat:title "Employee Data Mapping Configuration" ;
    dcat:description "Mapping config for employee CSV to HR ontology" ;
    dcat:issued "2025-11-01"^^xsd:date ;
    dcat:keyword "employees", "HR", "payroll" ;
    :alignmentScore 0.92 .
```

### 9. **PAV (Provenance, Authoring and Versioning)**

**Use case**: Track authoring and versions

```turtle
:hr_ontology_v2 a pav:Ontology ;
    pav:createdBy <http://example.org/users/ontologist> ;
    pav:createdOn "2025-01-15"^^xsd:date ;
    pav:lastUpdateOn "2025-11-01"^^xsd:date ;
    pav:version "2.1.0" ;
    pav:previousVersion :hr_ontology_v2_0 .
```

---

## Benefits of This Approach

### For Data Engineers
✅ Clear feedback on what's working and what's not  
✅ Actionable suggestions for improvement  
✅ Track mapping success over time  
✅ Less manual YAML editing  

### For Ontologists
✅ Data-driven evidence of where ontology needs enrichment  
✅ Real column names from production systems  
✅ Prioritized list of what to add first  
✅ Provenance tracking for governance  

### For Organizations
✅ **Continuous improvement** - Mappings get better with each dataset  
✅ **Knowledge capture** - Business terminology preserved in ontology  
✅ **Collaboration** - Bridge between technical and domain experts  
✅ **Quality metrics** - Quantify semantic alignment over time  

---

## Recommended Implementation Order

### Phase 1 (MVP - 2-3 weeks)
1. ✅ SKOS label extraction (DONE)
2. ✅ Enhanced matching (DONE)
3. **Generate alignment report** (JSON format)
4. **Basic stats** (success rate, unmapped columns)

### Phase 2 (Enrichment - 3-4 weeks)
5. **Interactive enrichment CLI**
6. **Auto-suggest SKOS additions**
7. **Turtle generation for additions**
8. **Basic provenance** (dcterms:modified, dcterms:creator)

### Phase 3 (Advanced - 4-5 weeks)
9. **Full provenance with PROV-O**
10. **Alignment statistics dashboard**
11. **SKOS coverage validation**
12. **Batch enrichment mode**
13. **Version control integration**

### Phase 4 (Enterprise - 6-8 weeks)
14. **Web UI for enrichment**
15. **Collaborative review workflow**
16. **VOID/DCAT cataloging**
17. **Machine learning suggestions** (learn from past alignments)

---

## Summary

**SKOS is the right choice** as the primary standard, but you should layer in:
- **PROV-O** for change tracking
- **Dublin Core** for basic metadata
- **SHACL** for validation
- **PAV** for versioning (if needed)

The key insight is creating a **feedback loop** where:
1. Data reveals gaps
2. System suggests fixes
3. Humans approve/refine
4. Ontology improves
5. Future mappings succeed

This transforms your tool from a "data mapper" into a **semantic alignment platform** that learns and improves over time. 🚀
