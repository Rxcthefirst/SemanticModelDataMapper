"""Phase 2 Matcher Tests: RestrictionBasedMatcher & SKOSRelationsMatcher."""
import os, tempfile, pytest
from rdflib import Graph, Namespace, RDF, RDFS, OWL, Literal
from rdflib.namespace import XSD, SKOS

from rdfmap.generator.ontology_analyzer import OntologyAnalyzer
from rdfmap.generator.graph_reasoner import GraphReasoner
from rdfmap.generator.data_analyzer import DataFieldAnalysis
from rdfmap.generator.matchers import RestrictionBasedMatcher, SKOSRelationsMatcher
from rdfmap.generator.matchers.base import MatchContext

TEST = Namespace("http://example.com/test#")


def make_column(name, values=None, inferred_type="string"):
    c = DataFieldAnalysis(name)
    c.sample_values = values or []
    c.inferred_type = inferred_type
    c.total_count = len(values or [])
    c.null_count = 0
    c.is_unique = len(set(values or [])) == len(values or []) if values else False
    return c

@pytest.fixture
def restriction_graph():
    g = Graph()
    g.bind("test", TEST)
    g.bind("xsd", XSD)
    g.bind("skos", SKOS)

    # Class Person with restriction: exactly 1 birthDate (xsd:date)
    g.add((TEST.Person, RDF.type, OWL.Class))
    g.add((TEST.Person, RDFS.label, Literal("Person")))

    g.add((TEST.birthDate, RDF.type, OWL.DatatypeProperty))
    g.add((TEST.birthDate, RDFS.label, Literal("birth date")))
    g.add((TEST.birthDate, RDFS.domain, TEST.Person))
    g.add((TEST.birthDate, RDFS.range, XSD.date))

    # Restriction blank node
    bn = TEST._bnode_birth  # using a URIRef placeholder (simplified)
    g.add((TEST.Person, RDFS.subClassOf, bn))
    g.add((bn, RDF.type, OWL.Restriction))
    g.add((bn, OWL.onProperty, TEST.birthDate))
    g.add((bn, OWL.cardinality, Literal("1")))
    g.add((bn, OWL.someValuesFrom, XSD.date))

    # SKOS relations for email
    g.add((TEST.email, RDF.type, OWL.DatatypeProperty))
    g.add((TEST.email, RDFS.label, Literal("email")))
    g.add((TEST.email, SKOS.exactMatch, TEST.electronicMailAddress))
    g.add((TEST.email, SKOS.closeMatch, TEST.mail))

    return g

@pytest.fixture
def analyzer(restriction_graph):
    with tempfile.NamedTemporaryFile(mode='wb', suffix='.ttl', delete=False) as f:
        restriction_graph.serialize(f, format='turtle')
        path = f.name
    oa = OntologyAnalyzer(path)
    os.unlink(path)
    return oa

@pytest.fixture
def reasoner(restriction_graph, analyzer):
    return GraphReasoner(restriction_graph, analyzer.classes, analyzer.properties)


def test_restriction_matcher_birthdate(analyzer):
    matcher = RestrictionBasedMatcher(ontology_analyzer=analyzer, threshold=0.4)
    col = make_column("dob", ["1990-01-15", "1991-02-20"], inferred_type="date")
    props = list(analyzer.properties.values())
    ctx = MatchContext(column=col, all_columns=[col], available_properties=props)
    res = matcher.match(col, props, ctx)
    assert res is not None, "Restriction matcher should find birthDate"
    assert "birthDate" in res.property.uri
    assert res.confidence >= 0.3


def test_restriction_mismatch_uniqueness(analyzer):
    matcher = RestrictionBasedMatcher(ontology_analyzer=analyzer, threshold=0.2)
    # Non-unique values should reduce score for cardinality=1
    col = make_column("dob", ["1990-01-15", "1990-01-15"], inferred_type="date")
    props = list(analyzer.properties.values())
    ctx = MatchContext(column=col, all_columns=[col], available_properties=props)
    res = matcher.match(col, props, ctx)
    # Might still match but lower confidence
    if res:
        assert res.confidence < 0.6


def test_skos_relations_matcher_exact(analyzer):
    matcher = SKOSRelationsMatcher(threshold=0.4)
    col = make_column("email_address", ["a@b.com"], inferred_type="string")
    props = list(analyzer.properties.values())
    ctx = MatchContext(column=col, all_columns=[col], available_properties=props)
    res = matcher.match(col, props, ctx)
    assert res is not None
    assert "email" in res.property.uri
    assert res.confidence >= 0.4


def test_skos_relations_matcher_close(analyzer):
    matcher = SKOSRelationsMatcher(threshold=0.2)
    col = make_column("mail", ["a@b.com"], inferred_type="string")
    props = list(analyzer.properties.values())
    ctx = MatchContext(column=col, all_columns=[col], available_properties=props)
    res = matcher.match(col, props, ctx)
    assert res is not None
    assert "email" in res.property.uri

