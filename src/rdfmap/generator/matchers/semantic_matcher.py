"""Enhanced semantic similarity matcher using embeddings with context awareness."""

from typing import Optional, List, Dict
from .base import ColumnPropertyMatcher, MatchResult, MatchContext, MatchPriority
from ..ontology_analyzer import OntologyProperty
from ..data_analyzer import DataFieldAnalysis
from ..semantic_matcher import SemanticMatcher as EmbeddingsMatcher
from ...models.alignment import MatchType


class SemanticSimilarityMatcher(ColumnPropertyMatcher):
    """Enhanced semantic matcher with class-aware and context-aware features.

    Combines embeddings with:
    - Domain/class awareness (boost when context properties share same domain)
    - Co-occurrence context boosts
    - Enhanced label and comment integration
    - Lexical fallback when embeddings unavailable
    """

    def __init__(
        self,
        enabled: bool = True,
        threshold: float = 0.6,
        model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
        reasoner=None,
        use_embeddings: bool = True,
        domain_boost: float = 0.1,
        cooccurrence_boost: float = 0.05
    ):
        super().__init__(enabled, threshold)
        self.reasoner = reasoner
        self.use_embeddings = use_embeddings
        self.domain_boost = domain_boost
        self.cooccurrence_boost = cooccurrence_boost

        # Initialize embeddings if available and enabled
        self._embeddings_matcher = None
        if enabled and use_embeddings:
            try:
                self._embeddings_matcher = EmbeddingsMatcher(model_name)
            except Exception:
                # Fall back to lexical matching if embeddings fail
                pass

        # Build property domain cache for context awareness
        self._prop_domain: Dict[str, Optional[str]] = {}
        if reasoner:
            self._prop_domain = {
                str(uri): (str(prop.domain) if prop.domain else None)
                for uri, prop in reasoner.properties.items()
            }

    def name(self) -> str:
        return "SemanticSimilarityMatcher"

    def priority(self) -> MatchPriority:
        return MatchPriority.MEDIUM

    def match(
        self,
        column: DataFieldAnalysis,
        properties: List[OntologyProperty],
        context: Optional[MatchContext] = None
    ) -> Optional[MatchResult]:
        if not self.enabled or not properties:
            return None

        # Get base scores from embeddings or lexical fallback
        base_scores = self._get_base_scores(column, properties)

        # Apply context-aware boosts
        final_scores = self._apply_context_boosts(base_scores, properties, context)

        # Find best match above threshold
        best_prop = None
        best_score = 0.0

        for prop in properties:
            prop_uri = str(prop.uri)
            score = final_scores.get(prop_uri, 0.0)

            if score > best_score and score >= self.threshold:
                best_score = score
                best_prop = prop

        if best_prop:
            # Determine if context was used
            base_score = base_scores.get(str(best_prop.uri), 0.0)
            context_used = abs(best_score - base_score) > 0.01

            if context_used:
                matched_via = f"enhanced_semantic(base={base_score:.3f}, final={best_score:.3f})"
            else:
                matched_via = f"semantic_similarity: {best_score:.3f}"

            return MatchResult(
                property=best_prop,
                match_type=MatchType.SEMANTIC_SIMILARITY,
                confidence=best_score,
                matched_via=matched_via,
                matcher_name=self.name()
            )

        return None

    def _get_base_scores(self, column: DataFieldAnalysis, properties: List[OntologyProperty]) -> Dict[str, float]:
        """Get base similarity scores using embeddings or lexical fallback."""
        scores = {}

        # Try embeddings first
        if self._embeddings_matcher:
            result = self._embeddings_matcher.match(column, properties, threshold=0.0)
            if result:
                best_prop, similarity = result
                scores[str(best_prop.uri)] = float(similarity)

        # Fill in remaining with lexical scores (or if embeddings failed)
        lexical_scores = self._get_lexical_scores(column, properties)
        for prop_uri, score in lexical_scores.items():
            if prop_uri not in scores:
                scores[prop_uri] = score

        return scores

    def _get_lexical_scores(self, column: DataFieldAnalysis, properties: List[OntologyProperty]) -> Dict[str, float]:
        """Lexical similarity fallback using labels, comments, and abbreviations."""
        col_name = column.name.lower().replace('_', ' ').replace('-', ' ')

        # Expand common abbreviations
        expansions = {
            'fname': 'first name',
            'lname': 'last name',
            'mname': 'middle name',
            'middle initial': 'middle name',
            'dob': 'birth date',
            'birth city': 'birth place',
            'email address': 'email',
            'phone': 'phone number',
            'postal code': 'zip code',
            'zipcode': 'zip code',
            'city name': 'city',
            'address': 'street address',
        }

        expanded_col = col_name
        for abbrev, full in expansions.items():
            if abbrev in col_name:
                expanded_col = col_name.replace(abbrev, full)
                break

        scores = {}
        for prop in properties:
            prop_uri = str(prop.uri)

            # Build property text from labels, comments, local name
            text_parts = []
            text_parts.extend(prop.get_all_labels())
            if prop.comment:
                text_parts.append(prop.comment)

            # Add local name
            local_name = prop_uri.split('#')[-1].split('/')[-1]
            text_parts.append(local_name)

            prop_text = " ".join(text_parts).lower().replace('_', ' ').replace('-', ' ')

            # Calculate similarity
            score = 0.0

            # Exact match
            if expanded_col == prop_text or col_name == prop_text:
                score = 1.0
            # Strong substring match
            elif expanded_col in prop_text or any(label.lower() in col_name for label in prop.get_all_labels()):
                score = 0.8
            else:
                # Word overlap with comments included
                col_words = set(expanded_col.split())
                prop_words = set(prop_text.split())

                if col_words and prop_words:
                    overlap = len(col_words & prop_words)
                    total = len(col_words | prop_words)
                    if total > 0:
                        score = (overlap / total) * 0.7

            scores[prop_uri] = score

        return scores

    def _apply_context_boosts(
        self,
        base_scores: Dict[str, float],
        properties: List[OntologyProperty],
        context: Optional[MatchContext]
    ) -> Dict[str, float]:
        """Apply domain-aware and co-occurrence boosts based on context."""
        if not context or not getattr(context, 'matched_properties', None) or not self.reasoner:
            return base_scores.copy()

        final_scores = base_scores.copy()
        matched_prop_uris = set(str(u) for u in context.matched_properties.values())

        # Get domains of already matched properties
        matched_domains = set()
        for uri in matched_prop_uris:
            domain = self._prop_domain.get(uri)
            if domain:
                matched_domains.add(domain)

        # Apply boosts to properties that share domains with matched ones
        for prop in properties:
            prop_uri = str(prop.uri)
            prop_domain = self._prop_domain.get(prop_uri)

            if prop_domain and prop_domain in matched_domains:
                # Domain boost: properties from same class/domain
                final_scores[prop_uri] = min(1.0, final_scores.get(prop_uri, 0.0) + self.domain_boost)

                # Co-occurrence boost: additional small boost for sibling properties
                if any(self._prop_domain.get(u) == prop_domain for u in matched_prop_uris):
                    final_scores[prop_uri] = min(1.0, final_scores[prop_uri] + self.cooccurrence_boost)

        return final_scores

