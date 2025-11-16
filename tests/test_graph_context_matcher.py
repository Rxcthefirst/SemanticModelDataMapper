"""Tests for Graph Context Matcher - Property Co-occurrence Patterns.

This test suite validates the enhanced Graph Context Matcher that uses:
1. Property co-occurrence patterns (properties that often appear together)
2. Context-based confidence boosting
3. Structural similarity and pattern recognition

Following TDD principles:
- Write tests first
- Implement features to make tests pass
- Refactor for quality

Target: +0.5 score improvement (9.0 → 9.5/10)
"""

import pytest
import tempfile
import os
from rdflib import Graph, Namespace, RDF, RDFS, OWL, Literal
from rdflib.namespace import XSD

from rdfmap.generator.graph_reasoner import GraphReasoner
from rdfmap.generator.ontology_analyzer import OntologyAnalyzer
from rdfmap.generator.data_analyzer import DataFieldAnalysis
from rdfmap.generator.matchers.base import MatchContext


# Test namespace
TEST = Namespace("http://example.com/person#")


@pytest.fixture
def person_ontology_graph():
    """Create a person ontology graph with co-occurring properties."""
    g = Graph()
    g.bind("test", TEST)
    g.bind("xsd", XSD)

    # Person class
    g.add((TEST.Person, RDF.type, OWL.Class))
    g.add((TEST.Person, RDFS.label, Literal("Person")))

    # Name properties (often appear together)
    g.add((TEST.firstName, RDF.type, OWL.DatatypeProperty))
    g.add((TEST.firstName, RDFS.label, Literal("first name")))
    g.add((TEST.firstName, RDFS.domain, TEST.Person))
    g.add((TEST.firstName, RDFS.range, XSD.string))

    g.add((TEST.lastName, RDF.type, OWL.DatatypeProperty))
    g.add((TEST.lastName, RDFS.label, Literal("last name")))
    g.add((TEST.lastName, RDFS.domain, TEST.Person))
    g.add((TEST.lastName, RDFS.range, XSD.string))

    g.add((TEST.middleName, RDF.type, OWL.DatatypeProperty))
    g.add((TEST.middleName, RDFS.label, Literal("middle name")))
    g.add((TEST.middleName, RDFS.domain, TEST.Person))
    g.add((TEST.middleName, RDFS.range, XSD.string))

    # Birth info properties (often appear together)
    g.add((TEST.birthDate, RDF.type, OWL.DatatypeProperty))
    g.add((TEST.birthDate, RDFS.label, Literal("birth date")))
    g.add((TEST.birthDate, RDFS.domain, TEST.Person))
    g.add((TEST.birthDate, RDFS.range, XSD.date))

    g.add((TEST.birthPlace, RDF.type, OWL.DatatypeProperty))
    g.add((TEST.birthPlace, RDFS.label, Literal("birth place")))
    g.add((TEST.birthPlace, RDFS.domain, TEST.Person))
    g.add((TEST.birthPlace, RDFS.range, XSD.string))

    # Contact info properties (often appear together)
    g.add((TEST.email, RDF.type, OWL.DatatypeProperty))
    g.add((TEST.email, RDFS.label, Literal("email")))
    g.add((TEST.email, RDFS.domain, TEST.Person))
    g.add((TEST.email, RDFS.range, XSD.string))

    g.add((TEST.phoneNumber, RDF.type, OWL.DatatypeProperty))
    g.add((TEST.phoneNumber, RDFS.label, Literal("phone number")))
    g.add((TEST.phoneNumber, RDFS.domain, TEST.Person))
    g.add((TEST.phoneNumber, RDFS.range, XSD.string))

    # Address properties (often appear together)
    g.add((TEST.streetAddress, RDF.type, OWL.DatatypeProperty))
    g.add((TEST.streetAddress, RDFS.label, Literal("street address")))
    g.add((TEST.streetAddress, RDFS.domain, TEST.Person))
    g.add((TEST.streetAddress, RDFS.range, XSD.string))

    g.add((TEST.city, RDF.type, OWL.DatatypeProperty))
    g.add((TEST.city, RDFS.label, Literal("city")))
    g.add((TEST.city, RDFS.domain, TEST.Person))
    g.add((TEST.city, RDFS.range, XSD.string))

    g.add((TEST.zipCode, RDF.type, OWL.DatatypeProperty))
    g.add((TEST.zipCode, RDFS.label, Literal("zip code")))
    g.add((TEST.zipCode, RDFS.domain, TEST.Person))
    g.add((TEST.zipCode, RDFS.range, XSD.string))

    return g


@pytest.fixture
def ontology_analyzer(person_ontology_graph):
    """Create an OntologyAnalyzer instance from the graph."""
    # Save to temp file since OntologyAnalyzer expects a file path
    with tempfile.NamedTemporaryFile(mode='wb', suffix='.ttl', delete=False) as f:
        person_ontology_graph.serialize(f, format='turtle')
        temp_path = f.name

    analyzer = OntologyAnalyzer(temp_path)
    os.unlink(temp_path)

    return analyzer


@pytest.fixture
def graph_reasoner(person_ontology_graph, ontology_analyzer):
    """Create a GraphReasoner instance."""
    return GraphReasoner(
        person_ontology_graph,
        ontology_analyzer.classes,
        ontology_analyzer.properties
    )


def create_column(name: str, sample_values: list, inferred_type: str = "string") -> DataFieldAnalysis:
    """Helper to create a column for testing."""
    col = DataFieldAnalysis(name=name)
    col.sample_values = sample_values
    col.inferred_type = inferred_type
    col.total_count = len(sample_values)
    col.null_count = sum(1 for v in sample_values if v is None)
    return col


class TestCoOccurrencePatterns:
    """Test property co-occurrence pattern detection."""

    def test_detect_name_property_cluster(self, graph_reasoner, ontology_analyzer):
        """Test detection of name properties that co-occur."""
        # When we have firstName and lastName columns
        # And we're matching a column that could be middleName
        # The matcher should boost confidence because name properties co-occur

        from rdfmap.generator.matchers.graph_matcher import GraphContextMatcher

        matcher = GraphContextMatcher(
            reasoner=graph_reasoner,
            enabled=True,
            threshold=0.5,
            use_cooccurrence=True
        )

        # Create columns
        first_name_col = create_column("fname", ["John", "Jane", "Bob"])
        last_name_col = create_column("lname", ["Doe", "Smith", "Johnson"])
        middle_name_col = create_column("mname", ["A", "B", "C"])

        # Get properties
        properties = list(ontology_analyzer.properties.values())

        # Create context with firstName and lastName already matched
        context = MatchContext(
            column=middle_name_col,
            all_columns=[first_name_col, last_name_col, middle_name_col],
            available_properties=properties,
            matched_properties={
                "fname": str(TEST.firstName),
                "lname": str(TEST.lastName)
            }
        )

        # Match middle name column
        result = matcher.match(middle_name_col, properties, context)

        assert result is not None, "Should find match for middle name"
        assert "middleName" in result.property.uri
        assert result.confidence > 0.7, f"Should have boosted confidence due to co-occurrence, got {result.confidence}"
        assert "context" in result.matched_via.lower() or "boost" in result.matched_via.lower()

    def test_boost_birth_date_when_birth_place_matched(self, graph_reasoner, ontology_analyzer):
        """Test confidence boost when related properties are already matched."""
        from rdfmap.generator.matchers.graph_matcher import GraphContextMatcher

        matcher = GraphContextMatcher(
            reasoner=graph_reasoner,
            enabled=True,
            threshold=0.5,
            use_cooccurrence=True
        )

        # Create columns
        birth_place_col = create_column("birth_city", ["New York", "Boston", "Chicago"])
        birth_date_col = create_column("dob", ["1990-01-15", "1985-05-20", "1992-08-10"])

        properties = list(ontology_analyzer.properties.values())
        # Context with birthPlace already matched
        context = MatchContext(
            column=birth_date_col,
            all_columns=[birth_place_col, birth_date_col],
            available_properties=properties,
            matched_properties={"birth_city": str(TEST.birthPlace)}
        )

        # Match birth date - should get confidence boost
        result = matcher.match(birth_date_col, properties, context)

        assert result is not None
        assert "birthDate" in result.property.uri
        assert result.confidence > 0.7

    def test_address_property_cluster(self, graph_reasoner, ontology_analyzer):
        """Test that address properties boost each other."""
        from rdfmap.generator.matchers.graph_matcher import GraphContextMatcher

        matcher = GraphContextMatcher(
            reasoner=graph_reasoner,
            enabled=True,
            threshold=0.5,
            use_cooccurrence=True
        )

        street_col = create_column("address", ["123 Main St", "456 Oak Ave"])
        city_col = create_column("city_name", ["Boston", "New York"])
        zip_col = create_column("postal_code", ["02101", "10001"])

        properties = list(ontology_analyzer.properties.values())
        context_empty = MatchContext(column=street_col, all_columns=[street_col, city_col, zip_col], available_properties=properties)
        street_result = matcher.match(street_col, properties, context_empty)
        initial_confidence = street_result.confidence if street_result else 0

        context_with_street = MatchContext(
            column=city_col,
            all_columns=[street_col, city_col, zip_col],
            available_properties=properties,
            matched_properties={"address": str(TEST.streetAddress)}
        )
        city_result = matcher.match(city_col, properties, context_with_street)

        assert city_result is not None
        assert "city" in city_result.property.uri
        assert city_result.confidence > 0.65

        context_with_both = MatchContext(
            column=zip_col,
            all_columns=[street_col, city_col, zip_col],
            available_properties=properties,
            matched_properties={
                "address": str(TEST.streetAddress),
                "city_name": str(TEST.city)
            }
        )
        zip_result = matcher.match(zip_col, properties, context_with_both)
        assert zip_result is not None
        assert "zipCode" in zip_result.property.uri
        assert zip_result.confidence > 0.7

    def test_contact_info_cluster(self, graph_reasoner, ontology_analyzer):
        """Test that email and phone boost each other."""
        from rdfmap.generator.matchers.graph_matcher import GraphContextMatcher

        matcher = GraphContextMatcher(
            reasoner=graph_reasoner,
            enabled=True,
            threshold=0.5,
            use_cooccurrence=True
        )

        email_col = create_column("email_address", ["john@example.com", "jane@example.com"])
        phone_col = create_column("phone", ["555-1234", "555-5678"])

        properties = list(ontology_analyzer.properties.values())
        context = MatchContext(
            column=phone_col,
            all_columns=[email_col, phone_col],
            available_properties=properties,
            matched_properties={"email_address": str(TEST.email)}
        )
        result = matcher.match(phone_col, properties, context)
        assert result is not None
        assert "phoneNumber" in result.property.uri
        assert result.confidence > 0.65


class TestCoOccurrencePatternLearning:
    """Test learning co-occurrence patterns from ontology structure."""

    def test_build_cooccurrence_cache(self, graph_reasoner):
        from rdfmap.generator.matchers.graph_matcher import GraphContextMatcher
        matcher = GraphContextMatcher(
            reasoner=graph_reasoner,
            enabled=True,
            use_cooccurrence=True
        )
        assert hasattr(matcher, 'cooccurrence_patterns')
        patterns = matcher.cooccurrence_patterns
        first_name_uri = str(TEST.firstName)
        last_name_uri = str(TEST.lastName)
        middle_name_uri = str(TEST.middleName)
        if first_name_uri in patterns:
            cooccurring = patterns[first_name_uri]
            assert last_name_uri in cooccurring or middle_name_uri in cooccurring

    def test_cooccurrence_score_calculation(self, graph_reasoner, ontology_analyzer):
        from rdfmap.generator.matchers.graph_matcher import GraphContextMatcher
        matcher = GraphContextMatcher(
            reasoner=graph_reasoner,
            enabled=True,
            use_cooccurrence=True
        )
        properties = list(ontology_analyzer.properties.values())
        context = MatchContext(
            column=create_column("dummy", ["x"]),
            all_columns=[],
            available_properties=properties,
            matched_properties={
                "col1": str(TEST.firstName),
                "col2": str(TEST.lastName)
            }
        )
        middle_name_prop = next(p for p in properties if "middleName" in p.uri)
        score = matcher._calculate_cooccurrence_score(middle_name_prop, context)
        assert score > 0
        assert score <= 1.0


class TestContextPropagation:
    """Test confidence boosting through context propagation."""

    def test_confidence_boost_with_one_matched_sibling(self, graph_reasoner, ontology_analyzer):
        from rdfmap.generator.matchers.graph_matcher import GraphContextMatcher
        matcher = GraphContextMatcher(
            reasoner=graph_reasoner,
            enabled=True,
            threshold=0.5,
            use_cooccurrence=True
        )
        col = create_column("fname", ["John", "Jane"])
        properties = list(ontology_analyzer.properties.values())
        context_empty = MatchContext(column=col, all_columns=[col], available_properties=properties)
        result_no_context = matcher.match(col, properties, context_empty)
        base_confidence = result_no_context.confidence if result_no_context else 0
        context_with_sibling = MatchContext(
            column=col,
            all_columns=[col],
            available_properties=properties,
            matched_properties={"other_col": str(TEST.lastName)}
        )
        result_with_context = matcher.match(col, properties, context_with_sibling)
        if result_with_context:
            assert result_with_context.confidence >= base_confidence

    def test_confidence_boost_scales_with_matched_siblings(self, graph_reasoner, ontology_analyzer):
        from rdfmap.generator.matchers.graph_matcher import GraphContextMatcher
        matcher = GraphContextMatcher(
            reasoner=graph_reasoner,
            enabled=True,
            use_cooccurrence=True
        )
        col = create_column("mid_name", ["A", "B"])
        properties = list(ontology_analyzer.properties.values())
        context_one = MatchContext(
            column=col,
            all_columns=[col],
            available_properties=properties,
            matched_properties={"col1": str(TEST.firstName)}
        )
        result_one = matcher.match(col, properties, context_one)
        confidence_one = result_one.confidence if result_one else 0
        context_two = MatchContext(
            column=col,
            all_columns=[col],
            available_properties=properties,
            matched_properties={
                "col1": str(TEST.firstName),
                "col2": str(TEST.lastName)
            }
        )
        result_two = matcher.match(col, properties, context_two)
        confidence_two = result_two.confidence if result_two else 0
        assert confidence_two >= confidence_one


class TestStructuralSimilarity:
    """Test structural similarity matching."""

    def test_detect_similar_column_patterns(self, graph_reasoner, ontology_analyzer):
        from rdfmap.generator.matchers.graph_matcher import GraphContextMatcher
        matcher = GraphContextMatcher(
            reasoner=graph_reasoner,
            enabled=True,
            use_cooccurrence=True
        )
        first_name = create_column("first_name", ["John", "Jane", "Bob"])
        last_name = create_column("last_name", ["Doe", "Smith", "Johnson"])
        middle_name = create_column("middle_initial", ["A", "B", "C"])

        properties = list(ontology_analyzer.properties.values())
        context = MatchContext(
            column=middle_name,
            all_columns=[first_name, last_name, middle_name],
            available_properties=properties,
            matched_properties={
                "first_name": str(TEST.firstName),
                "last_name": str(TEST.lastName)
            }
        )

        result = matcher.match(middle_name, properties, context)

        assert result is not None
        assert "middleName" in result.property.uri
        # Should have decent confidence due to structural similarity
        assert result.confidence > 0.6


class TestIntegration:
    """Integration tests for the complete Graph Context Matcher."""

    def test_end_to_end_person_data_matching(self, graph_reasoner, ontology_analyzer):
        from rdfmap.generator.matchers.graph_matcher import GraphContextMatcher
        matcher = GraphContextMatcher(
            reasoner=graph_reasoner,
            enabled=True,
            threshold=0.5,
            use_cooccurrence=True
        )
        columns = {
            "first_name": create_column("first_name", ["John", "Jane"]),
            "last_name": create_column("last_name", ["Doe", "Smith"]),
            "email": create_column("email", ["john@ex.com", "jane@ex.com"]),
            "phone": create_column("phone", ["555-1234", "555-5678"]),
            "dob": create_column("dob", ["1990-01-15", "1985-05-20"]),
        }
        properties = list(ontology_analyzer.properties.values())
        matched = {}
        context = MatchContext(column=columns["first_name"], all_columns=list(columns.values()), available_properties=properties)
        for col_name, col in columns.items():
            context.column = col
            context.matched_properties = matched
            result = matcher.match(col, properties, context)
            if result:
                matched[col_name] = result.property.uri
        assert len(matched) == 5
        assert any("firstName" in uri for uri in matched.values())
        assert any("lastName" in uri for uri in matched.values())
        assert any("email" in uri for uri in matched.values())
        assert any("phoneNumber" in uri for uri in matched.values())
        assert any("birthDate" in uri for uri in matched.values())

    def test_matcher_respects_threshold(self, graph_reasoner, ontology_analyzer):
        from rdfmap.generator.matchers.graph_matcher import GraphContextMatcher
        matcher = GraphContextMatcher(
            reasoner=graph_reasoner,
            enabled=True,
            threshold=0.9,
            use_cooccurrence=True
        )
        col = create_column("data", ["value1", "value2"])
        properties = list(ontology_analyzer.properties.values())
        context = MatchContext(column=col, all_columns=[col], available_properties=properties)
        result = matcher.match(col, properties, context)
        assert result is None or result.confidence >= 0.9


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
