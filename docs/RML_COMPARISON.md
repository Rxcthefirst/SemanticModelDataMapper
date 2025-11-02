# RML vs RDFMap Configuration Comparison

## Executive Summary

**Should you adopt RML?** 

**TL;DR: No, but consider RML import/export as a future feature.**

Your current config is **simpler, more maintainable, and better suited for your use case**. RML is powerful but complex. However, supporting RML as an **optional input format** could increase adoption.

---

## What is RML?

**RML (RDF Mapping Language)** is a W3C Community standard that extends R2RML (the W3C Recommendation for relational databases) to work with heterogeneous data sources (CSV, JSON, XML, etc.).

### RML Example

Here's what your mortgage mapping looks like in RML:

```turtle
@prefix rr: <http://www.w3.org/ns/r2rml#> .
@prefix rml: <http://semweb.mmlab.be/ns/rml#> .
@prefix ql: <http://semweb.mmlab.be/ns/ql#> .
@prefix ex: <https://example.com/mortgage#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

# Triples Map for MortgageLoan
<#LoansMapping>
  rml:logicalSource [
    rml:source "data/loans.csv" ;
    rml:referenceFormulation ql:CSV
  ] ;
  
  rr:subjectMap [
    rr:template "https://data.example.com/loan/{LoanID}" ;
    rr:class ex:MortgageLoan
  ] ;
  
  # Data properties
  rr:predicateObjectMap [
    rr:predicate ex:loanNumber ;
    rr:objectMap [
      rml:reference "LoanID" ;
      rr:datatype xsd:string
    ]
  ] ;
  
  rr:predicateObjectMap [
    rr:predicate ex:principalAmount ;
    rr:objectMap [
      rml:reference "Principal" ;
      rr:datatype xsd:decimal
    ]
  ] ;
  
  rr:predicateObjectMap [
    rr:predicate ex:interestRate ;
    rr:objectMap [
      rml:reference "InterestRate" ;
      rr:datatype xsd:decimal
    ]
  ] ;
  
  # Object property to Borrower
  rr:predicateObjectMap [
    rr:predicate ex:hasBorrower ;
    rr:objectMap [
      rr:parentTriplesMap <#BorrowerMapping> ;
      rr:joinCondition [
        rr:child "BorrowerID" ;
        rr:parent "BorrowerID"
      ]
    ]
  ] .

# Triples Map for Borrower
<#BorrowerMapping>
  rml:logicalSource [
    rml:source "data/loans.csv" ;
    rml:referenceFormulation ql:CSV
  ] ;
  
  rr:subjectMap [
    rr:template "https://data.example.com/borrower/{BorrowerID}" ;
    rr:class ex:Borrower
  ] ;
  
  rr:predicateObjectMap [
    rr:predicate ex:borrowerName ;
    rr:objectMap [
      rml:reference "BorrowerName" ;
      rr:datatype xsd:string
    ]
  ] .
```

**Your current YAML config does the same thing in 88 lines vs ~70 lines of RML Turtle.**

---

## Feature Comparison

| Feature | Your Config | RML | Winner |
|---------|-------------|-----|--------|
| **Readability** | ✅ YAML, intuitive | ❌ RDF/Turtle, verbose | **You** |
| **Multi-source joins** | ❌ Single source per sheet | ✅ Cross-source joins | **RML** |
| **Nested data** | ❌ Flat CSV/XLSX | ✅ JSON/XML hierarchies | **RML** |
| **Conditional mappings** | ❌ Not supported | ✅ `rr:condition` | **RML** |
| **Custom functions** | ✅ Transform registry | ✅ FnO (Function Ontology) | **Tie** |
| **IRI templates** | ✅ Simple `{column}` syntax | ✅ Similar | **Tie** |
| **Type inference** | ✅ Via generator | ❌ Manual | **You** |
| **Validation** | ✅ 6-layer system | ❌ External | **You** |
| **Error handling** | ✅ Row-level tracking | ❌ Typically fail-fast | **You** |
| **Streaming** | ✅ Built-in | ⚠️ Implementation-dependent | **You** |
| **Standard compliance** | ❌ Custom format | ✅ W3C standard | **RML** |
| **Tool ecosystem** | ❌ Just yours | ✅ Multiple implementations | **RML** |
| **Learning curve** | ✅ Minutes | ❌ Hours/Days | **You** |
| **Auto-generation** | ✅ `rdfmap generate` | ❌ Manual authoring | **You** |

---

## What RML Does Better

### 1. **Cross-Source Joins**

RML can join data from different sources:

```turtle
<#PersonMapping>
  rml:logicalSource [ rml:source "people.csv" ] ;
  rr:predicateObjectMap [
    rr:predicate ex:hasAddress ;
    rr:objectMap [
      rr:parentTriplesMap <#AddressMapping> ;
      rr:joinCondition [
        rr:child "address_id" ;
        rr:parent "id"
      ]
    ]
  ] .

<#AddressMapping>
  rml:logicalSource [ rml:source "addresses.json" ] .
```

**Your system:** Each sheet is independent. You'd need to pre-join data.

### 2. **Hierarchical Data (JSON/XML)**

RML uses JSONPath/XPath:

```turtle
<#JSONMapping>
  rml:logicalSource [
    rml:source "data.json" ;
    rml:referenceFormulation ql:JSONPath ;
    rml:iterator "$.users[*]"
  ] ;
  rr:predicateObjectMap [
    rr:predicate ex:email ;
    rr:objectMap [ rml:reference "$.contact.email" ]
  ] .
```

**Your system:** CSV/XLSX only (flat tables).

### 3. **Conditional Mappings**

```turtle
rr:predicateObjectMap [
  rr:predicate ex:status ;
  rr:objectMap [
    rml:reference "age" ;
    rr:condition [
      rr:predicate ex:isAdult ;
      rr:object "true"^^xsd:boolean
    ]
  ]
] .
```

**Your system:** No conditionals (apply transforms to all rows).

### 4. **Standard Tooling**

- **RMLMapper** (Java): Reference implementation
- **CARML** (Java): High-performance
- **SDM-RDFizer** (Python): Distributed processing
- **Morph-KGC** (Python): Knowledge graph construction

**Benefit:** Portability. RML mappings work across tools.

---

## What Your Config Does Better

### 1. **Human Readability**

**Your YAML:**
```yaml
columns:
  Principal:
    as: ex:principalAmount
    datatype: xsd:decimal
    transform: to_decimal
    required: true
```

**RML Turtle:**
```turtle
rr:predicateObjectMap [
  rr:predicate ex:principalAmount ;
  rr:objectMap [
    rml:reference "Principal" ;
    rr:datatype xsd:decimal
  ]
] .
```

**Winner:** Your config. Business users can edit YAML; RML requires RDF knowledge.

### 2. **Auto-Generation**

Your `rdfmap generate` command doesn't exist in RML land. You'd need to manually write every mapping.

### 3. **Integrated Validation**

Your system validates:
1. Config schema (Pydantic)
2. Required columns
3. Datatype constraints
4. Ontology alignment
5. SHACL shapes
6. Undefined properties

RML: Validation is external (you run the mapper, then validate output).

### 4. **Error Recovery**

```yaml
options:
  on_error: report  # Continue processing, collect errors
```

RML tools typically fail fast. Your row-level error tracking is superior.

### 5. **Developer Experience**

- JSON Schema export for validation
- Type hints throughout
- Modern Python CLI
- Streaming by default
- Comprehensive docs

RML tools are often Java-based academic projects with... varying DX.

---

## Should You Support RML?

### Option 1: **Keep Your Config (Recommended)**

**Pros:**
- Simpler to maintain
- Better for your target users (data engineers, not Semantic Web experts)
- Auto-generation is a killer feature
- Faster development

**Cons:**
- Not a standard
- Limits interoperability

### Option 2: **Add RML Import**

**Strategy:** Convert RML → Your Config

```python
# New module: src/rdfmap/importers/rml.py

def rml_to_rdfmap_config(rml_file: str) -> MappingConfig:
    """Convert RML mapping to RDFMap config."""
    # Parse RML Turtle
    # Extract TriplesMap definitions
    # Convert to your YAML structure
    # Handle limitations (warn about unsupported features)
```

**Pros:**
- Users can import existing RML mappings
- Leverage existing RML ecosystem
- Transition path for RML users

**Cons:**
- RML is more expressive (can't convert everything)
- Maintenance burden

### Option 3: **Add RML Export**

**Strategy:** Convert Your Config → RML

```python
# New module: src/rdfmap/exporters/rml.py

def rdfmap_config_to_rml(config: MappingConfig) -> str:
    """Export RDFMap config as RML Turtle."""
    # Your config is a subset of RML capabilities
    # Should be lossless conversion
```

**Pros:**
- Users can switch to other RML tools
- Increases trust (standards compliance)
- Good for academic/enterprise adoption

**Cons:**
- Effort to implement
- Most users won't need it

### Option 4: **Hybrid Approach (Best Long-Term)**

**Strategy:** Use RML as an intermediate representation

```
Your YAML → RML (in-memory) → RDF Output
             ↑
             Also accept RML files directly
```

**Implementation:**
1. Create `rml_exporter.py` (YAML → RML)
2. Create `rml_importer.py` (RML → YAML, with warnings for unsupported features)
3. Add CLI commands:
   ```bash
   rdfmap export-rml --mapping config.yaml --output mapping.rml.ttl
   rdfmap import-rml --rml mapping.rml.ttl --output config.yaml
   ```

**Pros:**
- Best of both worlds
- Standards compliance
- Interoperability
- Keeps your UX advantages

**Cons:**
- Significant engineering effort
- Adds complexity

---

## Recommended Roadmap

### Phase 1: **Keep Your Config** (Current)
✅ Already done. Your config is excellent.

### Phase 2: **Add RML Export** (Low-hanging fruit)
Estimated effort: 1-2 weeks

```bash
rdfmap export-rml --mapping mortgage_mapping.yaml -o mapping.rml.ttl
```

Benefits:
- Academic credibility
- Standards compliance
- Marketing ("Fully compatible with W3C RML standard")

### Phase 3: **Add RML Import** (Medium effort)
Estimated effort: 2-3 weeks

```bash
rdfmap import-rml --rml external_mapping.rml.ttl -o my_config.yaml
```

Benefits:
- Attract users from RMLMapper/CARML
- Leverage existing RML mappings

### Phase 4: **Consider RML as Internal Format** (Future)
Only if you need advanced features (cross-source joins, nested data).

---

## Real-World Scenario: When Users Need RML

### Scenario 1: Multi-Source Joins
**Problem:** User has `customers.csv` + `orders.json` and needs to join them.

**RML Solution:** Direct cross-source joins.

**Your Solution:** 
1. Pre-process with pandas/SQL to create joined CSV
2. Use your tool on the result

**Verdict:** Your approach is simpler for most users.

### Scenario 2: Nested JSON
**Problem:** User has deeply nested JSON (e.g., API responses).

**RML Solution:** JSONPath references.

**Your Solution:** Flatten to CSV first (pandas `json_normalize()`).

**Verdict:** RML is better for this use case.

### Scenario 3: Complex Conditionals
**Problem:** Map `age > 18` → `ex:Adult`, else `ex:Minor`.

**RML Solution:** Native conditionals.

**Your Solution:** Add a custom transform or pre-process.

**Verdict:** RML is more flexible.

---

## Bottom Line

### Your Config Wins for:
1. **Simplicity** - YAML > Turtle for most users
2. **Auto-generation** - Game changer
3. **Validation** - Integrated, comprehensive
4. **DX** - Modern Python, great docs
5. **Target audience** - Data engineers, not Semantic Web researchers

### RML Wins for:
1. **Standards compliance** - W3C community standard
2. **Interoperability** - Works with other tools
3. **Advanced features** - Joins, nested data, conditionals
4. **Academic credibility** - Recognized in research

### My Recommendation:

**Keep your config as the primary interface**, but add:

1. **RML Export** (Phase 2) - Easy, high value
   - Increases credibility
   - Enables tool switching
   - Marketing benefit

2. **RML Import** (Phase 3) - Medium effort, medium value
   - Attracts RML users
   - Provides migration path
   - Handles limitations gracefully (warn about unsupported features)

3. **Document limitations** - Be clear about what you don't support
   - "RDFMap focuses on tabular data (CSV/XLSX)"
   - "For multi-source joins or nested JSON, use RMLMapper then import"

This positions you as **"RML-compatible but easier to use"** rather than competing directly with RML.

---

## Implementation Example: RML Export

Here's a quick proof-of-concept:

```python
# src/rdfmap/exporters/rml_exporter.py

from rdflib import Graph, Namespace, Literal, URIRef
from rdflib.namespace import RDF, XSD
from rdfmap.models.mapping import MappingConfig

RML = Namespace("http://semweb.mmlab.be/ns/rml#")
RR = Namespace("http://www.w3.org/ns/r2rml#")
QL = Namespace("http://semweb.mmlab.be/ns/ql#")

def export_to_rml(config: MappingConfig) -> str:
    """Convert RDFMap config to RML Turtle."""
    g = Graph()
    g.bind("rml", RML)
    g.bind("rr", RR)
    g.bind("ql", QL)
    
    for ns_prefix, ns_uri in config.namespaces.items():
        g.bind(ns_prefix, Namespace(ns_uri))
    
    for sheet in config.sheets:
        # Create TriplesMap
        tm = URIRef(f"#{sheet.name}Mapping")
        
        # Logical source
        ls = URIRef(f"#{sheet.name}LogicalSource")
        g.add((tm, RML.logicalSource, ls))
        g.add((ls, RML.source, Literal(sheet.source)))
        g.add((ls, RML.referenceFormulation, QL.CSV))
        
        # Subject map
        sm = URIRef(f"#{sheet.name}SubjectMap")
        g.add((tm, RR.subjectMap, sm))
        g.add((sm, RR.template, Literal(sheet.row_resource.iri_template)))
        
        # Class
        class_uri = URIRef(sheet.row_resource.class_type)
        g.add((sm, RR.class_, class_uri))
        
        # Predicate-object maps for columns
        for col_name, col_mapping in sheet.columns.items():
            pom = URIRef(f"#{sheet.name}_{col_name}_POM")
            g.add((tm, RR.predicateObjectMap, pom))
            g.add((pom, RR.predicate, URIRef(col_mapping.as_property)))
            
            om = URIRef(f"#{sheet.name}_{col_name}_OM")
            g.add((pom, RR.objectMap, om))
            g.add((om, RML.reference, Literal(col_name)))
            
            if col_mapping.datatype:
                g.add((om, RR.datatype, URIRef(col_mapping.datatype)))
        
        # TODO: Handle objects (linked resources)
    
    return g.serialize(format="turtle")
```

Usage:
```bash
rdfmap export-rml --mapping config.yaml -o mapping.rml.ttl
```

---

## Conclusion

**Don't switch to RML as your primary format.** Your config is superior for your use case.

**Do consider RML import/export** to increase adoption and standards compliance.

**Focus on your strengths:** Auto-generation, validation, DX. These are what make your tool special.

RML is powerful but complex. You're building a **pragmatic tool for data engineers**, not a research platform. Keep that focus.
