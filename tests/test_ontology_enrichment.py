"""Tests for ontology enrichment functionality."""

import json
import tempfile
from datetime import datetime
from pathlib import Path

import pytest
from rdflib import Graph, Namespace, Literal, URIRef
from rdflib.namespace import RDF, RDFS, SKOS, DCTERMS

from rdfmap.generator.ontology_enricher import OntologyEnricher
from rdfmap.models.enrichment import (
    SKOSAddition, SKOSLabelType, EnrichmentAction, 
    InteractivePromptResponse, EnrichmentStats
)
from rdfmap.models.alignment import (
    AlignmentReport, UnmappedColumn,
    SKOSEnrichmentSuggestion, AlignmentStatistics
)


@pytest.fixture
def sample_ontology_ttl():
    """Create a sample ontology in Turtle format."""
    return """
@prefix ex: <http://example.org/hr#> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .

ex:Employee a owl:Class ;
    rdfs:label "Employee" .

ex:employeeId a owl:DatatypeProperty ;
    rdfs:label "employee identifier" ;
    rdfs:domain ex:Employee ;
    skos:prefLabel "Employee ID" .

ex:fullName a owl:DatatypeProperty ;
    rdfs:label "full name" ;
    rdfs:domain ex:Employee .

ex:salary a owl:DatatypeProperty ;
    rdfs:label "salary" ;
    rdfs:domain ex:Employee .
"""


@pytest.fixture
def temp_ontology_file(sample_ontology_ttl):
    """Create a temporary ontology file."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.ttl', delete=False) as f:
        f.write(sample_ontology_ttl)
        return f.name


@pytest.fixture
def sample_alignment_report():
    """Create a sample alignment report with suggestions."""
    return AlignmentReport(
        generated_at=datetime.utcnow(),
        ontology_file="hr_ontology.ttl",
        spreadsheet_file="employees.csv",
        target_class="http://example.org/hr#Employee",
        statistics=AlignmentStatistics(
            total_columns=5,
            mapped_columns=3,
            unmapped_columns=2,
            mapping_success_rate=0.6,
            average_confidence=0.75,
            high_confidence_matches=2,
            medium_confidence_matches=1,
            low_confidence_matches=0,
            very_low_confidence_matches=0
        ),
        unmapped_columns=[
            UnmappedColumn(
                column_name="emp_num",
                sample_values=["E001", "E002", "E003"],
                inferred_datatype="string"
            ),
            UnmappedColumn(
                column_name="full_name_display",
                sample_values=["John Doe", "Jane Smith"],
                inferred_datatype="string"
            )
        ],
        weak_matches=[],
        skos_enrichment_suggestions=[
            SKOSEnrichmentSuggestion(
                property_uri="http://example.org/hr#employeeId",
                property_label="employee identifier",
                suggested_label_type="skos:hiddenLabel",
                suggested_label_value="emp_num",
                turtle_snippet='<http://example.org/hr#employeeId> skos:hiddenLabel "emp_num" .',
                justification="Common abbreviation in legacy HR systems"
            ),
            SKOSEnrichmentSuggestion(
                property_uri="http://example.org/hr#fullName",
                property_label="full name",
                suggested_label_type="skos:altLabel",
                suggested_label_value="Full Name Display",
                turtle_snippet='<http://example.org/hr#fullName> skos:altLabel "Full Name Display" .',
                justification="Business terminology used in UI"
            )
        ]
    )


class TestOntologyEnricher:
    """Tests for OntologyEnricher class."""
    
    def test_initialization(self, temp_ontology_file):
        """Test enricher initialization."""
        enricher = OntologyEnricher(temp_ontology_file, agent="test_user")
        
        assert enricher.ontology_path == temp_ontology_file
        assert enricher.agent == "test_user"
        assert len(enricher.graph) > 0
        
    def test_auto_apply_enrichment(self, temp_ontology_file, sample_alignment_report):
        """Test automatic application of enrichments."""
        enricher = OntologyEnricher(temp_ontology_file, agent="test_user")
        
        result = enricher.enrich_from_alignment_report(
            sample_alignment_report,
            confidence_threshold=0.7,
            auto_apply=True
        )
        
        assert result.success
        assert len(result.operations_applied) == 2  # Both suggestions above threshold
        assert len(result.operations_rejected) == 0
        assert result.acceptance_rate == 1.0
        
        # Verify the labels were added to the graph
        emp_id_uri = URIRef("http://example.org/hr#employeeId")
        hidden_labels = list(enricher.graph.objects(emp_id_uri, SKOS.hiddenLabel))
        assert len(hidden_labels) == 1
        assert str(hidden_labels[0]) == "emp_num"
        
        full_name_uri = URIRef("http://example.org/hr#fullName")
        alt_labels = list(enricher.graph.objects(full_name_uri, SKOS.altLabel))
        assert len(alt_labels) == 1
        assert str(alt_labels[0]) == "Full Name Display"
    
    def test_interactive_enrichment_accept(self, temp_ontology_file, sample_alignment_report):
        """Test interactive enrichment with acceptance."""
        enricher = OntologyEnricher(temp_ontology_file, agent="test_user")
        
        def accept_all(skos_addition):
            return InteractivePromptResponse(action=EnrichmentAction.ACCEPTED)
        
        result = enricher.enrich_from_alignment_report(
            sample_alignment_report,
            confidence_threshold=0.7,
            interactive_callback=accept_all
        )
        
        assert result.success
        assert len(result.operations_applied) == 2
        assert all(op.action == EnrichmentAction.ACCEPTED for op in result.operations_applied)
    
    def test_interactive_enrichment_reject(self, temp_ontology_file, sample_alignment_report):
        """Test interactive enrichment with rejection."""
        enricher = OntologyEnricher(temp_ontology_file, agent="test_user")
        
        def reject_all(skos_addition):
            return InteractivePromptResponse(action=EnrichmentAction.REJECTED)
        
        result = enricher.enrich_from_alignment_report(
            sample_alignment_report,
            confidence_threshold=0.7,
            interactive_callback=reject_all
        )
        
        assert result.success
        assert len(result.operations_applied) == 0
        assert len(result.operations_rejected) == 2
        assert result.acceptance_rate == 0.0
    
    def test_interactive_enrichment_edit(self, temp_ontology_file, sample_alignment_report):
        """Test interactive enrichment with label editing."""
        enricher = OntologyEnricher(temp_ontology_file, agent="test_user")
        
        def edit_labels(skos_addition):
            return InteractivePromptResponse(
                action=EnrichmentAction.EDITED,
                edited_label="edited_" + skos_addition.label_value
            )
        
        result = enricher.enrich_from_alignment_report(
            sample_alignment_report,
            confidence_threshold=0.7,
            interactive_callback=edit_labels
        )
        
        assert result.success
        assert len(result.operations_applied) == 2
        
        # Verify edited labels were applied
        emp_id_uri = URIRef("http://example.org/hr#employeeId")
        hidden_labels = list(enricher.graph.objects(emp_id_uri, SKOS.hiddenLabel))
        assert str(hidden_labels[0]) == "edited_emp_num"
    
    def test_interactive_enrichment_with_annotations(self, temp_ontology_file, sample_alignment_report):
        """Test adding optional annotations (scope notes, examples, definitions)."""
        enricher = OntologyEnricher(temp_ontology_file, agent="test_user")
        
        def add_with_annotations(skos_addition):
            return InteractivePromptResponse(
                action=EnrichmentAction.ACCEPTED,
                scope_note="Test scope note",
                example="Test example",
                definition="Test definition"
            )
        
        result = enricher.enrich_from_alignment_report(
            sample_alignment_report,
            confidence_threshold=0.7,
            interactive_callback=add_with_annotations
        )
        
        assert result.success
        
        # Verify annotations were added
        emp_id_uri = URIRef("http://example.org/hr#employeeId")
        scope_notes = list(enricher.graph.objects(emp_id_uri, SKOS.scopeNote))
        examples = list(enricher.graph.objects(emp_id_uri, SKOS.example))
        definitions = list(enricher.graph.objects(emp_id_uri, SKOS.definition))
        
        assert len(scope_notes) == 1
        assert str(scope_notes[0]) == "Test scope note"
        assert len(examples) == 1
        assert str(examples[0]) == "Test example"
        assert len(definitions) == 1
        assert str(definitions[0]) == "Test definition"
    
    def test_interactive_skip_remaining(self, temp_ontology_file, sample_alignment_report):
        """Test skip remaining functionality."""
        enricher = OntologyEnricher(temp_ontology_file, agent="test_user")
        
        call_count = [0]
        
        def skip_after_first(skos_addition):
            call_count[0] += 1
            if call_count[0] == 1:
                return InteractivePromptResponse(action=EnrichmentAction.ACCEPTED)
            return InteractivePromptResponse(
                action=EnrichmentAction.SKIPPED,
                skip_remaining=True
            )
        
        result = enricher.enrich_from_alignment_report(
            sample_alignment_report,
            confidence_threshold=0.7,
            interactive_callback=skip_after_first
        )
        
        assert result.success
        assert len(result.operations_applied) == 1
        assert call_count[0] == 2  # Should stop after skip_remaining=True
    
    def test_provenance_tracking(self, temp_ontology_file, sample_alignment_report):
        """Test that provenance metadata is added."""
        enricher = OntologyEnricher(temp_ontology_file, agent="test_agent")
        
        result = enricher.enrich_from_alignment_report(
            sample_alignment_report,
            confidence_threshold=0.7,
            auto_apply=True
        )
        
        assert result.success
        
        # Verify provenance was added
        emp_id_uri = URIRef("http://example.org/hr#employeeId")
        
        # Check dcterms:modified
        modified = list(enricher.graph.objects(emp_id_uri, DCTERMS.modified))
        assert len(modified) == 1
        
        # Check dcterms:contributor
        contributors = list(enricher.graph.objects(emp_id_uri, DCTERMS.contributor))
        assert len(contributors) == 1
        assert str(contributors[0]) == "test_agent"
        
        # Check skos:changeNote
        change_notes = list(enricher.graph.objects(emp_id_uri, SKOS.changeNote))
        assert len(change_notes) == 1
        change_note = str(change_notes[0])
        assert "emp_num" in change_note
        assert "hiddenLabel" in change_note
    
    def test_turtle_generation(self, temp_ontology_file, sample_alignment_report):
        """Test Turtle syntax generation for applied operations."""
        enricher = OntologyEnricher(temp_ontology_file, agent="test_user")
        
        result = enricher.enrich_from_alignment_report(
            sample_alignment_report,
            confidence_threshold=0.7,
            auto_apply=True
        )
        
        assert result.turtle_additions
        assert "skos:hiddenLabel" in result.turtle_additions
        assert "skos:altLabel" in result.turtle_additions
        assert "emp_num" in result.turtle_additions
        assert "Full Name Display" in result.turtle_additions
        assert "dcterms:modified" in result.turtle_additions
        
    def test_save_enriched_ontology(self, temp_ontology_file, sample_alignment_report):
        """Test saving enriched ontology to file."""
        enricher = OntologyEnricher(temp_ontology_file, agent="test_user")
        
        enricher.enrich_from_alignment_report(
            sample_alignment_report,
            confidence_threshold=0.7,
            auto_apply=True
        )
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ttl', delete=False) as f:
            output_path = f.name
        
        enricher.save(output_path)
        
        # Verify file was created and can be loaded
        assert Path(output_path).exists()
        
        loaded_graph = Graph()
        loaded_graph.parse(output_path)
        
        assert len(loaded_graph) > len(Graph().parse(temp_ontology_file))
        
        # Clean up
        Path(output_path).unlink()
    
    def test_get_property_labels(self, temp_ontology_file):
        """Test retrieving existing labels for a property."""
        enricher = OntologyEnricher(temp_ontology_file, agent="test_user")
        
        labels = enricher.get_property_labels("http://example.org/hr#employeeId")
        
        assert "prefLabel" in labels
        assert "altLabel" in labels
        assert "hiddenLabel" in labels
        assert "Employee ID" in labels["prefLabel"]
    
    def test_no_suggestions_handling(self, temp_ontology_file):
        """Test handling of alignment report with no suggestions."""
        enricher = OntologyEnricher(temp_ontology_file, agent="test_user")
        
        empty_report = AlignmentReport(
            generated_at=datetime.utcnow(),
            ontology_file="test.ttl",
            spreadsheet_file="test.csv",
            target_class="http://example.org/hr#Test",
            statistics=AlignmentStatistics(
                total_columns=5,
                mapped_columns=5,
                unmapped_columns=0,
                mapping_success_rate=1.0,
                average_confidence=0.95,
                high_confidence_matches=5,
                medium_confidence_matches=0,
                low_confidence_matches=0,
                very_low_confidence_matches=0
            ),
            unmapped_columns=[],
            weak_matches=[],
            skos_enrichment_suggestions=[]
        )
        
        result = enricher.enrich_from_alignment_report(
            empty_report,
            confidence_threshold=0.7,
            auto_apply=True
        )
        
        assert result.success
        assert len(result.operations_applied) == 0
        assert len(result.operations_rejected) == 0


class TestEnrichmentStats:
    """Tests for EnrichmentStats model."""
    
    def test_stats_initialization(self):
        """Test stats initialization."""
        stats = EnrichmentStats()
        assert stats.total_suggestions == 0
        assert stats.accepted == 0
        assert stats.acceptance_rate == 0.0
    
    def test_stats_increment(self):
        """Test incrementing stats."""
        stats = EnrichmentStats()
        stats.total_suggestions = 3
        
        stats.increment(
            EnrichmentAction.ACCEPTED,
            SKOSLabelType.HIDDEN_LABEL,
            has_scope_note=True
        )
        stats.increment(
            EnrichmentAction.EDITED,
            SKOSLabelType.ALT_LABEL,
            has_example=True
        )
        stats.increment(
            EnrichmentAction.REJECTED,
            SKOSLabelType.PREF_LABEL
        )
        
        assert stats.accepted == 1
        assert stats.edited == 1
        assert stats.rejected == 1
        assert stats.hidden_labels_added == 1
        assert stats.alt_labels_added == 1
        assert stats.pref_labels_added == 0
        assert stats.scope_notes_added == 1
        assert stats.examples_added == 1
        assert stats.acceptance_rate == 2/3  # accepted + edited
    
    def test_stats_acceptance_rate(self):
        """Test acceptance rate calculation."""
        stats = EnrichmentStats()
        stats.total_suggestions = 10
        stats.accepted = 7
        stats.edited = 2
        stats.rejected = 1
        
        assert stats.acceptance_rate == 0.9  # (7 + 2) / 10


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
