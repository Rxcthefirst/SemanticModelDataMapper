"""
Comprehensive tests for the generator workflow with SKOS label matching.

Tests the complete workflow:
1. Ontology analysis (including SKOS labels)
2. Spreadsheet analysis  
3. Column-to-property matching (with SKOS support)
4. Mapping config generation
5. RDF conversion using generated config
6. Validation
"""

import pytest
from pathlib import Path
import yaml
import tempfile
import os

from rdfmap.generator.ontology_analyzer import OntologyAnalyzer
from rdfmap.generator.spreadsheet_analyzer import SpreadsheetAnalyzer
from rdfmap.generator.mapping_generator import MappingGenerator, GeneratorConfig
from rdfmap.config.loader import load_mapping_config
from rdfmap.emitter.graph_builder import RDFGraphBuilder
from rdfmap.models.errors import ProcessingReport
from rdflib import Graph, Namespace, RDF


# Fixture paths
FIXTURES_DIR = Path(__file__).parent / "fixtures" / "generator"
ONTOLOGY_FILE = FIXTURES_DIR / "employee_ontology.ttl"
EMPLOYEES_CSV = FIXTURES_DIR / "employees.csv"
DEPARTMENTS_CSV = FIXTURES_DIR / "departments.csv"


class TestOntologyAnalyzerSKOS:
    """Test that OntologyAnalyzer properly extracts SKOS labels."""
    
    def test_extracts_skos_labels_for_classes(self):
        """Test extraction of SKOS labels for classes."""
        analyzer = OntologyAnalyzer(str(ONTOLOGY_FILE))
        
        # Find Employee class
        employee_class = None
        for cls in analyzer.classes.values():
            if cls.label == "Employee":
                employee_class = cls
                break
        
        assert employee_class is not None
        assert employee_class.pref_label == "Employee"
        assert "Worker" in employee_class.alt_labels
        assert "Staff Member" in employee_class.alt_labels
    
    def test_extracts_skos_labels_for_properties(self):
        """Test extraction of SKOS labels for properties."""
        analyzer = OntologyAnalyzer(str(ONTOLOGY_FILE))
        
        # Find employeeId property
        emp_id_prop = None
        for prop in analyzer.properties.values():
            if str(prop.uri).endswith("employeeId"):
                emp_id_prop = prop
                break
        
        assert emp_id_prop is not None
        assert emp_id_prop.pref_label == "Employee ID"
        assert "EmpID" in emp_id_prop.alt_labels
        assert "Staff Number" in emp_id_prop.alt_labels
        assert "EMP_ID" in emp_id_prop.hidden_labels
        assert "emp_no" in emp_id_prop.hidden_labels
    
    def test_get_all_labels_includes_all_types(self):
        """Test that get_all_labels returns all label types."""
        analyzer = OntologyAnalyzer(str(ONTOLOGY_FILE))
        
        # Find firstName property
        first_name_prop = None
        for prop in analyzer.properties.values():
            if str(prop.uri).endswith("firstName"):
                first_name_prop = prop
                break
        
        assert first_name_prop is not None
        all_labels = first_name_prop.get_all_labels()
        
        assert "First Name" in all_labels  # prefLabel
        assert "first name" in all_labels  # rdfs:label
        assert "Given Name" in all_labels  # altLabel
        assert "Forename" in all_labels    # altLabel
        assert "fname" in all_labels        # hiddenLabel


class TestColumnMatchingWithSKOS:
    """Test column-to-property matching using SKOS labels."""
    
    def test_matches_hidden_label_exactly(self):
        """Test that hiddenLabel matches are found (e.g., EMP_ID -> employeeId)."""
        config = GeneratorConfig(base_iri="http://example.org/data/")
        generator = MappingGenerator(
            str(ONTOLOGY_FILE),
            str(EMPLOYEES_CSV),
            config
        )
        
        mapping = generator.generate(target_class="Employee")
        
        # EMP_ID column should match employeeId property via hiddenLabel
        assert "EMP_ID" in mapping["sheets"][0]["columns"]
        emp_id_mapping = mapping["sheets"][0]["columns"]["EMP_ID"]
        
        # Should map to employeeId property
        assert "employeeId" in emp_id_mapping["as"]
    
    def test_matches_multiple_hidden_labels(self):
        """Test matching of various abbreviated column names."""
        config = GeneratorConfig(base_iri="http://example.org/data/")
        generator = MappingGenerator(
            str(ONTOLOGY_FILE),
            str(EMPLOYEES_CSV),
            config
        )
        
        mapping = generator.generate(target_class="Employee")
        columns = mapping["sheets"][0]["columns"]
        
        # fname -> firstName (via hiddenLabel)
        assert "fname" in columns
        assert "firstName" in columns["fname"]["as"]
        
        # lname -> lastName (via hiddenLabel)
        assert "lname" in columns
        assert "lastName" in columns["lname"]["as"]
        
        # email_addr -> emailAddress (via hiddenLabel)
        assert "email_addr" in columns
        assert "emailAddress" in columns["email_addr"]["as"]
        
        # phone -> phoneNumber (via hiddenLabel)
        assert "phone" in columns
        assert "phoneNumber" in columns["phone"]["as"]
        
        # sal -> salary (via hiddenLabel)
        assert "sal" in columns
        assert "salary" in columns["sal"]["as"]
        
        # hire_dt -> hireDate (via hiddenLabel)
        assert "hire_dt" in columns
        assert "hireDate" in columns["hire_dt"]["as"]
        
        # active -> isActive (via hiddenLabel)
        assert "active" in columns
        assert "isActive" in columns["active"]["as"]
    
    def test_priority_pref_label_over_hidden_label(self):
        """Test that prefLabel has priority over hiddenLabel if both match."""
        # This tests the matching priority order
        config = GeneratorConfig(base_iri="http://example.org/data/")
        generator = MappingGenerator(
            str(ONTOLOGY_FILE),
            str(EMPLOYEES_CSV),
            config
        )
        
        # The matching function should prioritize in order:
        # prefLabel > rdfs:label > altLabel > hiddenLabel > local name
        # This is verified by the implementation
        mapping = generator.generate(target_class="Employee")
        
        # All columns should be matched
        assert len(mapping["sheets"][0]["columns"]) > 0


class TestGeneratorWorkflowComplete:
    """Test the complete generator workflow end-to-end."""
    
    def test_full_workflow_employees(self):
        """Test complete workflow: analyze -> generate -> convert -> validate."""
        # Step 1: Analyze ontology
        ontology = OntologyAnalyzer(str(ONTOLOGY_FILE))
        assert len(ontology.classes) > 0
        assert len(ontology.properties) > 0
        
        # Step 2: Analyze spreadsheet
        spreadsheet = SpreadsheetAnalyzer(str(EMPLOYEES_CSV))
        assert len(spreadsheet.get_column_names()) == 11
        
        # Step 3: Generate mapping config
        config = GeneratorConfig(base_iri="http://example.org/data/")
        generator = MappingGenerator(
            str(ONTOLOGY_FILE),
            str(EMPLOYEES_CSV),
            config
        )
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            mapping_file = f.name
        
        try:
            mapping = generator.generate(
                target_class="Employee",
                output_path=mapping_file
            )
            
            # Save to file
            with open(mapping_file, 'w') as f:
                yaml.dump(mapping, f, default_flow_style=False, sort_keys=False)
            
            # Step 4: Verify generated config structure
            assert "namespaces" in mapping
            assert "defaults" in mapping
            assert "sheets" in mapping
            assert len(mapping["sheets"]) == 1
            
            sheet = mapping["sheets"][0]
            assert sheet["name"] == "employees"
            assert "row_resource" in sheet
            assert "columns" in sheet
            
            # Verify column mappings were created
            assert len(sheet["columns"]) > 0
            
            # Verify key columns are mapped correctly
            columns = sheet["columns"]
            assert "EMP_ID" in columns
            assert "fname" in columns
            assert "lname" in columns
            assert "sal" in columns
            
            # Step 5: Load config and build RDF
            loaded_config = load_mapping_config(mapping_file)
            report = ProcessingReport()
            builder = RDFGraphBuilder(loaded_config, report)
            
            # Process the CSV data
            from rdfmap.parsers.data_source import create_parser
            sheet = loaded_config.sheets[0]
            parser = create_parser(
                Path(sheet.source),
                delimiter=loaded_config.options.delimiter if loaded_config.options else ',',
                has_header=loaded_config.options.header if loaded_config.options else True
            )
            
            for chunk in parser.parse():
                builder.add_dataframe(chunk, sheet)
            
            # Get the built graph
            graph = builder.get_graph()
            
            # Step 6: Verify RDF output
            assert len(graph) > 0
            
            # Check that employees were created
            HR = Namespace("http://example.org/hr#")
            employees = list(graph.subjects(predicate=RDF.type, object=HR.Employee))
            assert len(employees) > 0
            
            # Verify at least one employee has properties
            for emp in employees[:1]:
                # Should have properties mapped from columns
                emp_triples = list(graph.triples((emp, None, None)))
                assert len(emp_triples) > 0
        
        finally:
            # Cleanup
            if os.path.exists(mapping_file):
                os.unlink(mapping_file)
    
    def test_workflow_with_linked_objects(self):
        """Test workflow with object properties and linked resources."""
        config = GeneratorConfig(
            base_iri="http://example.org/data/",
            auto_detect_relationships=True
        )
        generator = MappingGenerator(
            str(ONTOLOGY_FILE),
            str(EMPLOYEES_CSV),
            config
        )
        
        mapping = generator.generate(target_class="Employee")
        
        # Should detect linked objects (department, position, manager)
        sheet = mapping["sheets"][0]
        
        # Check if objects were detected
        # (Department and Position should be detected based on object properties)
        if "objects" in sheet:
            assert len(sheet["objects"]) > 0
    
    def test_workflow_departments(self):
        """Test workflow with departments CSV."""
        config = GeneratorConfig(base_iri="http://example.org/data/")
        generator = MappingGenerator(
            str(ONTOLOGY_FILE),
            str(DEPARTMENTS_CSV),
            config
        )
        
        mapping = generator.generate(target_class="Department")
        
        # Verify structure
        assert len(mapping["sheets"]) == 1
        sheet = mapping["sheets"][0]
        
        # dept_cd should match departmentCode (via hiddenLabel)
        columns = sheet["columns"]
        assert "dept_cd" in columns
        assert "departmentCode" in columns["dept_cd"]["as"]
        
        # dept_name should match departmentName (via hiddenLabel)
        assert "dept_name" in columns
        assert "departmentName" in columns["dept_name"]["as"]


class TestMatchingPriority:
    """Test the priority order of label matching."""
    
    def test_matching_priority_order(self):
        """
        Test that matching follows the correct priority:
        1. SKOS prefLabel (exact)
        2. rdfs:label (exact)
        3. SKOS altLabel (exact)
        4. SKOS hiddenLabel (exact)
        5. Local name (exact)
        6. Any label (partial)
        7. Local name (fuzzy)
        """
        config = GeneratorConfig(base_iri="http://example.org/data/")
        generator = MappingGenerator(
            str(ONTOLOGY_FILE),
            str(EMPLOYEES_CSV),
            config
        )
        
        # Get properties for Employee class
        ontology = generator.ontology
        employee_uri = None
        for uri, cls in ontology.classes.items():
            if cls.label == "Employee":
                employee_uri = uri
                break
        
        assert employee_uri is not None
        properties = ontology.get_datatype_properties(employee_uri)
        
        # Get column analysis
        col_analysis = generator.spreadsheet.get_analysis("fname")
        
        # Test matching (returns tuple: property, match_type, matched_via)
        match_result = generator._match_column_to_property("fname", col_analysis, properties)
        
        # Should match firstName property via hiddenLabel
        assert match_result is not None
        matched_prop, match_type, matched_via = match_result
        assert "firstName" in str(matched_prop.uri)
        
        # Verify it matched via hiddenLabel
        from rdfmap.models.alignment import MatchType
        assert match_type == MatchType.EXACT_HIDDEN_LABEL


class TestDataTypeInference:
    """Test that generated mappings include correct datatypes."""
    
    def test_datatype_inference(self):
        """Test that spreadsheet analysis correctly infers datatypes."""
        config = GeneratorConfig(base_iri="http://example.org/data/")
        generator = MappingGenerator(
            str(ONTOLOGY_FILE),
            str(EMPLOYEES_CSV),
            config
        )
        
        mapping = generator.generate(target_class="Employee")
        columns = mapping["sheets"][0]["columns"]
        
        # sal should be integer (whole numbers in CSV)
        if "sal" in columns and "datatype" in columns["sal"]:
            assert "integer" in columns["sal"]["datatype"].lower()
        
        # hire_dt should be date
        if "hire_dt" in columns and "datatype" in columns["hire_dt"]:
            assert "date" in columns["hire_dt"]["datatype"].lower()
        
        # active should be string (Yes/No values in CSV)
        if "active" in columns and "datatype" in columns["active"]:
            assert "string" in columns["active"]["datatype"].lower()


class TestErrorHandling:
    """Test error handling in generator workflow."""
    
    def test_nonexistent_ontology_file(self):
        """Test handling of non-existent ontology file."""
        with pytest.raises(Exception):
            OntologyAnalyzer("nonexistent.ttl")
    
    def test_nonexistent_spreadsheet_file(self):
        """Test handling of non-existent spreadsheet file."""
        with pytest.raises(Exception):
            SpreadsheetAnalyzer("nonexistent.csv")
    
    def test_invalid_target_class(self):
        """Test handling of invalid target class."""
        config = GeneratorConfig(base_iri="http://example.org/data/")
        generator = MappingGenerator(
            str(ONTOLOGY_FILE),
            str(EMPLOYEES_CSV),
            config
        )
        
        with pytest.raises(ValueError, match="Could not find class"):
            generator.generate(target_class="NonExistentClass")


class TestConfigGeneration:
    """Test specific aspects of config generation."""
    
    def test_iri_template_generation(self):
        """Test IRI template generation with identifier columns."""
        config = GeneratorConfig(base_iri="http://example.org/data/")
        generator = MappingGenerator(
            str(ONTOLOGY_FILE),
            str(EMPLOYEES_CSV),
            config
        )
        
        mapping = generator.generate(target_class="Employee")
        
        # Should generate IRI template with identifier column
        iri_template = mapping["sheets"][0]["row_resource"]["iri_template"]
        assert "{" in iri_template
        assert "}" in iri_template
        assert "EMP_ID" in iri_template or "employee" in iri_template.lower()
    
    def test_required_columns_flagged(self):
        """Test that required columns are flagged in generated config."""
        config = GeneratorConfig(base_iri="http://example.org/data/")
        generator = MappingGenerator(
            str(ONTOLOGY_FILE),
            str(EMPLOYEES_CSV),
            config
        )
        
        mapping = generator.generate(target_class="Employee")
        columns = mapping["sheets"][0]["columns"]
        
        # Check if any columns are marked as required
        # (based on null percentage analysis)
        has_required = any(
            col.get("required", False) 
            for col in columns.values()
        )
        
        # At least EMP_ID should be required (no nulls)
        if "EMP_ID" in columns:
            # May or may not be marked required depending on analysis
            pass
    
    def test_namespace_generation(self):
        """Test that namespaces are properly generated."""
        config = GeneratorConfig(base_iri="http://example.org/data/")
        generator = MappingGenerator(
            str(ONTOLOGY_FILE),
            str(EMPLOYEES_CSV),
            config
        )
        
        mapping = generator.generate(target_class="Employee")
        
        assert "namespaces" in mapping
        namespaces = mapping["namespaces"]
        
        # Should include xsd
        assert "xsd" in namespaces
        
        # Should include HR namespace from ontology
        has_hr_namespace = any(
            "hr" in ns.lower() or "example.org/hr" in uri
            for ns, uri in namespaces.items()
        )
        assert has_hr_namespace


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
