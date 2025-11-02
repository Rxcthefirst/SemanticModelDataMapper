"""Data models for semantic alignment reporting.

This module provides models for tracking and reporting the quality of 
semantic alignment between spreadsheet data and ontologies, including
unmapped columns, weak matches, and suggestions for ontology enrichment.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class MatchType(str, Enum):
    """Type of match between column and property."""
    EXACT_PREF_LABEL = "exact_pref_label"  # Exact match with skos:prefLabel
    EXACT_LABEL = "exact_label"  # Exact match with rdfs:label
    EXACT_ALT_LABEL = "exact_alt_label"  # Exact match with skos:altLabel
    EXACT_HIDDEN_LABEL = "exact_hidden_label"  # Exact match with skos:hiddenLabel
    EXACT_LOCAL_NAME = "exact_local_name"  # Exact match with property local name
    PARTIAL = "partial"  # Partial string match
    FUZZY = "fuzzy"  # Fuzzy/similarity match
    MANUAL = "manual"  # Manually specified in config
    UNMAPPED = "unmapped"  # No match found


class ConfidenceLevel(str, Enum):
    """Confidence level for a match."""
    HIGH = "high"  # 0.8 - 1.0
    MEDIUM = "medium"  # 0.5 - 0.79
    LOW = "low"  # 0.3 - 0.49
    VERY_LOW = "very_low"  # 0.0 - 0.29


class UnmappedColumn(BaseModel):
    """Information about a column that couldn't be mapped."""
    column_name: str = Field(description="Name of the unmapped column")
    sample_values: List[Any] = Field(
        default_factory=list,
        description="Sample values from the column (up to 5)"
    )
    inferred_datatype: Optional[str] = Field(
        default=None,
        description="Inferred XSD datatype"
    )
    reason: str = Field(
        default="No matching property found in ontology",
        description="Reason why column couldn't be mapped"
    )


class SKOSEnrichmentSuggestion(BaseModel):
    """Suggestion for enriching ontology with SKOS labels."""
    property_uri: str = Field(description="URI of the property to enrich")
    property_label: str = Field(description="Human-readable property label")
    suggested_label_type: str = Field(
        description="Type of SKOS label to add (altLabel, hiddenLabel)"
    )
    suggested_label_value: str = Field(
        description="The column name that should be added as a label"
    )
    turtle_snippet: str = Field(
        description="Ready-to-add Turtle syntax for the SKOS triple"
    )
    justification: str = Field(
        description="Why this suggestion is being made"
    )


class WeakMatch(BaseModel):
    """Information about a low-confidence match that needs review."""
    column_name: str = Field(description="Name of the column")
    matched_property: str = Field(description="URI of the matched property")
    match_type: MatchType = Field(description="Type of match that was made")
    confidence_score: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence score between 0 and 1"
    )
    confidence_level: ConfidenceLevel = Field(
        description="Categorical confidence level"
    )
    matched_via: str = Field(
        description="What label/name was used for the match"
    )
    sample_values: List[Any] = Field(
        default_factory=list,
        description="Sample values from the column"
    )
    suggestions: List[SKOSEnrichmentSuggestion] = Field(
        default_factory=list,
        description="Suggestions to improve this match"
    )


class AlignmentStatistics(BaseModel):
    """Summary statistics for the alignment."""
    total_columns: int = Field(description="Total number of columns in spreadsheet")
    mapped_columns: int = Field(description="Number of successfully mapped columns")
    unmapped_columns: int = Field(description="Number of unmapped columns")
    high_confidence_matches: int = Field(description="Matches with confidence >= 0.8")
    medium_confidence_matches: int = Field(description="Matches with confidence 0.5-0.79")
    low_confidence_matches: int = Field(description="Matches with confidence 0.3-0.49")
    very_low_confidence_matches: int = Field(description="Matches with confidence < 0.3")
    mapping_success_rate: float = Field(
        ge=0.0,
        le=1.0,
        description="Percentage of columns successfully mapped (0-1)"
    )
    average_confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Average confidence score across all matches"
    )


class AlignmentReport(BaseModel):
    """Complete alignment report for a mapping generation session."""
    
    # Metadata
    generated_at: datetime = Field(
        default_factory=datetime.now,
        description="Timestamp when report was generated"
    )
    ontology_file: str = Field(description="Path to the ontology file")
    spreadsheet_file: str = Field(description="Path to the spreadsheet file")
    target_class: str = Field(description="Target ontology class for mapping")
    
    # Statistics
    statistics: AlignmentStatistics = Field(
        description="Summary statistics for the alignment"
    )
    
    # Details
    unmapped_columns: List[UnmappedColumn] = Field(
        default_factory=list,
        description="Columns that couldn't be mapped"
    )
    weak_matches: List[WeakMatch] = Field(
        default_factory=list,
        description="Low-confidence matches requiring review"
    )
    skos_enrichment_suggestions: List[SKOSEnrichmentSuggestion] = Field(
        default_factory=list,
        description="Suggestions for enriching the ontology with SKOS labels"
    )
    
    # Configuration
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary with proper JSON encoding."""
        return self.model_dump(mode='json')
    
    def summary_message(self) -> str:
        """Generate a human-readable summary message."""
        stats = self.statistics
        lines = [
            f"Semantic Alignment Report",
            f"=" * 50,
            f"Generated: {self.generated_at.strftime('%Y-%m-%d %H:%M:%S')}",
            f"Ontology: {self.ontology_file}",
            f"Spreadsheet: {self.spreadsheet_file}",
            f"Target Class: {self.target_class}",
            f"",
            f"Statistics:",
            f"  Total Columns: {stats.total_columns}",
            f"  Mapped: {stats.mapped_columns} ({stats.mapping_success_rate:.1%})",
            f"  Unmapped: {stats.unmapped_columns}",
            f"",
            f"Confidence Distribution:",
            f"  High (≥0.8):     {stats.high_confidence_matches}",
            f"  Medium (0.5-0.8): {stats.medium_confidence_matches}",
            f"  Low (0.3-0.5):    {stats.low_confidence_matches}",
            f"  Very Low (<0.3):  {stats.very_low_confidence_matches}",
            f"  Average: {stats.average_confidence:.2f}",
            f"",
        ]
        
        if self.unmapped_columns:
            lines.append(f"⚠️  {len(self.unmapped_columns)} unmapped columns need attention")
        
        if self.weak_matches:
            lines.append(f"⚠️  {len(self.weak_matches)} weak matches need review")
        
        if self.skos_enrichment_suggestions:
            lines.append(f"💡 {len(self.skos_enrichment_suggestions)} SKOS enrichment suggestions available")
        
        return "\n".join(lines)


def calculate_confidence_score(match_type: MatchType, similarity: float = 1.0) -> float:
    """Calculate confidence score based on match type and similarity.
    
    Args:
        match_type: Type of match that was made
        similarity: Similarity score for fuzzy matches (0-1)
        
    Returns:
        Confidence score between 0 and 1
    """
    base_scores = {
        MatchType.EXACT_PREF_LABEL: 1.0,
        MatchType.EXACT_LABEL: 0.95,
        MatchType.EXACT_ALT_LABEL: 0.90,
        MatchType.EXACT_HIDDEN_LABEL: 0.85,
        MatchType.EXACT_LOCAL_NAME: 0.80,
        MatchType.PARTIAL: 0.60,
        MatchType.FUZZY: 0.40,
        MatchType.MANUAL: 1.0,
        MatchType.UNMAPPED: 0.0,
    }
    
    base_score = base_scores.get(match_type, 0.5)
    
    # For fuzzy matches, scale by similarity
    if match_type == MatchType.FUZZY:
        return base_score * similarity
    
    return base_score


def get_confidence_level(score: float) -> ConfidenceLevel:
    """Get categorical confidence level from numeric score.
    
    Args:
        score: Confidence score between 0 and 1
        
    Returns:
        Categorical confidence level
    """
    if score >= 0.8:
        return ConfidenceLevel.HIGH
    elif score >= 0.5:
        return ConfidenceLevel.MEDIUM
    elif score >= 0.3:
        return ConfidenceLevel.LOW
    else:
        return ConfidenceLevel.VERY_LOW
