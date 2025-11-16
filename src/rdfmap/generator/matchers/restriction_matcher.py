"""Restriction-Based Matcher leveraging OWL restrictions for property applicability.

Uses ontology_analyzer.property_restrictions extracted from OWL Restriction axioms
(e.g., someValuesFrom, allValuesFrom, cardinality) to guide matching:
- Boost properties whose restrictions align with column data patterns (type, uniqueness)
- Penalize mismatches (e.g., cardinality vs uniqueness)
"""
from typing import Optional, List
from .base import ColumnPropertyMatcher, MatchResult, MatchContext, MatchPriority
from ..ontology_analyzer import OntologyProperty, OntologyAnalyzer
from ..data_analyzer import DataFieldAnalysis
from ...models.alignment import MatchType

class RestrictionBasedMatcher(ColumnPropertyMatcher):
    def __init__(self, ontology_analyzer: OntologyAnalyzer, enabled: bool = True, threshold: float = 0.55):
        super().__init__(enabled, threshold)
        self.ontology = ontology_analyzer

    def name(self) -> str:
        return "RestrictionBasedMatcher"

    def priority(self) -> MatchPriority:
        return MatchPriority.MEDIUM

    def match(self, column: DataFieldAnalysis, properties: List[OntologyProperty], context: Optional[MatchContext] = None) -> Optional[MatchResult]:
        if not self.enabled or not properties:
            return None
        best_prop = None
        best_score = 0.0
        for prop in properties:
            score = self._score_property(column, prop)
            if score > best_score and score >= self.threshold:
                best_score = score
                best_prop = prop
        if best_prop:
            return MatchResult(
                property=best_prop,
                match_type=MatchType.SEMANTIC_SIMILARITY,
                confidence=best_score,
                matched_via=f"restrictions(score={best_score:.3f})",
                matcher_name=self.name()
            )
        return None

    def _score_property(self, column: DataFieldAnalysis, prop: OntologyProperty) -> float:
        base = 0.0
        uri = str(prop.uri)
        restrictions = self.ontology.property_restrictions.get(uri, [])
        if not restrictions:
            return base  # no boost if no restrictions known
        for r in restrictions:
            # Cardinality handling
            if r.get('cardinality') is not None:
                card = r['cardinality']
                if card == 1 and column.is_unique:
                    base += 0.4
                elif card == 1 and not column.is_unique:
                    base -= 0.2
            # Min cardinality
            if r.get('minCardinality') is not None:
                minc = r['minCardinality']
                if minc >= 1 and column.null_percentage < 20:
                    base += 0.2
            # Max cardinality
            if r.get('maxCardinality') is not None:
                maxc = r['maxCardinality']
                if maxc == 1 and column.is_unique:
                    base += 0.2
            # Type constraints (someValuesFrom / allValuesFrom)
            expected = r.get('someValuesFrom') or r.get('allValuesFrom')
            if expected and column.inferred_type:
                # Simple heuristic: check substring match of XSD local name
                expected_local = expected.split('#')[-1].lower()
                inferred = column.inferred_type.lower()
                if expected_local in inferred or inferred in expected_local:
                    base += 0.3
                else:
                    base -= 0.1
        return max(0.0, min(base, 1.0))
