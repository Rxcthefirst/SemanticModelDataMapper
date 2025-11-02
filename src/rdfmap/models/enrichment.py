"""Data models for ontology enrichment operations.

This module provides models for SKOS label enrichment, provenance tracking,
and interactive enrichment workflows.
"""

from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class SKOSLabelType(str, Enum):
    """Type of SKOS label to add."""
    PREF_LABEL = "prefLabel"
    ALT_LABEL = "altLabel"
    HIDDEN_LABEL = "hiddenLabel"


class EnrichmentAction(str, Enum):
    """Action taken during enrichment."""
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    EDITED = "edited"
    SKIPPED = "skipped"


class SKOSAddition(BaseModel):
    """A SKOS label addition to be applied to a property."""
    property_uri: str = Field(description="URI of the property to enrich")
    property_label: str = Field(description="Human-readable label of the property")
    label_type: SKOSLabelType = Field(description="Type of SKOS label to add")
    label_value: str = Field(description="The label value to add")
    language: str = Field(default="en", description="Language tag for the label")
    rationale: str = Field(description="Why this label is being added")
    confidence: float = Field(
        ge=0.0, le=1.0,
        description="Confidence score of the suggested mapping"
    )
    source_column: str = Field(description="Original column name from data")


class ProvenanceInfo(BaseModel):
    """Provenance metadata for an enrichment operation."""
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    agent: Optional[str] = Field(
        default=None,
        description="User or system that performed the enrichment"
    )
    alignment_report_source: Optional[str] = Field(
        default=None,
        description="Path to the alignment report that suggested this enrichment"
    )
    tool_version: str = Field(default="rdfmap-1.0.0")
    comment: Optional[str] = Field(
        default=None,
        description="Additional notes about this enrichment"
    )


class EnrichmentOperation(BaseModel):
    """A single enrichment operation with provenance."""
    skos_addition: SKOSAddition
    action: EnrichmentAction
    provenance: ProvenanceInfo
    edited_label_value: Optional[str] = Field(
        default=None,
        description="Modified label value if action was EDITED"
    )
    scope_note: Optional[str] = Field(
        default=None,
        description="Optional skos:scopeNote to add"
    )
    example: Optional[str] = Field(
        default=None,
        description="Optional skos:example to add"
    )
    definition: Optional[str] = Field(
        default=None,
        description="Optional skos:definition to add"
    )


class EnrichmentResult(BaseModel):
    """Result of an enrichment operation."""
    success: bool
    operations_applied: List[EnrichmentOperation] = Field(default_factory=list)
    operations_rejected: List[EnrichmentOperation] = Field(default_factory=list)
    enriched_ontology_path: Optional[str] = None
    turtle_additions: str = Field(
        default="",
        description="Generated Turtle syntax for the additions"
    )
    errors: List[str] = Field(default_factory=list)
    
    @property
    def total_operations(self) -> int:
        """Total number of operations processed."""
        return len(self.operations_applied) + len(self.operations_rejected)
    
    @property
    def acceptance_rate(self) -> float:
        """Percentage of operations that were accepted."""
        if self.total_operations == 0:
            return 0.0
        return len(self.operations_applied) / self.total_operations


class EnrichmentStats(BaseModel):
    """Statistics about the enrichment session."""
    total_suggestions: int = 0
    accepted: int = 0
    rejected: int = 0
    edited: int = 0
    skipped: int = 0
    pref_labels_added: int = 0
    alt_labels_added: int = 0
    hidden_labels_added: int = 0
    scope_notes_added: int = 0
    examples_added: int = 0
    definitions_added: int = 0
    
    @property
    def acceptance_rate(self) -> float:
        """Percentage of suggestions that were accepted or edited."""
        if self.total_suggestions == 0:
            return 0.0
        return (self.accepted + self.edited) / self.total_suggestions
    
    def increment(self, action: EnrichmentAction, label_type: SKOSLabelType, 
                  has_scope_note: bool = False, has_example: bool = False,
                  has_definition: bool = False):
        """Increment counters based on an enrichment operation."""
        if action == EnrichmentAction.ACCEPTED:
            self.accepted += 1
        elif action == EnrichmentAction.REJECTED:
            self.rejected += 1
        elif action == EnrichmentAction.EDITED:
            self.edited += 1
        elif action == EnrichmentAction.SKIPPED:
            self.skipped += 1
        
        if action in (EnrichmentAction.ACCEPTED, EnrichmentAction.EDITED):
            if label_type == SKOSLabelType.PREF_LABEL:
                self.pref_labels_added += 1
            elif label_type == SKOSLabelType.ALT_LABEL:
                self.alt_labels_added += 1
            elif label_type == SKOSLabelType.HIDDEN_LABEL:
                self.hidden_labels_added += 1
            
            if has_scope_note:
                self.scope_notes_added += 1
            if has_example:
                self.examples_added += 1
            if has_definition:
                self.definitions_added += 1


class InteractivePromptResponse(BaseModel):
    """Response from an interactive enrichment prompt."""
    action: EnrichmentAction
    edited_label: Optional[str] = None
    scope_note: Optional[str] = None
    example: Optional[str] = None
    definition: Optional[str] = None
    skip_remaining: bool = False
