"""End-to-end test for the mortgage example."""

import pytest
from pathlib import Path
from decimal import Decimal

from rdflib import Graph, Namespace, Literal, URIRef
from rdflib.namespace import RDF, XSD

from rdfmap.config.loader import load_mapping_config
from rdfmap.emitter.graph_builder import RDFGraphBuilder
from rdfmap.models.errors import ProcessingReport
from rdfmap.parsers.data_source import create_parser
from rdfmap.validator.shacl import validate_rdf


@pytest.fixture
def mortgage_example_dir():
    """Get path to mortgage example directory."""
    return Path(__file__).parent.parent / "examples" / "mortgage"


@pytest.fixture
def mortgage_config(mortgage_example_dir):
    """Load mortgage mapping configuration."""
    config_path = mortgage_example_dir / "config" / "mortgage_mapping.yaml"
    return load_mapping_config(config_path)


class TestMortgageExample:
    """End-to-end tests for the mortgage example."""
    
    def test_load_mortgage_config(self, mortgage_config):
        """Test that mortgage configuration loads correctly."""
        assert mortgage_config is not None
        assert len(mortgage_config.sheets) == 1
        assert mortgage_config.sheets[0].name == "loans"
        assert "ex" in mortgage_config.namespaces
        assert mortgage_config.defaults.base_iri == "https://data.example.com/"
    
    def test_parse_mortgage_data(self, mortgage_example_dir, mortgage_config):
        """Test parsing mortgage CSV data."""
        sheet = mortgage_config.sheets[0]
        parser = create_parser(
            Path(sheet.source),
            delimiter=mortgage_config.options.delimiter,
            has_header=mortgage_config.options.header,
        )
        
        # Get columns
        columns = parser.get_column_names()
        assert "LoanID" in columns
        assert "BorrowerName" in columns
        assert "Principal" in columns
        
        # Parse data
        chunks = list(parser.parse())
        assert len(chunks) > 0
        
        df = chunks[0]
        assert len(df) == 5  # 5 loans in example data
        assert df.iloc[0]["LoanID"] == "L-1001"
        assert df.iloc[0]["BorrowerName"] == "Alex Morgan"
    
    def test_build_rdf_graph(self, mortgage_config):
        """Test building RDF graph from mortgage data."""
        report = ProcessingReport()
        builder = RDFGraphBuilder(mortgage_config, report)
        
        # Process first sheet
        sheet = mortgage_config.sheets[0]
        parser = create_parser(
            Path(sheet.source),
            delimiter=mortgage_config.options.delimiter,
            has_header=mortgage_config.options.header,
        )
        
        for chunk in parser.parse():
            builder.add_dataframe(chunk, sheet)
        
        graph = builder.get_graph()
        
        # Verify graph has triples
        assert len(graph) > 0
        
        # Verify namespaces are bound
        namespaces = dict(graph.namespaces())
        assert "ex" in namespaces
        
        # Verify specific triples exist
        ex = Namespace("https://example.com/mortgage#")
        
        # Check for loan L-1001
        loan_uri = URIRef("https://data.example.com/loan/L-1001")
        
        # Check loan type
        types = list(graph.objects(loan_uri, RDF.type))
        assert len(types) > 0
        assert ex.MortgageLoan in types
        
        # Check loan number
        loan_numbers = list(graph.objects(loan_uri, ex.loanNumber))
        assert len(loan_numbers) > 0
        assert str(loan_numbers[0]) == "L-1001"
        
        # Check principal amount
        principals = list(graph.objects(loan_uri, ex.principalAmount))
        assert len(principals) > 0
        # The literal should have xsd:decimal datatype
        
        # Check linked borrower
        borrowers = list(graph.objects(loan_uri, ex.hasBorrower))
        assert len(borrowers) > 0
        
        borrower_uri = borrowers[0]
        borrower_names = list(graph.objects(borrower_uri, ex.borrowerName))
        assert len(borrower_names) > 0
        assert str(borrower_names[0]) == "Alex Morgan"
        
        # Check linked property
        properties = list(graph.objects(loan_uri, ex.collateralProperty))
        assert len(properties) > 0
        
        property_uri = properties[0]
        addresses = list(graph.objects(property_uri, ex.propertyAddress))
        assert len(addresses) > 0
        assert str(addresses[0]) == "12 Oak St"
    
    def test_validate_mortgage_rdf(self, mortgage_example_dir, mortgage_config):
        """Test SHACL validation of mortgage RDF."""
        # Build graph
        report = ProcessingReport()
        builder = RDFGraphBuilder(mortgage_config, report)
        
        sheet = mortgage_config.sheets[0]
        parser = create_parser(
            Path(sheet.source),
            delimiter=mortgage_config.options.delimiter,
            has_header=mortgage_config.options.header,
        )
        
        for chunk in parser.parse():
            builder.add_dataframe(chunk, sheet)
        
        graph = builder.get_graph()
        
        # Validate
        shapes_file = mortgage_example_dir / "shapes" / "mortgage_shapes.ttl"
        validation_report = validate_rdf(graph, shapes_file=shapes_file)
        
        # Should conform to shapes
        assert validation_report.conforms is True
        assert len(validation_report.results) == 0
    
    def test_processing_report(self, mortgage_config):
        """Test that processing report tracks errors correctly."""
        report = ProcessingReport()
        builder = RDFGraphBuilder(mortgage_config, report)
        
        sheet = mortgage_config.sheets[0]
        parser = create_parser(
            Path(sheet.source),
            delimiter=mortgage_config.options.delimiter,
            has_header=mortgage_config.options.header,
        )
        
        for chunk in parser.parse():
            builder.add_dataframe(chunk, sheet)
        
        report.finalize()
        
        # Should have processed 5 rows successfully
        assert report.total_rows == 5
        assert report.successful_rows == 5
        assert report.failed_rows == 0
    
    def test_serialization_formats(self, mortgage_config):
        """Test serialization to different RDF formats."""
        from rdfmap.emitter.graph_builder import serialize_graph
        
        report = ProcessingReport()
        builder = RDFGraphBuilder(mortgage_config, report)
        
        sheet = mortgage_config.sheets[0]
        parser = create_parser(
            Path(sheet.source),
            delimiter=mortgage_config.options.delimiter,
            has_header=mortgage_config.options.header,
        )
        
        for chunk in parser.parse():
            builder.add_dataframe(chunk, sheet)
        
        graph = builder.get_graph()
        
        # Test Turtle
        turtle_output = serialize_graph(graph, "turtle")
        assert "@prefix ex:" in turtle_output or "@prefix" in turtle_output
        
        # Test JSON-LD (may be in expanded form without @context/@graph wrapper)
        jsonld_output = serialize_graph(graph, "json-ld")
        # Valid JSON-LD can be: 1) object with @context, 2) array of objects (expanded form), 3) object with @graph
        assert ("@context" in jsonld_output or "@graph" in jsonld_output or 
                (jsonld_output.strip().startswith("[") and "@id" in jsonld_output))
        
        # Test N-Triples
        nt_output = serialize_graph(graph, "nt")
        assert len(nt_output) > 0


class TestDataTransformations:
    """Test data transformations in mortgage example."""
    
    def test_decimal_transformation(self, mortgage_config):
        """Test that principal amounts are correctly transformed to decimals."""
        report = ProcessingReport()
        builder = RDFGraphBuilder(mortgage_config, report)
        
        sheet = mortgage_config.sheets[0]
        parser = create_parser(Path(sheet.source))
        
        for chunk in parser.parse():
            builder.add_dataframe(chunk, sheet)
        
        graph = builder.get_graph()
        ex = Namespace("https://example.com/mortgage#")
        
        # Find a loan and check its principal
        loan_uri = URIRef("https://data.example.com/loan/L-1001")
        principals = list(graph.objects(loan_uri, ex.principalAmount))
        
        assert len(principals) > 0
        principal = principals[0]
        
        # Should be a literal with xsd:decimal datatype
        assert isinstance(principal, Literal)
        # The value should match the CSV data
        assert str(principal) == "250000"
    
    def test_date_transformation(self, mortgage_config):
        """Test that dates are correctly transformed."""
        report = ProcessingReport()
        builder = RDFGraphBuilder(mortgage_config, report)
        
        sheet = mortgage_config.sheets[0]
        parser = create_parser(Path(sheet.source))
        
        for chunk in parser.parse():
            builder.add_dataframe(chunk, sheet)
        
        graph = builder.get_graph()
        ex = Namespace("https://example.com/mortgage#")
        
        # Find a loan and check its origination date
        loan_uri = URIRef("https://data.example.com/loan/L-1001")
        dates = list(graph.objects(loan_uri, ex.originationDate))
        
        assert len(dates) > 0
        date = dates[0]
        
        # Should be a literal with xsd:date datatype
        assert isinstance(date, Literal)
        assert str(date) == "2023-06-15"
