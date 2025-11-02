"""Ontology enrichment engine for applying SKOS labels and provenance.

This module provides functionality to enrich ontologies with SKOS labels
based on alignment reports, including interactive and batch modes.
"""

import os
from datetime import datetime
from typing import Dict, List, Optional, TextIO
from pathlib import Path
from rdflib import Graph, Namespace, Literal, URIRef, RDF, RDFS
from rdflib.namespace import SKOS, DCTERMS, XSD

from ..models.enrichment import (
    SKOSAddition, SKOSLabelType, EnrichmentOperation, 
    EnrichmentAction, ProvenanceInfo, EnrichmentResult, EnrichmentStats
)
from ..models.alignment import AlignmentReport, UnmappedColumn, SKOSEnrichmentSuggestion

# Namespace for provenance
PROV = Namespace("http://www.w3.org/ns/prov#")


class OntologyEnricher:
    """Enriches ontologies with SKOS labels based on alignment reports."""
    
    def __init__(
        self, 
        ontology_path: str,
        agent: Optional[str] = None,
        tool_version: str = "rdfmap-1.0.0"
    ):
        """Initialize the enricher.
        
        Args:
            ontology_path: Path to the ontology file to enrich
            agent: User or system performing the enrichment (e.g., email or username)
            tool_version: Version string for provenance tracking
        """
        self.ontology_path = ontology_path
        self.agent = agent or os.environ.get("USER", "unknown")
        self.tool_version = tool_version
        
        # Load ontology
        self.graph = Graph()
        self.graph.parse(ontology_path)
        
        # Bind common namespaces
        self.graph.bind("skos", SKOS)
        self.graph.bind("dcterms", DCTERMS)
        self.graph.bind("prov", PROV)
        
    def enrich_from_alignment_report(
        self,
        alignment_report: AlignmentReport,
        confidence_threshold: float = 0.0,
        auto_apply: bool = False,
        interactive_callback: Optional[callable] = None
    ) -> EnrichmentResult:
        """Enrich ontology based on alignment report suggestions.
        
        Args:
            alignment_report: The alignment report with SKOS suggestions
            confidence_threshold: Minimum confidence to consider (0.0-1.0)
            auto_apply: If True, automatically apply all above threshold
            interactive_callback: Function to call for interactive prompts
            
        Returns:
            EnrichmentResult with details of what was applied
        """
        result = EnrichmentResult(success=True)
        stats = EnrichmentStats()
        
        # Get all SKOS suggestions from the report
        suggestions_to_process: List[SKOSAddition] = []
        
        for skos_sugg in alignment_report.skos_enrichment_suggestions:
            # Convert SKOSEnrichmentSuggestion to SKOSAddition
            # Note: We don't have confidence or source column directly, 
            # so we'll use defaults or infer from the suggestion
            
            # Determine label type from suggested_label_type string
            label_type_str = skos_sugg.suggested_label_type.split(':')[-1]  # e.g., "skos:hiddenLabel" -> "hiddenLabel"
            try:
                if label_type_str == "prefLabel":
                    label_type = SKOSLabelType.PREF_LABEL
                elif label_type_str == "altLabel":
                    label_type = SKOSLabelType.ALT_LABEL
                elif label_type_str == "hiddenLabel":
                    label_type = SKOSLabelType.HIDDEN_LABEL
                else:
                    # Default to hiddenLabel for unknown types
                    label_type = SKOSLabelType.HIDDEN_LABEL
            except (AttributeError, ValueError):
                label_type = SKOSLabelType.HIDDEN_LABEL
            
            skos_addition = SKOSAddition(
                property_uri=skos_sugg.property_uri,
                property_label=skos_sugg.property_label,
                label_type=label_type,
                label_value=skos_sugg.suggested_label_value,
                rationale=skos_sugg.justification,
                confidence=0.7,  # Default confidence since not in SKOSEnrichmentSuggestion
                source_column=skos_sugg.suggested_label_value  # Use label value as proxy for source column
            )
            suggestions_to_process.append(skos_addition)
        
        stats.total_suggestions = len(suggestions_to_process)
        
        # Process each suggestion
        for skos_addition in suggestions_to_process:
            provenance = ProvenanceInfo(
                agent=self.agent,
                alignment_report_source=str(alignment_report.spreadsheet_file),
                tool_version=self.tool_version
            )
            
            if auto_apply:
                # Automatically apply
                operation = EnrichmentOperation(
                    skos_addition=skos_addition,
                    action=EnrichmentAction.ACCEPTED,
                    provenance=provenance
                )
                self._apply_operation(operation)
                result.operations_applied.append(operation)
                stats.increment(
                    EnrichmentAction.ACCEPTED,
                    skos_addition.label_type
                )
                
            elif interactive_callback:
                # Interactive mode
                response = interactive_callback(skos_addition)
                
                if response.skip_remaining:
                    # User wants to skip all remaining
                    break
                
                operation = EnrichmentOperation(
                    skos_addition=skos_addition,
                    action=response.action,
                    provenance=provenance,
                    edited_label_value=response.edited_label,
                    scope_note=response.scope_note,
                    example=response.example,
                    definition=response.definition
                )
                
                if response.action in (EnrichmentAction.ACCEPTED, EnrichmentAction.EDITED):
                    self._apply_operation(operation)
                    result.operations_applied.append(operation)
                    stats.increment(
                        response.action,
                        skos_addition.label_type,
                        has_scope_note=bool(response.scope_note),
                        has_example=bool(response.example),
                        has_definition=bool(response.definition)
                    )
                else:
                    result.operations_rejected.append(operation)
                    stats.increment(response.action, skos_addition.label_type)
            else:
                # No interaction, just record as skipped
                operation = EnrichmentOperation(
                    skos_addition=skos_addition,
                    action=EnrichmentAction.SKIPPED,
                    provenance=provenance
                )
                result.operations_rejected.append(operation)
                stats.increment(EnrichmentAction.SKIPPED, skos_addition.label_type)
        
        # Generate turtle for all applied operations
        result.turtle_additions = self._generate_turtle_for_operations(
            result.operations_applied
        )
        
        return result
    
    def _apply_operation(self, operation: EnrichmentOperation):
        """Apply an enrichment operation to the graph.
        
        Args:
            operation: The enrichment operation to apply
        """
        prop_uri = URIRef(operation.skos_addition.property_uri)
        
        # Determine the label value to use
        label_value = (
            operation.edited_label_value 
            if operation.edited_label_value 
            else operation.skos_addition.label_value
        )
        
        # Add the SKOS label
        label_literal = Literal(
            label_value, 
            lang=operation.skos_addition.language
        )
        
        if operation.skos_addition.label_type == SKOSLabelType.PREF_LABEL:
            self.graph.add((prop_uri, SKOS.prefLabel, label_literal))
        elif operation.skos_addition.label_type == SKOSLabelType.ALT_LABEL:
            self.graph.add((prop_uri, SKOS.altLabel, label_literal))
        elif operation.skos_addition.label_type == SKOSLabelType.HIDDEN_LABEL:
            self.graph.add((prop_uri, SKOS.hiddenLabel, label_literal))
        
        # Add optional SKOS annotations
        if operation.scope_note:
            self.graph.add((
                prop_uri,
                SKOS.scopeNote,
                Literal(operation.scope_note, lang="en")
            ))
        
        if operation.example:
            self.graph.add((
                prop_uri,
                SKOS.example,
                Literal(operation.example, lang="en")
            ))
        
        if operation.definition:
            self.graph.add((
                prop_uri,
                SKOS.definition,
                Literal(operation.definition, lang="en")
            ))
        
        # Add provenance metadata
        now = Literal(
            operation.provenance.timestamp.isoformat(),
            datatype=XSD.dateTime
        )
        self.graph.add((prop_uri, DCTERMS.modified, now))
        
        if operation.provenance.agent:
            self.graph.add((
                prop_uri,
                DCTERMS.contributor,
                Literal(operation.provenance.agent)
            ))
        
        # Add change note with rationale
        change_note = self._generate_change_note(operation)
        self.graph.add((
            prop_uri,
            SKOS.changeNote,
            Literal(change_note, lang="en")
        ))
    
    def _generate_change_note(self, operation: EnrichmentOperation) -> str:
        """Generate a human-readable change note.
        
        Args:
            operation: The enrichment operation
            
        Returns:
            Change note string
        """
        label_type_str = operation.skos_addition.label_type.value
        label_value = (
            operation.edited_label_value 
            if operation.edited_label_value 
            else operation.skos_addition.label_value
        )
        
        note_parts = [
            f"Added {label_type_str} '{label_value}'",
            f"on {operation.provenance.timestamp.strftime('%Y-%m-%d')}",
            f"from column '{operation.skos_addition.source_column}'."
        ]
        
        if operation.skos_addition.rationale:
            note_parts.append(f"Rationale: {operation.skos_addition.rationale}")
        
        if operation.provenance.comment:
            note_parts.append(operation.provenance.comment)
        
        return " ".join(note_parts)
    
    def _generate_turtle_for_operations(
        self, 
        operations: List[EnrichmentOperation]
    ) -> str:
        """Generate Turtle syntax for a list of operations.
        
        Args:
            operations: List of applied operations
            
        Returns:
            Turtle formatted string
        """
        if not operations:
            return ""
        
        lines = [
            "@prefix skos: <http://www.w3.org/2004/02/skos/core#> .",
            "@prefix dcterms: <http://purl.org/dc/terms/> .",
            "@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .",
            ""
        ]
        
        for op in operations:
            prop_uri = op.skos_addition.property_uri
            label_value = (
                op.edited_label_value 
                if op.edited_label_value 
                else op.skos_addition.label_value
            )
            
            lines.append(f"<{prop_uri}>")
            
            # SKOS label
            label_pred = {
                SKOSLabelType.PREF_LABEL: "skos:prefLabel",
                SKOSLabelType.ALT_LABEL: "skos:altLabel",
                SKOSLabelType.HIDDEN_LABEL: "skos:hiddenLabel"
            }[op.skos_addition.label_type]
            
            lines.append(f'    {label_pred} "{label_value}"@{op.skos_addition.language} ;')
            
            # Optional annotations
            if op.scope_note:
                lines.append(f'    skos:scopeNote "{op.scope_note}"@en ;')
            if op.example:
                lines.append(f'    skos:example "{op.example}"@en ;')
            if op.definition:
                lines.append(f'    skos:definition "{op.definition}"@en ;')
            
            # Provenance
            timestamp = op.provenance.timestamp.isoformat()
            lines.append(f'    dcterms:modified "{timestamp}"^^xsd:dateTime ;')
            
            if op.provenance.agent:
                lines.append(f'    dcterms:contributor "{op.provenance.agent}" ;')
            
            # Change note
            change_note = self._generate_change_note(op)
            lines.append(f'    skos:changeNote "{change_note}"@en .')
            lines.append("")
        
        return "\n".join(lines)
    
    def save(self, output_path: str, format: str = "turtle"):
        """Save the enriched ontology.
        
        Args:
            output_path: Path to save the enriched ontology
            format: RDF serialization format (default: turtle)
        """
        self.graph.serialize(destination=output_path, format=format)
    
    def get_property_labels(self, property_uri: str) -> Dict[str, List[str]]:
        """Get all existing SKOS labels for a property.
        
        Args:
            property_uri: URI of the property
            
        Returns:
            Dictionary mapping label types to lists of label values
        """
        prop_uri = URIRef(property_uri)
        labels = {
            "prefLabel": [],
            "altLabel": [],
            "hiddenLabel": []
        }
        
        for s, p, o in self.graph.triples((prop_uri, None, None)):
            if p == SKOS.prefLabel:
                labels["prefLabel"].append(str(o))
            elif p == SKOS.altLabel:
                labels["altLabel"].append(str(o))
            elif p == SKOS.hiddenLabel:
                labels["hiddenLabel"].append(str(o))
        
        return labels
