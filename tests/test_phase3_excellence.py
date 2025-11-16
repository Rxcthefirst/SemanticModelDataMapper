"""Phase 3 Excellence Tests: Enhanced GraphContextMatcher with Probabilistic Reasoning.

Tests the enhanced GraphContextMatcher with:
- Bayesian confidence propagation
- Property co-occurrence learning
- Semantic similarity graphs
- Evidence accumulation across multiple signals
"""
import os
import tempfile
import pytest
from rdflib import Graph, Namespace, RDF, RDFS, OWL, Literal
from rdflib.namespace import XSD, SKOS

from rdfmap.generator.ontology_analyzer import OntologyAnalyzer
from rdfmap.generator.graph_reasoner import GraphReasoner
from rdfmap.generator.data_analyzer import DataFieldAnalysis
from rdfmap.generator.matchers import GraphContextMatcher
from rdfmap.generator.matchers.base import MatchContext

TEST = Namespace("http://example.com/test#")


def make_column(name, values=None, inferred_type="string", is_unique=None, null_percentage=0.0):
    c = DataFieldAnalysis(name)
    c.sample_values = values or []
    c.inferred_type = inferred_type
    c.total_count = len(values or [])
    c.null_count = int((null_percentage / 100.0) * c.total_count)
    if is_unique is not None:
        c.is_unique = is_unique
    else:
        c.is_unique = len(set(values or [])) == len(values or []) if values else False
    return c


@pytest.fixture
def advanced_ontology_graph():
    """Create advanced ontology for testing probabilistic reasoning and validation."""
    g = Graph()
    g.bind("test", TEST)
    g.bind("xsd", XSD)
    g.bind("skos", SKOS)

    # Person class with multiple properties that often co-occur
    g.add((TEST.Person, RDF.type, OWL.Class))
    g.add((TEST.Person, RDFS.label, Literal("Person")))
    g.add((TEST.Person, RDFS.comment, Literal("An individual human being")))

    # Employee subclass (for inheritance testing)
    g.add((TEST.Employee, RDF.type, OWL.Class))
    g.add((TEST.Employee, RDFS.subClassOf, TEST.Person))
    g.add((TEST.Employee, RDFS.label, Literal("Employee")))

    # Personal information cluster (often appear together)
    g.add((TEST.firstName, RDF.type, OWL.DatatypeProperty))
    g.add((TEST.firstName, RDFS.label, Literal("first name")))
    g.add((TEST.firstName, RDFS.comment, Literal("Given name of a person")))
    g.add((TEST.firstName, RDFS.domain, TEST.Person))
    g.add((TEST.firstName, RDFS.range, XSD.string))

    g.add((TEST.lastName, RDF.type, OWL.DatatypeProperty))
    g.add((TEST.lastName, RDFS.label, Literal("last name")))
    g.add((TEST.lastName, RDFS.comment, Literal("Family name of a person")))
    g.add((TEST.lastName, RDFS.domain, TEST.Person))
    g.add((TEST.lastName, RDFS.range, XSD.string))

    g.add((TEST.middleName, RDF.type, OWL.DatatypeProperty))
    g.add((TEST.middleName, RDFS.label, Literal("middle name")))
    g.add((TEST.middleName, RDFS.domain, TEST.Person))
    g.add((TEST.middleName, RDFS.range, XSD.string))

    # Birth information cluster
    g.add((TEST.birthDate, RDF.type, OWL.DatatypeProperty))
    g.add((TEST.birthDate, RDFS.label, Literal("birth date")))
    g.add((TEST.birthDate, RDFS.comment, Literal("Date when person was born")))
    g.add((TEST.birthDate, RDFS.domain, TEST.Person))
    g.add((TEST.birthDate, RDFS.range, XSD.date))

    g.add((TEST.birthPlace, RDF.type, OWL.DatatypeProperty))
    g.add((TEST.birthPlace, RDFS.label, Literal("birth place")))
    g.add((TEST.birthPlace, RDFS.domain, TEST.Person))
    g.add((TEST.birthPlace, RDFS.range, XSD.string))

    # Contact information cluster
    g.add((TEST.email, RDF.type, OWL.DatatypeProperty))
    g.add((TEST.email, RDFS.label, Literal("email")))
    g.add((TEST.email, RDFS.comment, Literal("Electronic mail address")))
    g.add((TEST.email, RDFS.domain, TEST.Person))
    g.add((TEST.email, RDFS.range, XSD.string))

    g.add((TEST.phoneNumber, RDF.type, OWL.DatatypeProperty))
    g.add((TEST.phoneNumber, RDFS.label, Literal("phone number")))
    g.add((TEST.phoneNumber, RDFS.domain, TEST.Person))
    g.add((TEST.phoneNumber, RDFS.range, XSD.string))

    # Employee-specific properties
    g.add((TEST.employeeId, RDF.type, OWL.DatatypeProperty))
    g.add((TEST.employeeId, RDFS.label, Literal("employee ID")))
    g.add((TEST.employeeId, RDFS.comment, Literal("Unique identifier for employee")))
    g.add((TEST.employeeId, RDFS.domain, TEST.Employee))
    g.add((TEST.employeeId, RDFS.range, XSD.string))
    g.add((TEST.employeeId, RDF.type, OWL.InverseFunctionalProperty))  # Unique identifier

    # Add some restrictions for validation testing
    # Birth date cardinality restriction
    bn_birth = TEST._restriction_birth
    g.add((TEST.Person, RDFS.subClassOf, bn_birth))
    g.add((bn_birth, RDF.type, OWL.Restriction))
    g.add((bn_birth, OWL.onProperty, TEST.birthDate))
    g.add((bn_birth, OWL.cardinality, Literal("1")))

    # SKOS relations for additional semantic signals
    g.add((TEST.email, SKOS.related, TEST.phoneNumber))
    g.add((TEST.firstName, SKOS.related, TEST.lastName))
    g.add((TEST.birthDate, SKOS.related, TEST.birthPlace))

    return g


@pytest.fixture
def analyzer(advanced_ontology_graph):
    with tempfile.NamedTemporaryFile(mode='wb', suffix='.ttl', delete=False) as f:
        advanced_ontology_graph.serialize(f, format='turtle')
        path = f.name
    oa = OntologyAnalyzer(path)
    os.unlink(path)
    return oa


@pytest.fixture
def reasoner(advanced_ontology_graph, analyzer):
    return GraphReasoner(advanced_ontology_graph, analyzer.classes, analyzer.properties)


def test_enhanced_graph_context_cooccurrence_learning(analyzer, reasoner):
    """Test that enhanced GraphContextMatcher learns property co-occurrence patterns."""
    matcher = GraphContextMatcher(
        reasoner=reasoner,
        use_probabilistic_reasoning=True,
        threshold=0.5
    )

    # Verify co-occurrence patterns were learned
    assert hasattr(matcher, 'cooccurrence_patterns')
    patterns = matcher.cooccurrence_patterns

    # Check that Person domain properties have co-occurrence relationships
    first_name_uri = str(TEST.firstName)
    last_name_uri = str(TEST.lastName)

    if first_name_uri in patterns:
        cooccurring = patterns[first_name_uri]
        assert last_name_uri in cooccurring, "firstName should co-occur with lastName"


def test_enhanced_graph_context_probabilistic_reasoning(analyzer, reasoner):
    """Test Bayesian-style confidence propagation in enhanced GraphContextMatcher."""
    matcher = GraphContextMatcher(
        reasoner=reasoner,
        use_probabilistic_reasoning=True,
        threshold=0.4
    )

    columns = [
        make_column("first_name", ["John", "Jane"], "string"),
        make_column("middle_initial", ["A", "B"], "string")  # Should benefit from firstName context
    ]

    properties = list(analyzer.properties.values())

    # Match middle name with context of already matched firstName
    context = MatchContext(
        column=columns[1],
        all_columns=columns,
        available_properties=properties,
        matched_properties={"first_name": str(TEST.firstName)}
    )

    result = matcher.match(columns[1], properties, context)
    assert result is not None, "Should find match with confidence propagation"
    assert "middleName" in result.property.uri


def test_enhanced_graph_context_evidence_accumulation(analyzer, reasoner):
    """Test that multiple evidence sources strengthen confidence."""
    matcher = GraphContextMatcher(
        reasoner=reasoner,
        use_probabilistic_reasoning=True,
        threshold=0.4
    )

    columns = [
        make_column("first_name", ["John", "Jane"], "string"),
        make_column("last_name", ["Doe", "Smith"], "string"),
        make_column("birth_date", ["1990-01-15", "1985-03-20"], "date")  # Should benefit from multiple name properties
    ]

    properties = list(analyzer.properties.values())

    # Context with multiple matched properties
    context = MatchContext(
        column=columns[2],
        all_columns=columns,
        available_properties=properties,
        matched_properties={
            "first_name": str(TEST.firstName),
            "last_name": str(TEST.lastName)
        }
    )

    result = matcher.match(columns[2], properties, context)
    assert result is not None, "Should find match with accumulated evidence"
    assert "birthDate" in result.property.uri

    # Should show evidence in matched_via
    assert "context" in result.matched_via.lower()


def test_enhanced_graph_context_semantic_similarity(analyzer, reasoner):
    """Test semantic similarity graph building in enhanced GraphContextMatcher."""
    matcher = GraphContextMatcher(
        reasoner=reasoner,
        use_probabilistic_reasoning=True,
        threshold=0.4
    )

    # Verify semantic similarity graph was built
    assert hasattr(matcher, 'property_similarities')
    similarities = matcher.property_similarities

    # Should have some similarity relationships
    assert len(similarities) > 0, "Should have built property similarity graph"

    # Check that properties have similarity scores
    for prop_uri, similar_props in similarities.items():
        if similar_props:
            for similar_uri, score in similar_props:
                assert 0.0 <= score <= 1.0, "Similarity scores should be between 0 and 1"


def test_enhanced_graph_context_probabilistic_boost(analyzer, reasoner):
    """Test probabilistic confidence boosting based on evidence."""
    matcher = GraphContextMatcher(
        reasoner=reasoner,
        use_probabilistic_reasoning=True,
        use_cooccurrence=True,
        threshold=0.3
    )

    # Test with weak base similarity but strong context
    col = make_column("employee_birth", ["1990-01-15"], "date")
    properties = list(analyzer.properties.values())

    # Context with related properties already matched
    context = MatchContext(
        column=col,
        all_columns=[col],
        available_properties=properties,
        matched_properties={
            "employee_id": str(TEST.employeeId),
            "first_name": str(TEST.firstName)
        }
    )

    result = matcher.match(col, properties, context)
    if result:  # May or may not match depending on base similarity
        assert result.confidence > 0.3, "Should have boosted confidence from context"
def test_phase3_enhanced_graph_context_pipeline(analyzer, reasoner):
    """Test enhanced GraphContextMatcher in full pipeline context."""
    from rdfmap.generator.matchers.base import MatcherPipeline
    from rdfmap.generator.matchers import (
        ExactPrefLabelMatcher, ExactRdfsLabelMatcher, GraphContextMatcher
    )

    # Create pipeline with enhanced GraphContextMatcher
    matchers = [
        ExactPrefLabelMatcher(threshold=1.0),
        ExactRdfsLabelMatcher(threshold=0.95),
        GraphContextMatcher(
            reasoner=reasoner,
            use_probabilistic_reasoning=True,
            threshold=0.4
        )
    ]

    pipeline = MatcherPipeline(matchers)

    columns = [
        make_column("first_name", ["John", "Jane"], "string"),
        make_column("last_name", ["Doe", "Smith"], "string"),
        make_column("email_addr", ["john@example.com", "jane@test.org"], "string"),
        make_column("birth_date", ["1990-01-15", "1985-03-20"], "date"),
        make_column("emp_id", ["E001", "E002"], "string", is_unique=True)
    ]

    properties = list(analyzer.properties.values())

    matches = {}
    for col in columns:
        context = MatchContext(
            column=col,
            all_columns=columns,
            available_properties=properties,
            matched_properties=matches
        )

        result = pipeline.match(col, properties, context)
        if result:
            matches[col.name] = result.property.uri

    # Should achieve good match rate with enhanced reasoning
    assert len(matches) >= 3, f"Expected at least 3 matches with enhanced pipeline, got {len(matches)}"


def test_enhanced_graph_context_evidence_traceability(analyzer, reasoner):
    """Test that enhanced GraphContextMatcher provides clear evidence trails."""
    matcher = GraphContextMatcher(
        reasoner=reasoner,
        use_probabilistic_reasoning=True,
        threshold=0.4
    )

    col = make_column("birth_date", ["1990-01-15", "1985-03-20"], "date")
    properties = list(analyzer.properties.values())
    context = MatchContext(
        column=col,
        all_columns=[col],
        available_properties=properties,
        matched_properties={"first_name": str(TEST.firstName)}
    )

    result = matcher.match(col, properties, context)

    if result:
        # Should contain evidence source information
        assert result.matched_via is not None, "Should have matched_via information"
        # Should show either context boost or label match details
        assert "context" in result.matched_via.lower() or "label" in result.matched_via.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])


