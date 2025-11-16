"""Tests for Enhanced Semantic Matcher (class-aware + context-aware).

Focus:
- Use labels + comments in similarity
- Class-aware/domain-aware boosts
- Multi-field/context co-occurrence boosts
- Threshold behavior

No heavy embedding dependency; rely on lexical fallback.
"""

import os
import tempfile
import pytest
from rdflib import Graph, Namespace, RDF, RDFS, OWL, Literal
from rdflib.namespace import XSD

from rdfmap.generator.ontology_analyzer import OntologyAnalyzer
from rdfmap.generator.graph_reasoner import GraphReasoner
from rdfmap.generator.data_analyzer import DataFieldAnalysis
from rdfmap.generator.matchers import SemanticSimilarityMatcher
from rdfmap.generator.matchers.base import MatchContext

TEST = Namespace("http://example.com/person#")


def make_column(name, values=None, inferred_type="string"):
    c = DataFieldAnalysis(name=name)
    c.sample_values = values or []
    c.inferred_type = inferred_type
    c.total_count = len(values or [])
    c.null_count = 0
    return c


@pytest.fixture
def person_graph():
    g = Graph()
    g.bind("test", TEST)
    g.bind("xsd", XSD)

    # Classes
    g.add((TEST.Person, RDF.type, OWL.Class))
    g.add((TEST.Person, RDFS.label, Literal("Person")))

    # Properties
    # Name family
    g.add((TEST.firstName, RDF.type, OWL.DatatypeProperty))
    g.add((TEST.firstName, RDFS.label, Literal("first name")))
    g.add((TEST.firstName, RDFS.comment, Literal("Given name of a person")))
    g.add((TEST.firstName, RDFS.domain, TEST.Person))

    g.add((TEST.lastName, RDF.type, OWL.DatatypeProperty))
    g.add((TEST.lastName, RDFS.label, Literal("last name")))
    g.add((TEST.lastName, RDFS.domain, TEST.Person))

    g.add((TEST.middleName, RDF.type, OWL.DatatypeProperty))
    g.add((TEST.middleName, RDFS.label, Literal("middle name")))
    g.add((TEST.middleName, RDFS.comment, Literal("Middle name or initial")))
    g.add((TEST.middleName, RDFS.domain, TEST.Person))

    # Birth info
    g.add((TEST.birthDate, RDF.type, OWL.DatatypeProperty))
    g.add((TEST.birthDate, RDFS.label, Literal("birth date")))
    g.add((TEST.birthDate, RDFS.domain, TEST.Person))
    g.add((TEST.birthDate, RDFS.range, XSD.date))

    g.add((TEST.birthPlace, RDF.type, OWL.DatatypeProperty))
    g.add((TEST.birthPlace, RDFS.label, Literal("birth place")))
    g.add((TEST.birthPlace, RDFS.domain, TEST.Person))

    # Contact
    g.add((TEST.email, RDF.type, OWL.DatatypeProperty))
    g.add((TEST.email, RDFS.label, Literal("email")))
    g.add((TEST.email, RDFS.domain, TEST.Person))

    g.add((TEST.phoneNumber, RDF.type, OWL.DatatypeProperty))
    g.add((TEST.phoneNumber, RDFS.label, Literal("phone number")))
    g.add((TEST.phoneNumber, RDFS.domain, TEST.Person))

    return g


@pytest.fixture
def analyzer(person_graph):
    with tempfile.NamedTemporaryFile(mode='wb', suffix='.ttl', delete=False) as f:
        person_graph.serialize(f, format='turtle')
        path = f.name
    oa = OntologyAnalyzer(path)
    os.unlink(path)
    return oa


@pytest.fixture
def reasoner(person_graph, analyzer):
    return GraphReasoner(person_graph, analyzer.classes, analyzer.properties)


def test_basic_label_and_comment_usage(reasoner, analyzer):
    matcher = SemanticSimilarityMatcher(
        reasoner=reasoner,
        enabled=True,
        threshold=0.5,
        use_embeddings=False
    )

    col = make_column("mname", ["A", "B", "C"])  # should map to middle name
    properties = list(analyzer.properties.values())

    context = MatchContext(
        column=col,
        all_columns=[col],
        available_properties=properties,
    )

    result = matcher.match(col, properties, context)
    assert result is not None, "Should find a semantic match via label/comment"
    assert "middleName" in result.property.uri


def test_domain_aware_boost(reasoner, analyzer):
    matcher = SemanticSimilarityMatcher(
        reasoner=reasoner,
        enabled=True,
        threshold=0.5,
        use_embeddings=False
    )

    # With first/last already matched (same domain), birth date should be boosted
    first_col = make_column("first_name", ["John"])
    last_col = make_column("last_name", ["Doe"])
    dob_col = make_column("dob", ["1990-01-15"])

    properties = list(analyzer.properties.values())
    matched = {
        "first_name": str(TEST.firstName),
        "last_name": str(TEST.lastName)
    }

    ctx = MatchContext(
        column=dob_col,
        all_columns=[first_col, last_col, dob_col],
        available_properties=properties,
        matched_properties=matched
    )

    result = matcher.match(dob_col, properties, ctx)
    assert result is not None
    assert "birthDate" in result.property.uri
    assert result.confidence >= 0.65, f"Expected boost to >=0.65, got {result.confidence}"


def test_threshold_respected(reasoner, analyzer):
    matcher = SemanticSimilarityMatcher(
        reasoner=reasoner,
        enabled=True,
        threshold=0.9,
        use_embeddings=False
    )

    # Ambiguous column
    col = make_column("data", ["value1", "value2"])
    properties = list(analyzer.properties.values())
    ctx = MatchContext(column=col, all_columns=[col], available_properties=properties)

    res = matcher.match(col, properties, ctx)
    assert res is None or res.confidence >= 0.9
