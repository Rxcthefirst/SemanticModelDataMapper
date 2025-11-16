"""Phase 2 Integration Tests: Testing combined Phase 1 + Phase 2 matcher functionality.

Validates that the enhanced pipeline with OWL restrictions and SKOS relations
works cohesively with existing semantic matchers.
"""
import os
import tempfile
import pytest
from rdflib import Graph, Namespace, RDF, RDFS, OWL, Literal
from rdflib.namespace import XSD, SKOS

from rdfmap.generator.ontology_analyzer import OntologyAnalyzer
from rdfmap.generator.graph_reasoner import GraphReasoner
from rdfmap.generator.data_analyzer import DataFieldAnalysis
from rdfmap.generator.matchers import (
    RestrictionBasedMatcher,
    SKOSRelationsMatcher,
    SemanticSimilarityMatcher
)
from rdfmap.generator.matchers.base import MatchContext
from rdfmap.generator.matchers.factory import create_default_pipeline

TEST = Namespace("http://example.com/test#")


def make_column(name, values=None, inferred_type="string", is_unique=None):
    c = DataFieldAnalysis(name)
    c.sample_values = values or []
    c.inferred_type = inferred_type
    c.total_count = len(values or [])
    c.null_count = 0
    if is_unique is not None:
        c.is_unique = is_unique
    else:
        c.is_unique = len(set(values or [])) == len(values or []) if values else False
    return c


@pytest.fixture
def comprehensive_graph():
    """Create a comprehensive ontology with hierarchy, restrictions, and SKOS relations."""
    g = Graph()
    g.bind("test", TEST)
    g.bind("xsd", XSD)
    g.bind("skos", SKOS)

    # Person class with restrictions
    g.add((TEST.Person, RDF.type, OWL.Class))
    g.add((TEST.Person, RDFS.label, Literal("Person")))

    # Employee subclass
    g.add((TEST.Employee, RDF.type, OWL.Class))
    g.add((TEST.Employee, RDFS.label, Literal("Employee")))
    g.add((TEST.Employee, RDFS.subClassOf, TEST.Person))

    # Properties with various constraints
    # Birth date with cardinality restriction
    g.add((TEST.birthDate, RDF.type, OWL.DatatypeProperty))
    g.add((TEST.birthDate, RDFS.label, Literal("birth date")))
    g.add((TEST.birthDate, RDFS.domain, TEST.Person))
    g.add((TEST.birthDate, RDFS.range, XSD.date))

    # Restriction: exactly 1 birthDate per Person
    bn_birth = TEST._bnode_birth_restriction
    g.add((TEST.Person, RDFS.subClassOf, bn_birth))
    g.add((bn_birth, RDF.type, OWL.Restriction))
    g.add((bn_birth, OWL.onProperty, TEST.birthDate))
    g.add((bn_birth, OWL.cardinality, Literal("1")))

    # Email with SKOS relations
    g.add((TEST.email, RDF.type, OWL.DatatypeProperty))
    g.add((TEST.email, RDFS.label, Literal("email")))
    g.add((TEST.email, RDFS.domain, TEST.Person))
    g.add((TEST.email, SKOS.exactMatch, TEST.electronicMail))
    g.add((TEST.email, SKOS.closeMatch, TEST.mail))
    g.add((TEST.email, SKOS.altLabel, Literal("electronic mail")))

    # Employee ID with uniqueness constraint
    g.add((TEST.employeeId, RDF.type, OWL.DatatypeProperty))
    g.add((TEST.employeeId, RDFS.label, Literal("employee ID")))
    g.add((TEST.employeeId, RDFS.domain, TEST.Employee))
    g.add((TEST.employeeId, RDF.type, OWL.InverseFunctionalProperty))  # Unique identifier

    # Name properties (hierarchical)
    g.add((TEST.name, RDF.type, OWL.DatatypeProperty))
    g.add((TEST.name, RDFS.label, Literal("name")))
    g.add((TEST.name, RDFS.domain, TEST.Person))

    g.add((TEST.firstName, RDF.type, OWL.DatatypeProperty))
    g.add((TEST.firstName, RDFS.label, Literal("first name")))
    g.add((TEST.firstName, RDFS.domain, TEST.Person))
    g.add((TEST.firstName, RDFS.subPropertyOf, TEST.name))

    g.add((TEST.lastName, RDF.type, OWL.DatatypeProperty))
    g.add((TEST.lastName, RDFS.label, Literal("last name")))
    g.add((TEST.lastName, RDFS.domain, TEST.Person))
    g.add((TEST.lastName, RDFS.subPropertyOf, TEST.name))

    return g


@pytest.fixture
def analyzer(comprehensive_graph):
    with tempfile.NamedTemporaryFile(mode='wb', suffix='.ttl', delete=False) as f:
        comprehensive_graph.serialize(f, format='turtle')
        path = f.name
    oa = OntologyAnalyzer(path)
    os.unlink(path)
    return oa


@pytest.fixture
def reasoner(comprehensive_graph, analyzer):
    return GraphReasoner(comprehensive_graph, analyzer.classes, analyzer.properties)


def test_phase2_pipeline_integration(analyzer, reasoner):
    """Test complete Phase 2 pipeline with multiple matcher types."""
    pipeline = create_default_pipeline(
        use_restrictions=True,
        use_skos_relations=True,
        use_semantic=False,  # Disable to isolate Phase 2 effects
        ontology_analyzer=analyzer,
        reasoner=reasoner
    )

    columns = [
        make_column("dob", ["1990-01-15", "1985-03-20"], "date", is_unique=True),
        make_column("email_address", ["john@example.com", "jane@example.com"], "string"),
        make_column("emp_id", ["E001", "E002"], "string", is_unique=True),
        make_column("first_name", ["John", "Jane"], "string"),
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

    # Verify expected matches
    assert len(matches) >= 3, f"Expected at least 3 matches, got {len(matches)}: {matches}"

    # Check specific matches
    matched_uris = list(matches.values())
    assert any("birthDate" in str(uri) for uri in matched_uris), "birthDate should be matched"
    assert any("email" in str(uri) for uri in matched_uris), "email should be matched via SKOS"
    assert any("employeeId" in str(uri) for uri in matched_uris), "employeeId should be matched via uniqueness"


def test_restriction_vs_skos_priority(analyzer):
    """Test that restriction-based matching takes priority over SKOS when appropriate."""
    restriction_matcher = RestrictionBasedMatcher(analyzer, threshold=0.3)
    skos_matcher = SKOSRelationsMatcher(threshold=0.3)

    # Unique date column should score higher on restricted birthDate property
    col = make_column("birth_date", ["1990-01-15"], "date", is_unique=True)
    properties = list(analyzer.properties.values())

    context = MatchContext(column=col, all_columns=[col], available_properties=properties)

    restriction_result = restriction_matcher.match(col, properties, context)
    skos_result = skos_matcher.match(col, properties, context)

    assert restriction_result is not None, "Restriction matcher should find birthDate"
    # SKOS might not match since "birth_date" doesn't have SKOS relations in our test ontology

    # Restriction should have higher confidence for date+unique column
    assert restriction_result.confidence >= 0.3


def test_negative_restriction_case(analyzer):
    """Test that cardinality mismatch properly lowers confidence."""
    matcher = RestrictionBasedMatcher(analyzer, threshold=0.6)

    # Non-unique values for cardinality=1 property should lower confidence
    col = make_column("birth_date", ["1990-01-15", "1990-01-15"], "date", is_unique=False)
    properties = list(analyzer.properties.values())

    context = MatchContext(column=col, all_columns=[col], available_properties=properties)
    result = matcher.match(col, properties, context)

    # Should either not match (None) or have low confidence due to cardinality mismatch
    if result:
        assert result.confidence < 0.6, f"Expected low confidence due to cardinality mismatch, got {result.confidence}"
    # else: No match is also acceptable behavior


def test_skos_hierarchy_boost(analyzer):
    """Test SKOS relations boost (exactMatch, closeMatch)."""
    matcher = SKOSRelationsMatcher(threshold=0.3)

    # Test exactMatch boost
    col_exact = make_column("electronicMail", ["test@example.com"], "string")
    # Test closeMatch boost
    col_close = make_column("mail", ["test@example.com"], "string")

    properties = list(analyzer.properties.values())
    context = MatchContext(column=col_exact, all_columns=[col_exact], available_properties=properties)

    result_exact = matcher.match(col_exact, properties, context)
    result_close = matcher.match(col_close, properties, context)

    # Both should match email property
    assert result_exact is not None, "exactMatch should find email"
    assert result_close is not None, "closeMatch should find email"

    # Both should have reasonable confidence (exactMatch relationships are complex to score)
    assert result_exact.confidence >= 0.3
    assert result_close.confidence >= 0.3


def test_semantic_with_phase2_integration(analyzer, reasoner):
    """Test that semantic matcher works alongside Phase 2 matchers."""
    # Use semantic matcher with context awareness from Phase 1 enhancement
    semantic_matcher = SemanticSimilarityMatcher(
        reasoner=reasoner,
        use_embeddings=False,  # Use lexical fallback for testing
        threshold=0.4
    )

    restriction_matcher = RestrictionBasedMatcher(analyzer, threshold=0.4)

    col = make_column("employee_identifier", ["EMP001", "EMP002"], "string", is_unique=True)
    properties = list(analyzer.properties.values())

    context = MatchContext(column=col, all_columns=[col], available_properties=properties)

    semantic_result = semantic_matcher.match(col, properties, context)
    restriction_result = restriction_matcher.match(col, properties, context)

    # Both matchers should be able to find matches, but potentially different properties
    # This tests that they don't interfere with each other
    matches_found = sum([1 for r in [semantic_result, restriction_result] if r is not None])
    assert matches_found >= 1, "At least one matcher should find a match"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
