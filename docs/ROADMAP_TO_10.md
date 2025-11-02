# Roadmap to 10/10 Innovation Score

**Current Score:** 7.5-8/10  
**Target Score:** 10/10  
**Gap:** 2-2.5 points  

This document outlines the strategic path to close the innovation gap and position RDFMap as the **definitive solution** for semantic data mapping.

---

## The 2.5 Point Gap: What's Missing?

### Current Weaknesses (Why Not 10/10):

1. **Not a W3C Standard** (-1.0 points)
   - Custom config format limits interoperability
   - Can't leverage existing RML ecosystem
   - Academic/enterprise adoption barrier

2. **Limited Data Source Support** (-0.75 points)
   - CSV/XLSX only (flat tables)
   - No hierarchical data (JSON/XML)
   - No database connectors

3. **No Multi-Source Capabilities** (-0.5 points)
   - Can't join data across sources
   - Each sheet is independent
   - Requires pre-processing for complex scenarios

4. **Missing Advanced Features** (-0.25 points)
   - No conditional mappings
   - Limited transform expressiveness
   - No incremental updates

**Total Gap:** 2.5 points

---

## Strategic Roadmap: Three Phases

```
Phase 1 (3-6 months): Standards Compatibility → +1.0 point
Phase 2 (6-12 months): Advanced Capabilities → +1.0 point  
Phase 3 (12-18 months): Ecosystem Leadership → +0.5 point
```

---

# Phase 1: Standards Compatibility (3-6 months)

**Goal:** Become **RML-compatible** while maintaining UX advantages  
**Impact:** Innovation score → **8.5-9.0/10**

## 1.1 RML Export (Weeks 1-4)

### Implementation

**New Module:** `src/rdfmap/exporters/rml_exporter.py`

```python
"""Export RDFMap configurations to RML (R2RML/RML) format."""

from rdflib import Graph, Namespace, Literal, URIRef, BNode
from rdflib.namespace import RDF, XSD
from rdfmap.models.mapping import MappingConfig, SheetMapping

# RML/R2RML namespaces
RML = Namespace("http://semweb.mmlab.be/ns/rml#")
RR = Namespace("http://www.w3.org/ns/r2rml#")
QL = Namespace("http://semweb.mmlab.be/ns/ql#")

class RMLExporter:
    """Convert RDFMap config to RML Turtle format."""
    
    def __init__(self, config: MappingConfig):
        self.config = config
        self.graph = Graph()
        self._bind_namespaces()
    
    def export(self) -> str:
        """Generate complete RML mapping as Turtle string."""
        for sheet in self.config.sheets:
            self._create_triples_map(sheet)
        return self.graph.serialize(format="turtle")
    
    def _create_triples_map(self, sheet: SheetMapping):
        """Create RML TriplesMap for a sheet."""
        # TriplesMap node
        tm = URIRef(f"#{sheet.name}TriplesMap")
        self.graph.add((tm, RDF.type, RR.TriplesMap))
        
        # Logical source
        self._add_logical_source(tm, sheet)
        
        # Subject map
        self._add_subject_map(tm, sheet)
        
        # Predicate-object maps (data properties)
        for col_name, col_mapping in sheet.columns.items():
            self._add_predicate_object_map(tm, col_name, col_mapping)
        
        # Linked objects (foreign key joins)
        for obj_name, linked_obj in sheet.objects.items():
            self._add_object_reference_map(tm, obj_name, linked_obj, sheet)
    
    def _add_logical_source(self, tm: URIRef, sheet: SheetMapping):
        """Add rml:logicalSource with CSV configuration."""
        ls = BNode()
        self.graph.add((tm, RML.logicalSource, ls))
        self.graph.add((ls, RML.source, Literal(sheet.source)))
        self.graph.add((ls, RML.referenceFormulation, QL.CSV))
    
    def _add_subject_map(self, tm: URIRef, sheet: SheetMapping):
        """Add rr:subjectMap with IRI template and class."""
        sm = BNode()
        self.graph.add((tm, RR.subjectMap, sm))
        
        # IRI template
        template = sheet.row_resource.iri_template
        self.graph.add((sm, RR.template, Literal(template)))
        
        # rdf:type
        class_uri = self._expand_curie(sheet.row_resource.class_type)
        self.graph.add((sm, RR.class_, class_uri))
    
    def _add_predicate_object_map(self, tm: URIRef, col: str, mapping):
        """Add predicate-object map for a column."""
        pom = BNode()
        self.graph.add((tm, RR.predicateObjectMap, pom))
        
        # Predicate
        pred_uri = self._expand_curie(mapping.as_property)
        self.graph.add((pom, RR.predicate, pred_uri))
        
        # Object map
        om = BNode()
        self.graph.add((pom, RR.objectMap, om))
        self.graph.add((om, RML.reference, Literal(col)))
        
        # Datatype
        if mapping.datatype:
            dt_uri = self._expand_curie(mapping.datatype)
            self.graph.add((om, RR.datatype, dt_uri))
        
        # Language tag
        if mapping.language:
            self.graph.add((om, RR.language, Literal(mapping.language)))
    
    def _add_object_reference_map(self, tm: URIRef, name: str, 
                                   linked_obj, sheet: SheetMapping):
        """Add object property referencing another TriplesMap."""
        pom = BNode()
        self.graph.add((tm, RR.predicateObjectMap, pom))
        
        # Predicate (object property)
        pred_uri = self._expand_curie(linked_obj.predicate)
        self.graph.add((pom, RR.predicate, pred_uri))
        
        # Object map with parent triples map reference
        om = BNode()
        self.graph.add((pom, RR.objectMap, om))
        
        # Create parent triples map for linked object
        parent_tm = URIRef(f"#{name}TriplesMap")
        self.graph.add((om, RR.parentTriplesMap, parent_tm))
        
        # Create the parent TriplesMap definition
        self._create_linked_object_triples_map(parent_tm, name, 
                                                linked_obj, sheet)
    
    def _create_linked_object_triples_map(self, tm: URIRef, name: str,
                                          linked_obj, sheet: SheetMapping):
        """Create TriplesMap for a linked object."""
        self.graph.add((tm, RDF.type, RR.TriplesMap))
        
        # Same logical source as parent
        ls = BNode()
        self.graph.add((tm, RML.logicalSource, ls))
        self.graph.add((ls, RML.source, Literal(sheet.source)))
        self.graph.add((ls, RML.referenceFormulation, QL.CSV))
        
        # Subject map for linked object
        sm = BNode()
        self.graph.add((tm, RR.subjectMap, sm))
        self.graph.add((sm, RR.template, Literal(linked_obj.iri_template)))
        
        class_uri = self._expand_curie(linked_obj.class_type)
        self.graph.add((sm, RR.class_, class_uri))
        
        # Properties of linked object
        for prop in linked_obj.properties:
            self._add_predicate_object_map(tm, prop.column, prop)
    
    def _expand_curie(self, curie: str) -> URIRef:
        """Expand CURIE to full URI using config namespaces."""
        if ":" in curie and not curie.startswith("http"):
            prefix, local = curie.split(":", 1)
            if prefix in self.config.namespaces:
                return URIRef(self.config.namespaces[prefix] + local)
        return URIRef(curie)
    
    def _bind_namespaces(self):
        """Bind all namespaces to graph."""
        self.graph.bind("rml", RML)
        self.graph.bind("rr", RR)
        self.graph.bind("ql", QL)
        for prefix, uri in self.config.namespaces.items():
            self.graph.bind(prefix, Namespace(uri))


def export_rml(config: MappingConfig, output_path: str = None) -> str:
    """
    Export RDFMap configuration to RML Turtle format.
    
    Args:
        config: Validated MappingConfig object
        output_path: Optional file path to write output
    
    Returns:
        RML mapping as Turtle string
    """
    exporter = RMLExporter(config)
    rml_turtle = exporter.export()
    
    if output_path:
        with open(output_path, "w") as f:
            f.write(rml_turtle)
    
    return rml_turtle
```

### CLI Integration

**Updated:** `src/rdfmap/cli/main.py`

```python
@app.command()
def export_rml(
    mapping: Annotated[Path, typer.Option("--mapping", "-m", 
                                          help="RDFMap config file")] = ...,
    output: Annotated[Path, typer.Option("--output", "-o",
                                         help="Output RML file")] = ...,
    verbose: Annotated[bool, typer.Option("--verbose", "-v")] = False
):
    """
    Export RDFMap configuration to RML (W3C standard) format.
    
    Example:
        rdfmap export-rml -m config.yaml -o mapping.rml.ttl
    """
    from rdfmap.models.mapping import load_mapping_config
    from rdfmap.exporters.rml_exporter import export_rml
    
    if verbose:
        typer.echo(f"Loading config: {mapping}")
    
    config = load_mapping_config(mapping)
    
    if verbose:
        typer.echo(f"Exporting to RML...")
    
    rml_content = export_rml(config, str(output))
    
    typer.secho(f"✓ RML mapping exported to: {output}", fg=typer.colors.GREEN)
    typer.echo(f"  Compatible with: RMLMapper, CARML, Morph-KGC")
```

### Testing

**New Test:** `tests/test_rml_exporter.py`

```python
"""Tests for RML export functionality."""

import pytest
from rdflib import Graph, Namespace
from rdfmap.models.mapping import load_mapping_config
from rdfmap.exporters.rml_exporter import export_rml, RMLExporter

RR = Namespace("http://www.w3.org/ns/r2rml#")
RML = Namespace("http://semweb.mmlab.be/ns/rml#")

def test_export_simple_mapping():
    """Test basic RML export."""
    config = load_mapping_config("examples/mortgage/config/mortgage_mapping.yaml")
    rml_turtle = export_rml(config)
    
    # Parse as RDF
    g = Graph()
    g.parse(data=rml_turtle, format="turtle")
    
    # Verify TriplesMap exists
    triples_maps = list(g.subjects(RDF.type, RR.TriplesMap))
    assert len(triples_maps) > 0
    
    # Verify logical source
    for tm in triples_maps:
        ls = g.value(tm, RML.logicalSource)
        assert ls is not None

def test_rml_roundtrip_compatibility():
    """Test that exported RML can be processed by RMLMapper."""
    # This would require RMLMapper installed
    # For now, validate RDF structure
    config = load_mapping_config("examples/mortgage/config/mortgage_mapping.yaml")
    rml_turtle = export_rml(config)
    
    g = Graph()
    g.parse(data=rml_turtle, format="turtle")
    
    # Check required RML/R2RML structure
    assert len(list(g.triples((None, RR.predicateObjectMap, None)))) > 0
    assert len(list(g.triples((None, RR.subjectMap, None)))) > 0
```

### Documentation

**New Section in README.md:**

```markdown
#### `export-rml`

Export RDFMap configuration to RML (W3C standard) format for compatibility with other tools.

```bash
rdfmap export-rml --mapping config.yaml --output mapping.rml.ttl
```

**Use Cases:**
- Share mappings with teams using RMLMapper/CARML
- Archive mappings in standards-compliant format
- Validate against W3C specifications
- Integrate with enterprise RML workflows

**Compatible Tools:**
- [RMLMapper](https://github.com/RMLio/rmlmapper-java) (Java)
- [CARML](https://github.com/carml/carml) (Java)
- [Morph-KGC](https://github.com/oeg-upm/morph-kgc) (Python)
- [SDM-RDFizer](https://github.com/SDM-TIB/SDM-RDFizer) (Python)
```

### Deliverables

- ✅ `src/rdfmap/exporters/rml_exporter.py` (300-400 lines)
- ✅ CLI command: `rdfmap export-rml`
- ✅ Unit tests with 90%+ coverage
- ✅ Documentation in README + example
- ✅ Validation: Export mortgage example, verify with RMLMapper

**Marketing Impact:** "Fully compatible with W3C RML standard"

---

## 1.2 RML Import (Weeks 5-10)

### Implementation

**New Module:** `src/rdfmap/importers/rml_importer.py`

```python
"""Import RML mappings to RDFMap configuration."""

from rdflib import Graph, Namespace, RDF, Literal
from typing import Dict, List, Optional
from rdfmap.models.mapping import (
    MappingConfig, SheetMapping, RowResource, 
    ColumnMapping, LinkedObject, DefaultsConfig
)

RR = Namespace("http://www.w3.org/ns/r2rml#")
RML = Namespace("http://semweb.mmlab.be/ns/rml#")
QL = Namespace("http://semweb.mmlab.be/ns/ql#")

class RMLImporter:
    """Import RML mappings to RDFMap config."""
    
    def __init__(self, rml_file: str):
        self.graph = Graph()
        self.graph.parse(rml_file, format="turtle")
        self.warnings: List[str] = []
    
    def import_mapping(self) -> MappingConfig:
        """Convert RML to RDFMap config."""
        # Extract namespaces
        namespaces = self._extract_namespaces()
        
        # Process each TriplesMap
        sheets = []
        for tm in self.graph.subjects(RDF.type, RR.TriplesMap):
            sheet = self._process_triples_map(tm)
            if sheet:
                sheets.append(sheet)
        
        # Build config
        config = MappingConfig(
            namespaces=namespaces,
            defaults=DefaultsConfig(base_iri="http://example.org/"),
            sheets=sheets
        )
        
        return config
    
    def _process_triples_map(self, tm) -> Optional[SheetMapping]:
        """Convert RML TriplesMap to SheetMapping."""
        # Get logical source
        ls = self.graph.value(tm, RML.logicalSource)
        if not ls:
            return None
        
        source = self.graph.value(ls, RML.source)
        ref_formulation = self.graph.value(ls, RML.referenceFormulation)
        
        # Only support CSV for now
        if ref_formulation != QL.CSV:
            self.warnings.append(
                f"Unsupported reference formulation: {ref_formulation}. "
                "RDFMap currently supports CSV/XLSX only."
            )
            return None
        
        # Get subject map
        sm = self.graph.value(tm, RR.subjectMap)
        template = str(self.graph.value(sm, RR.template))
        class_uri = self.graph.value(sm, RR.class_)
        
        # Extract sheet name from TriplesMap URI
        tm_str = str(tm)
        sheet_name = tm_str.split("#")[-1].replace("TriplesMap", "")
        
        # Build row resource
        row_resource = RowResource(
            class_type=self._shrink_uri(class_uri),
            iri_template=template
        )
        
        # Process predicate-object maps
        columns = {}
        objects = {}
        
        for pom in self.graph.objects(tm, RR.predicateObjectMap):
            predicate = self.graph.value(pom, RR.predicate)
            om = self.graph.value(pom, RR.objectMap)
            
            # Check if it's a reference to parent triples map (object property)
            parent_tm = self.graph.value(om, RR.parentTriplesMap)
            
            if parent_tm:
                # It's a linked object
                linked = self._process_linked_object(parent_tm, predicate)
                if linked:
                    obj_name = str(parent_tm).split("#")[-1]
                    objects[obj_name] = linked
            else:
                # It's a data property
                reference = self.graph.value(om, RML.reference)
                if reference:
                    col_name = str(reference)
                    datatype = self.graph.value(om, RR.datatype)
                    language = self.graph.value(om, RR.language)
                    
                    columns[col_name] = ColumnMapping(
                        as_property=self._shrink_uri(predicate),
                        datatype=self._shrink_uri(datatype) if datatype else None,
                        language=str(language) if language else None
                    )
        
        return SheetMapping(
            name=sheet_name,
            source=str(source),
            row_resource=row_resource,
            columns=columns,
            objects=objects
        )
    
    def _process_linked_object(self, parent_tm, predicate) -> Optional[LinkedObject]:
        """Process parent TriplesMap as linked object."""
        sm = self.graph.value(parent_tm, RR.subjectMap)
        template = str(self.graph.value(sm, RR.template))
        class_uri = self.graph.value(sm, RR.class_)
        
        # Get properties
        properties = []
        for pom in self.graph.objects(parent_tm, RR.predicateObjectMap):
            pred = self.graph.value(pom, RR.predicate)
            om = self.graph.value(pom, RR.objectMap)
            reference = self.graph.value(om, RML.reference)
            
            if reference:
                datatype = self.graph.value(om, RR.datatype)
                properties.append({
                    "column": str(reference),
                    "as": self._shrink_uri(pred),
                    "datatype": self._shrink_uri(datatype) if datatype else None
                })
        
        return LinkedObject(
            predicate=self._shrink_uri(predicate),
            class_type=self._shrink_uri(class_uri),
            iri_template=template,
            properties=properties
        )
    
    def _extract_namespaces(self) -> Dict[str, str]:
        """Extract namespace bindings from RML graph."""
        namespaces = {}
        for prefix, uri in self.graph.namespaces():
            if prefix and prefix not in ["rml", "rr", "ql"]:
                namespaces[prefix] = str(uri)
        
        # Ensure xsd is present
        if "xsd" not in namespaces:
            namespaces["xsd"] = "http://www.w3.org/2001/XMLSchema#"
        
        return namespaces
    
    def _shrink_uri(self, uri) -> str:
        """Convert full URI to CURIE if possible."""
        if not uri:
            return None
        
        uri_str = str(uri)
        for prefix, ns in self.graph.namespaces():
            ns_str = str(ns)
            if uri_str.startswith(ns_str):
                return f"{prefix}:{uri_str[len(ns_str):]}"
        
        return uri_str


def import_rml(rml_file: str, output_yaml: str = None) -> MappingConfig:
    """
    Import RML mapping to RDFMap configuration.
    
    Args:
        rml_file: Path to RML Turtle file
        output_yaml: Optional path to write YAML config
    
    Returns:
        MappingConfig object
    
    Raises:
        ValueError: If RML contains unsupported features
    """
    importer = RMLImporter(rml_file)
    config = importer.import_mapping()
    
    # Print warnings
    if importer.warnings:
        print("⚠️  Import warnings:")
        for warning in importer.warnings:
            print(f"  - {warning}")
    
    # Export to YAML if requested
    if output_yaml:
        import yaml
        with open(output_yaml, "w") as f:
            yaml.dump(config.model_dump(by_alias=True), f, 
                     default_flow_style=False, sort_keys=False)
    
    return config
```

### CLI Integration

```python
@app.command()
def import_rml(
    rml: Annotated[Path, typer.Option("--rml", "-r",
                                      help="RML mapping file")] = ...,
    output: Annotated[Path, typer.Option("--output", "-o",
                                         help="Output YAML config")] = ...,
    verbose: Annotated[bool, typer.Option("--verbose", "-v")] = False
):
    """
    Import RML mapping to RDFMap configuration.
    
    Example:
        rdfmap import-rml -r mapping.rml.ttl -o config.yaml
    
    Note: Some advanced RML features may not be supported.
    Warnings will be displayed for unsupported constructs.
    """
    from rdfmap.importers.rml_importer import import_rml
    
    if verbose:
        typer.echo(f"Loading RML: {rml}")
    
    config = import_rml(str(rml), str(output))
    
    typer.secho(f"✓ RML imported to: {output}", fg=typer.colors.GREEN)
    typer.echo(f"  Sheets: {len(config.sheets)}")
    typer.echo(f"  Namespaces: {len(config.namespaces)}")
```

### Limitations Document

**New File:** `docs/RML_IMPORT_LIMITATIONS.md`

```markdown
# RML Import Limitations

RDFMap supports importing **RML mappings for CSV data sources**. However, some advanced RML features are not supported.

## ✅ Supported Features

- CSV logical sources (`rml:source`, `ql:CSV`)
- IRI templates (`rr:template`)
- Data properties with references (`rml:reference`)
- XSD datatypes (`rr:datatype`)
- Language tags (`rr:language`)
- Object properties (linked resources via `rr:parentTriplesMap`)
- Class declarations (`rr:class`)

## ❌ Unsupported Features

| RML Feature | Status | Workaround |
|-------------|--------|------------|
| JSON/XML sources | Not supported | Pre-convert to CSV |
| JSONPath/XPath | Not supported | Flatten hierarchical data |
| Cross-source joins | Not supported | Pre-join data sources |
| Custom functions (FnO) | Not supported | Use RDFMap transforms |
| Conditional mappings | Not supported | Filter data before processing |
| Named graphs | Not supported | Post-process RDF output |
| RML views/queries | Not supported | Pre-process with SQL/pandas |

## Import Process

1. Parse RML Turtle file
2. Extract TriplesMap definitions
3. Convert to RDFMap YAML structure
4. Display warnings for unsupported features
5. Export clean YAML config

## Example

**Input RML:**
```turtle
<#PersonMapping> a rr:TriplesMap ;
  rml:logicalSource [
    rml:source "people.csv" ;
    rml:referenceFormulation ql:CSV
  ] ;
  rr:subjectMap [
    rr:template "http://example.org/person/{id}" ;
    rr:class ex:Person
  ] ;
  rr:predicateObjectMap [
    rr:predicate ex:name ;
    rr:objectMap [ rml:reference "name" ]
  ] .
```

**Output YAML:**
```yaml
namespaces:
  ex: http://example.org/
  xsd: http://www.w3.org/2001/XMLSchema#

defaults:
  base_iri: http://example.org/

sheets:
  - name: Person
    source: people.csv
    row_resource:
      class: ex:Person
      iri_template: "http://example.org/person/{id}"
    columns:
      name:
        as: ex:name
```

**Command:**
```bash
rdfmap import-rml -r mapping.rml.ttl -o config.yaml
```
```

### Deliverables

- ✅ `src/rdfmap/importers/rml_importer.py` (400-500 lines)
- ✅ CLI command: `rdfmap import-rml`
- ✅ Limitations documentation
- ✅ Unit tests with RML examples
- ✅ Migration guide from RMLMapper

**Marketing Impact:** "Import existing RML mappings" + "Transition path from other tools"

---

## 1.3 Standards Compliance Documentation (Weeks 11-12)

### Deliverables

1. **Compliance Matrix:** `docs/STANDARDS_COMPLIANCE.md`
2. **Academic Paper:** Submit to ISWC (International Semantic Web Conference)
3. **W3C Community Engagement:** Join RML Community Group
4. **Certification Tests:** Validate against RML test suite

**Marketing Impact:** 
- "W3C RML Compatible"
- Academic citations
- Enterprise trust

---

# Phase 2: Advanced Capabilities (6-12 months)

**Goal:** Match RML's expressiveness while maintaining UX  
**Impact:** Innovation score → **9.0-9.5/10**

## 2.1 Multi-Source Support (Months 7-9)

### Problem

Current limitation: Each sheet is independent. Can't join data across sources.

### Solution: Cross-Sheet References

**New Config Syntax:**

```yaml
sheets:
  - name: customers
    source: customers.csv
    row_resource:
      class: ex:Customer
      iri_template: "{base_iri}customer/{customer_id}"
    columns:
      customer_id:
        as: ex:customerId
        datatype: xsd:string
      name:
        as: ex:name
        datatype: xsd:string

  - name: orders
    source: orders.csv
    row_resource:
      class: ex:Order
      iri_template: "{base_iri}order/{order_id}"
    columns:
      order_id:
        as: ex:orderId
        datatype: xsd:string
      total:
        as: ex:totalAmount
        datatype: xsd:decimal
    
    # NEW: Cross-sheet references
    references:
      - column: customer_id
        target_sheet: customers
        target_column: customer_id
        predicate: ex:placedBy
        # Creates: <order/123> ex:placedBy <customer/456>
```

### Implementation

**Updated:** `src/rdfmap/models/mapping.py`

```python
class SheetReference(BaseModel):
    """Reference to another sheet for cross-sheet joins."""
    
    column: str = Field(..., description="Column in current sheet")
    target_sheet: str = Field(..., description="Name of target sheet")
    target_column: str = Field(..., description="Column in target sheet")
    predicate: str = Field(..., description="Predicate linking resources")
    required: bool = Field(False, description="Fail if target not found")


class SheetMapping(BaseModel):
    # ... existing fields ...
    references: List[SheetReference] = Field(
        default_factory=list,
        description="Cross-sheet references (joins)"
    )
```

**New Module:** `src/rdfmap/resolver/cross_sheet_resolver.py`

```python
"""Resolve cross-sheet references (joins)."""

from typing import Dict, Set
from pandas import DataFrame
from rdfmap.models.mapping import MappingConfig, SheetMapping

class CrossSheetResolver:
    """Resolve cross-sheet references during processing."""
    
    def __init__(self, config: MappingConfig):
        self.config = config
        self.sheet_data: Dict[str, DataFrame] = {}
        self.key_indices: Dict[str, Dict] = {}
    
    def load_sheet_data(self, sheet: SheetMapping, df: DataFrame):
        """Cache sheet data for cross-referencing."""
        self.sheet_data[sheet.name] = df
        
        # Build indices for join columns
        for ref in sheet.references:
            target = ref.target_sheet
            if target not in self.key_indices:
                target_df = self.sheet_data.get(target)
                if target_df is not None:
                    self.key_indices[target] = {
                        ref.target_column: target_df.set_index(ref.target_column)
                    }
    
    def resolve_reference(self, sheet_name: str, row: dict, 
                         reference: SheetReference) -> Optional[str]:
        """
        Resolve a single cross-sheet reference.
        
        Returns IRI of target resource or None if not found.
        """
        # Get value from current row
        key_value = row.get(reference.column)
        if not key_value:
            return None
        
        # Look up in target sheet
        target_df = self.sheet_data.get(reference.target_sheet)
        if target_df is None:
            if reference.required:
                raise ValueError(
                    f"Target sheet '{reference.target_sheet}' not loaded"
                )
            return None
        
        # Find matching row
        matches = target_df[
            target_df[reference.target_column] == key_value
        ]
        
        if matches.empty:
            if reference.required:
                raise ValueError(
                    f"No match found for {reference.column}={key_value} "
                    f"in sheet '{reference.target_sheet}'"
                )
            return None
        
        # Generate IRI for target resource
        target_sheet = next(
            s for s in self.config.sheets 
            if s.name == reference.target_sheet
        )
        target_iri = self._generate_iri(
            target_sheet.row_resource.iri_template,
            matches.iloc[0].to_dict()
        )
        
        return target_iri
    
    def _generate_iri(self, template: str, row: dict) -> str:
        """Generate IRI from template and row data."""
        # Reuse existing IRI generation logic
        from rdfmap.iri.generator import IRIGenerator
        return IRIGenerator.generate(template, row)
```

### CLI Enhancement

```bash
# Process multiple sheets with cross-references
rdfmap convert \
  --mapping multi_sheet_mapping.yaml \
  --format ttl \
  --output output.ttl \
  --validate-refs  # NEW: Validate cross-sheet references
```

### Deliverables

- ✅ Cross-sheet reference support
- ✅ Join validation
- ✅ Documentation with examples
- ✅ Performance optimization (indexed lookups)

**Impact:** +0.5 points (multi-source capability)

---

## 2.2 Hierarchical Data Support (Months 10-12)

### Problem

Only flat CSV/XLSX supported. No JSON/XML.

### Solution: JSON/XML Parsers with Path Expressions

**New Config Syntax:**

```yaml
sheets:
  - name: api_response
    source: users.json
    source_type: json  # NEW
    
    # JSON path for iteration
    iterator: "$.users[*]"
    
    row_resource:
      class: ex:User
      iri_template: "{base_iri}user/{$.id}"  # JSONPath in template
    
    columns:
      # Nested field access
      email:
        path: "$.contact.email"  # JSONPath
        as: ex:email
        datatype: xsd:string
      
      city:
        path: "$.address.city"
        as: ex:city
        datatype: xsd:string
      
      # Array handling
      tags:
        path: "$.metadata.tags[*]"
        as: ex:tag
        datatype: xsd:string
        multi_valued: true
```

**Example JSON:**
```json
{
  "users": [
    {
      "id": "u123",
      "contact": {
        "email": "user@example.com"
      },
      "address": {
        "city": "Boston"
      },
      "metadata": {
        "tags": ["premium", "verified"]
      }
    }
  ]
}
```

### Implementation

**New Module:** `src/rdfmap/parsers/json_parser.py`

```python
"""JSON data source parser with JSONPath support."""

import json
import jsonpath_ng
from typing import Iterator, Dict, Any
from rdfmap.parsers.data_source import DataSource

class JSONDataSource(DataSource):
    """Parse JSON with JSONPath expressions."""
    
    def __init__(self, source_path: str, iterator: str = "$[*]"):
        self.source_path = source_path
        self.iterator = jsonpath_ng.parse(iterator)
        self.data = self._load_json()
    
    def _load_json(self) -> Any:
        """Load JSON file."""
        with open(self.source_path) as f:
            return json.load(f)
    
    def rows(self) -> Iterator[Dict[str, Any]]:
        """Iterate over matched elements."""
        for match in self.iterator.find(self.data):
            # Flatten nested object to dict
            yield self._flatten(match.value)
    
    def _flatten(self, obj: Any, parent_key: str = "") -> Dict:
        """Flatten nested dict to dot-notation keys."""
        items = []
        if isinstance(obj, dict):
            for k, v in obj.items():
                new_key = f"{parent_key}.{k}" if parent_key else k
                if isinstance(v, dict):
                    items.extend(self._flatten(v, new_key).items())
                elif isinstance(v, list):
                    items.append((new_key, v))
                else:
                    items.append((new_key, v))
        return dict(items)


class JSONPathColumnMapping:
    """Resolve JSONPath expressions in column mappings."""
    
    @staticmethod
    def extract_value(row: Dict, path: str) -> Any:
        """Extract value using JSONPath."""
        if path.startswith("$."):
            # It's a JSONPath
            parser = jsonpath_ng.parse(path)
            matches = parser.find(row)
            if matches:
                return [m.value for m in matches]
        else:
            # It's a regular column name
            return row.get(path)
```

**Updated:** `src/rdfmap/models/mapping.py`

```python
class SourceType(str, Enum):
    """Data source types."""
    CSV = "csv"
    XLSX = "xlsx"
    JSON = "json"
    XML = "xml"


class SheetMapping(BaseModel):
    # ... existing fields ...
    source_type: Optional[SourceType] = Field(
        None, 
        description="Source type (auto-detected if omitted)"
    )
    iterator: Optional[str] = Field(
        None,
        description="JSONPath/XPath iterator for hierarchical data"
    )


class ColumnMapping(BaseModel):
    # ... existing fields ...
    path: Optional[str] = Field(
        None,
        description="JSONPath/XPath for nested field access"
    )
```

### Deliverables

- ✅ JSON parser with JSONPath
- ✅ XML parser with XPath
- ✅ Nested field extraction
- ✅ Array handling (multi-valued)
- ✅ Documentation + examples

**Impact:** +0.5 points (hierarchical data support)

---

## 2.3 Conditional Mappings (Month 12)

### Problem

No way to apply different mappings based on row values.

### Solution: Conditional Rules

**New Config Syntax:**

```yaml
sheets:
  - name: people
    source: people.csv
    row_resource:
      class: ex:Person
      iri_template: "{base_iri}person/{id}"
    
    columns:
      age:
        as: ex:age
        datatype: xsd:integer
      
      # Conditional property
      status:
        rules:
          - condition: "age >= 18"
            as: ex:status
            value: "Adult"
            datatype: xsd:string
          
          - condition: "age < 18"
            as: ex:status
            value: "Minor"
            datatype: xsd:string
          
          - condition: "age >= 65"
            as: ex:seniorStatus
            value: "Senior"
            datatype: xsd:string
```

### Implementation

**New Module:** `src/rdfmap/rules/conditional.py`

```python
"""Conditional mapping rules."""

from typing import Any, Dict
import ast
import operator

class ConditionalRule:
    """Evaluate conditional expressions."""
    
    OPERATORS = {
        ast.Eq: operator.eq,
        ast.NotEq: operator.ne,
        ast.Lt: operator.lt,
        ast.LtE: operator.le,
        ast.Gt: operator.gt,
        ast.GtE: operator.ge,
        ast.In: lambda x, y: x in y,
        ast.NotIn: lambda x, y: x not in y,
    }
    
    def __init__(self, condition: str):
        self.condition = condition
        self.parsed = ast.parse(condition, mode="eval")
    
    def evaluate(self, row: Dict[str, Any]) -> bool:
        """Evaluate condition against row data."""
        return self._eval_node(self.parsed.body, row)
    
    def _eval_node(self, node, row: Dict) -> Any:
        """Recursively evaluate AST node."""
        if isinstance(node, ast.Compare):
            left = self._eval_node(node.left, row)
            for op, comparator in zip(node.ops, node.comparators):
                right = self._eval_node(comparator, row)
                op_func = self.OPERATORS.get(type(op))
                if op_func and not op_func(left, right):
                    return False
            return True
        
        elif isinstance(node, ast.Name):
            # Variable reference (column name)
            return row.get(node.id)
        
        elif isinstance(node, ast.Constant):
            # Literal value
            return node.value
        
        elif isinstance(node, ast.BinOp):
            # Binary operation
            left = self._eval_node(node.left, row)
            right = self._eval_node(node.right, row)
            # ... handle operators ...
        
        else:
            raise ValueError(f"Unsupported expression: {ast.dump(node)}")
```

### Deliverables

- ✅ Conditional rule engine
- ✅ Safe expression evaluation
- ✅ Documentation with examples
- ✅ Complex condition support (AND/OR)

**Impact:** +0.25 points (advanced mapping logic)

---

# Phase 3: Ecosystem Leadership (12-18 months)

**Goal:** Become the go-to tool for semantic data mapping  
**Impact:** Innovation score → **9.5-10/10**

## 3.1 Database Connectors

### Support

- PostgreSQL
- MySQL
- SQLite
- MongoDB
- Neo4j

**Config Example:**

```yaml
sheets:
  - name: customers
    source: 
      type: postgresql
      connection: "postgresql://localhost/mydb"
      query: "SELECT * FROM customers"
    # ... rest of mapping ...
```

**Impact:** +0.25 points

---

## 3.2 Streaming & Incremental Updates

### Features

- Process billion-row datasets
- Incremental updates (only changed rows)
- Delta detection
- Versioned graphs

**Command:**
```bash
rdfmap convert --mapping config.yaml --incremental --since "2024-01-01"
```

**Impact:** +0.15 points

---

## 3.3 GUI / Web Interface

### Features

- Visual mapping editor
- Drag-and-drop ontology alignment
- Preview pane
- Validation feedback

**Tech Stack:**
- FastAPI backend
- React frontend
- D3.js for visualizations

**Impact:** +0.1 points (accessibility)

---

## 3.4 Cloud Deployment

### Features

- Docker images
- Kubernetes operators
- AWS/GCP/Azure marketplace
- SaaS offering

**Impact:** Adoption, not innovation score

---

# Summary: Path to 10/10

## Phase 1 (3-6 months): **+1.0 point** → 8.5-9.0/10
- ✅ RML export (weeks 1-4)
- ✅ RML import (weeks 5-10)
- ✅ Standards documentation (weeks 11-12)

## Phase 2 (6-12 months): **+1.0 point** → 9.0-9.5/10
- ✅ Multi-source support (months 7-9)
- ✅ JSON/XML support (months 10-12)
- ✅ Conditional mappings (month 12)

## Phase 3 (12-18 months): **+0.5 points** → 9.5-10/10
- ✅ Database connectors
- ✅ Streaming/incremental
- ✅ GUI
- ✅ Cloud deployment

---

# Priority Recommendations

## Must Do (High ROI):
1. **RML Export** (Phase 1.1) - Marketing + standards compliance
2. **Multi-Source** (Phase 2.1) - Closes major capability gap
3. **JSON Support** (Phase 2.2) - Modern data formats

## Should Do (Medium ROI):
4. **RML Import** (Phase 1.2) - User migration path
5. **Database Connectors** (Phase 3.1) - Enterprise adoption

## Nice to Have (Lower ROI):
6. **Conditional Mappings** (Phase 2.3) - Power users
7. **GUI** (Phase 3.3) - Accessibility
8. **Cloud** (Phase 3.4) - Distribution

---

# Investment Analysis

| Phase | Effort | Impact | ROI |
|-------|--------|--------|-----|
| 1.1 (RML Export) | 3 weeks | +0.5 points | ⭐⭐⭐⭐⭐ |
| 1.2 (RML Import) | 6 weeks | +0.5 points | ⭐⭐⭐⭐ |
| 2.1 (Multi-Source) | 12 weeks | +0.5 points | ⭐⭐⭐⭐ |
| 2.2 (JSON/XML) | 12 weeks | +0.5 points | ⭐⭐⭐⭐ |
| 2.3 (Conditional) | 4 weeks | +0.25 points | ⭐⭐⭐ |
| 3.1 (Databases) | 8 weeks | +0.25 points | ⭐⭐⭐ |
| 3.2 (Streaming) | 6 weeks | +0.15 points | ⭐⭐ |
| 3.3 (GUI) | 16 weeks | +0.1 points | ⭐⭐ |

**Total to 10/10:** ~67 weeks (~16 months) of focused development

---

# Next Steps

## Immediate Actions (This Month):

1. **Implement RML Export (Phase 1.1)**
   - Start with basic TriplesMap generation
   - Test with RMLMapper for validation
   - Document compatibility

2. **Write Academic Paper**
   - Focus on auto-generation innovation
   - Submit to ISWC or ESWC
   - Get citations

3. **Engage W3C Community**
   - Join RML Community Group
   - Present at conference
   - Build relationships

## Success Metrics:

- ✅ "W3C RML Compatible" badge on GitHub
- ✅ 1000+ GitHub stars
- ✅ Academic citation
- ✅ Enterprise adoption (3+ companies)
- ✅ Listed on RML tools page
- ✅ 10/10 innovation score

---

**You've built something genuinely innovative. This roadmap shows the path to making it undeniably best-in-class.**
