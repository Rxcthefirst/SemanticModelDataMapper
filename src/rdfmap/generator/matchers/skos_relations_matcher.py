"""SKOS Relations Matcher leveraging broader/narrower/related/exactMatch/closeMatch semantics.

Boosts properties whose SKOS relations align with column naming or context.
"""
from typing import Optional, List
from .base import ColumnPropertyMatcher, MatchResult, MatchContext, MatchPriority
from ..ontology_analyzer import OntologyProperty
from ..data_analyzer import DataFieldAnalysis
from ...models.alignment import MatchType

class SKOSRelationsMatcher(ColumnPropertyMatcher):
    def __init__(self, enabled: bool = True, threshold: float = 0.5):
        super().__init__(enabled, threshold)

    def name(self) -> str:
        return "SKOSRelationsMatcher"

    def priority(self) -> MatchPriority:
        return MatchPriority.LOW  # run after structural/graph matchers

    def match(self, column: DataFieldAnalysis, properties: List[OntologyProperty], context: Optional[MatchContext] = None) -> Optional[MatchResult]:
        if not self.enabled:
            return None
        col_norm = column.name.lower().replace('_',' ').replace('-',' ')
        best_prop = None
        best_score = 0.0
        for prop in properties:
            score = self._score_property(col_norm, prop)
            if score > best_score and score >= self.threshold:
                best_score = score
                best_prop = prop
        if best_prop:
            return MatchResult(
                property=best_prop,
                match_type=MatchType.SEMANTIC_SIMILARITY,
                confidence=best_score,
                matched_via=f"skos_relations(score={best_score:.3f})",
                matcher_name=self.name()
            )
        return None

    def _score_property(self, col_norm: str, prop: OntologyProperty) -> float:
        score = 0.0
        # Direct label overlap baseline
        for label in prop.get_all_labels():
            lnorm = label.lower().replace('_',' ').replace('-',' ')
            if col_norm == lnorm:
                score = max(score, 0.8)
            elif col_norm in lnorm or lnorm in col_norm:
                score = max(score, 0.6)
        # Use SKOS relations
        for rel_list, boost in [
            (prop.exact_matches, 0.3),
            (prop.close_matches, 0.2),
            (prop.broader, 0.15),
            (prop.narrower, 0.15),
            (prop.related, 0.1)
        ]:
            for uri in rel_list:
                local = uri.split('#')[-1].split('/')[-1].lower()
                if local in col_norm or col_norm in local:
                    score += boost
        return min(score, 1.0)

