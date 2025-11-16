"""Graph-based ontology reasoning matcher.

This matcher leverages deep semantic structure of the ontology to make
intelligent matching decisions based on:
- Class hierarchies and inheritance
- Domain/Range validation
- Property relationships and paths
- Semantic distance and relevance
"""

from typing import List, Optional, Dict, Set, Tuple
from collections import defaultdict
from .base import (
    ColumnPropertyMatcher,
    MatchResult,
    MatchContext,
    MatchPriority
)
from ..ontology_analyzer import OntologyProperty
from ..data_analyzer import DataFieldAnalysis
from ..graph_reasoner import GraphReasoner
from ...models.alignment import MatchType


class GraphReasoningMatcher(ColumnPropertyMatcher):
    """Advanced matcher using ontology graph structure for reasoning.

    This matcher goes beyond simple label matching to understand the semantic
    context of properties within the ontology. It considers:

    1. Domain/Range compatibility with inferred data types
    2. Property inheritance from parent classes
    3. Semantic paths through the ontology
    4. Related properties that might be better matches
    5. Structural patterns in the data

    This matcher is particularly powerful when:
    - The ontology has rich hierarchical structure
    - Properties have well-defined domains and ranges
    - Data types can be reliably inferred
    - Context about related columns is available
    """

    def __init__(
        self,
        reasoner: GraphReasoner,
        enabled: bool = True,
        threshold: float = 0.6,
        validate_types: bool = True,
        use_inheritance: bool = True
    ):
        """Initialize graph reasoning matcher.

        Args:
            reasoner: GraphReasoner instance for ontology analysis
            enabled: Whether this matcher is active
            threshold: Minimum confidence for matches
            validate_types: Whether to validate data type compatibility
            use_inheritance: Whether to consider inherited properties
        """
        super().__init__(enabled, threshold)
        self.reasoner = reasoner
        self.validate_types = validate_types
        self.use_inheritance = use_inheritance

    def name(self) -> str:
        return "GraphReasoningMatcher"

    def priority(self) -> MatchPriority:
        return MatchPriority.MEDIUM

    def match(
        self,
        column: DataFieldAnalysis,
        properties: List[OntologyProperty],
        context: Optional[MatchContext] = None
    ) -> Optional[MatchResult]:
        """Match column using graph reasoning.

        Strategy:
        1. Score each property based on structural fit
        2. Validate domain/range compatibility
        3. Consider inherited properties
        4. Factor in semantic distance
        5. Return best match above threshold
        """
        if not self.enabled:
            return None

        best_match = None
        best_score = 0.0

        for prop in properties:
            score = self._score_property(column, prop, context)

            if score > best_score and score >= self.threshold:
                best_score = score
                best_match = prop

        if best_match:
            return MatchResult(
                property=best_match,
                match_type=MatchType.GRAPH_REASONING,
                confidence=best_score,
                matched_via=f"graph_reasoning(score={best_score:.3f})",
                matcher_name=self.name()
            )

        return None

    def _score_property(
        self,
        column: DataFieldAnalysis,
        prop: OntologyProperty,
        context: Optional[MatchContext]
    ) -> float:
        """Score a property based on graph reasoning.

        Returns:
            Score from 0.0 to 1.0
        """
        scores = []
        weights = []

        # 1. Data type compatibility (if validation enabled)
        if self.validate_types and column.inferred_type:
            is_valid, type_confidence = self.reasoner.validate_property_for_data_type(
                prop, column.inferred_type
            )
            if not is_valid:
                # Hard fail on type mismatch
                return 0.0
            scores.append(type_confidence)
            weights.append(0.3)

        # 2. Structural pattern matching
        if context and context.all_columns:
            structure_score = self._score_structural_fit(column, prop, context)
            if structure_score > 0:
                scores.append(structure_score)
                weights.append(0.25)

        # 3. Property context relevance
        context_score = self._score_property_context(column, prop)
        if context_score > 0:
            scores.append(context_score)
            weights.append(0.2)

        # 4. Semantic label similarity (as baseline)
        label_score = self._score_label_similarity(column, prop)
        scores.append(label_score)
        weights.append(0.25)

        # Calculate weighted average
        if not scores:
            return 0.0

        total_weight = sum(weights)
        weighted_score = sum(s * w for s, w in zip(scores, weights)) / total_weight

        return weighted_score

    def _score_structural_fit(
        self,
        column: DataFieldAnalysis,
        prop: OntologyProperty,
        context: MatchContext
    ) -> float:
        """Score based on structural patterns in the data.

        This looks for patterns like:
        - Foreign key relationships (if prop is ObjectProperty)
        - Related columns that map to sibling properties
        - Hierarchical data structures
        """
        score = 0.0

        # Check if this is an object property and column looks like FK
        if prop.is_object_property:
            # Look for FK patterns in column name
            fk_indicators = ['_id', 'id', 'ref', 'key', 'fk']
            col_name_lower = column.name.lower()

            if any(indicator in col_name_lower for indicator in fk_indicators):
                score += 0.4

            # Check if there's a unique constraint (typical for FKs)
            if column.is_unique:
                score += 0.2

        # Check if sibling properties are also matched by nearby columns
        if prop.domain:
            prop_context = self.reasoner.get_property_context(prop.uri)
            sibling_props = prop_context.sibling_properties

            if sibling_props and len(context.all_columns) > 1:
                # Check if other columns might match sibling properties
                matched_siblings = 0
                for sibling in sibling_props[:5]:  # Check up to 5 siblings
                    for other_col in context.all_columns:
                        if other_col.name != column.name:
                            if self._columns_match_roughly(other_col.name, sibling):
                                matched_siblings += 1
                                break

                if matched_siblings > 0:
                    # More matched siblings = stronger structural fit
                    sibling_score = min(matched_siblings / 3.0, 0.3)
                    score += sibling_score

        return min(score, 1.0)

    def _score_property_context(
        self,
        column: DataFieldAnalysis,
        prop: OntologyProperty
    ) -> float:
        """Score based on property's position in ontology.

        Properties that are:
        - Part of well-defined classes
        - Have clear domains and ranges
        - Are not too generic

        Score higher than orphaned or overly generic properties.
        """
        score = 0.0

        try:
            prop_context = self.reasoner.get_property_context(prop.uri)

            # Has well-defined domain
            if prop.domain:
                score += 0.3

            # Has well-defined range
            if prop.range_type:
                score += 0.2

            # Part of a larger class structure (has siblings)
            if prop_context.sibling_properties:
                num_siblings = len(prop_context.sibling_properties)
                # More siblings suggests it's part of a coherent model
                sibling_score = min(num_siblings / 10.0, 0.2)
                score += sibling_score

            # Has parent properties (specialized from more general property)
            if prop_context.parent_properties:
                score += 0.15

            # Domain has ancestors (part of class hierarchy)
            if prop_context.domain_ancestors:
                hierarchy_depth = len(prop_context.domain_ancestors)
                hierarchy_score = min(hierarchy_depth / 5.0, 0.15)
                score += hierarchy_score

        except Exception:
            # If we can't get context, neutral score
            score = 0.5

        return min(score, 1.0)

    def _score_label_similarity(
        self,
        column: DataFieldAnalysis,
        prop: OntologyProperty
    ) -> float:
        """Basic label-based similarity as fallback."""
        col_name_lower = column.name.lower().replace('_', ' ').replace('-', ' ')

        # Check all labels
        all_labels = prop.get_all_labels()

        max_similarity = 0.0
        for label in all_labels:
            label_lower = label.lower().replace('_', ' ').replace('-', ' ')

            # Exact match
            if col_name_lower == label_lower:
                max_similarity = max(max_similarity, 1.0)
                continue

            # Substring match
            if col_name_lower in label_lower or label_lower in col_name_lower:
                max_similarity = max(max_similarity, 0.7)
                continue

            # Word overlap
            col_words = set(col_name_lower.split())
            label_words = set(label_lower.split())

            if col_words and label_words:
                overlap = len(col_words & label_words)
                max_words = max(len(col_words), len(label_words))
                word_score = overlap / max_words
                max_similarity = max(max_similarity, word_score * 0.6)

        return max_similarity

    def _columns_match_roughly(self, column_name: str, prop: OntologyProperty) -> bool:
        """Quick check if column name roughly matches property."""
        col_lower = column_name.lower().replace('_', ' ')

        for label in prop.get_all_labels():
            label_lower = label.lower().replace('_', ' ')
            if col_lower in label_lower or label_lower in col_lower:
                return True

            # Check word overlap
            col_words = set(col_lower.split())
            label_words = set(label_lower.split())
            if len(col_words & label_words) >= min(len(col_words), len(label_words)) // 2:
                return True

        return False


class InheritanceAwareMatcher(ColumnPropertyMatcher):
    """Matcher that considers inherited properties from parent classes.

    When matching columns to a specific class, this matcher also considers
    properties inherited from parent classes in the ontology hierarchy.

    Example: If matching to a "MortgageLoan" class, also consider properties
    from parent "Loan" or "FinancialInstrument" classes.
    """

    def __init__(
        self,
        reasoner: GraphReasoner,
        target_class: Optional[str] = None,
        enabled: bool = True,
        threshold: float = 0.7
    ):
        """Initialize inheritance-aware matcher.

        Args:
            reasoner: GraphReasoner instance
            target_class: URI of target class to match to (optional)
            enabled: Whether this matcher is active
            threshold: Minimum confidence for matches
        """
        super().__init__(enabled, threshold)
        self.reasoner = reasoner
        self.target_class = target_class

    def name(self) -> str:
        return "InheritanceAwareMatcher"

    def priority(self) -> MatchPriority:
        return MatchPriority.MEDIUM

    def match(
        self,
        column: DataFieldAnalysis,
        properties: List[OntologyProperty],
        context: Optional[MatchContext] = None
    ) -> Optional[MatchResult]:
        """Match considering inherited properties."""
        if not self.enabled or not self.target_class:
            return None

        # Get inherited properties
        from rdflib import URIRef
        class_uri = URIRef(self.target_class)
        inherited_props = self.reasoner.get_inherited_properties(class_uri)

        # Expand property list with inherited ones
        all_props_map = {p.uri: p for p in properties}
        for inherited_prop in inherited_props:
            if inherited_prop.uri not in all_props_map:
                all_props_map[inherited_prop.uri] = inherited_prop

        expanded_properties = list(all_props_map.values())

        # Try to match with expanded list
        best_match = None
        best_score = 0.0

        for prop in expanded_properties:
            score = self._score_property(column, prop)

            if score > best_score and score >= self.threshold:
                best_score = score
                best_match = prop

        if best_match:
            # Check if this was an inherited property
            is_inherited = best_match.uri not in [p.uri for p in properties]

            match_type = (
                MatchType.INHERITED_PROPERTY
                if is_inherited
                else MatchType.GRAPH_REASONING
            )

            matched_via = (
                f"inherited_from_parent(score={best_score:.3f})"
                if is_inherited
                else f"direct_property(score={best_score:.3f})"
            )

            return MatchResult(
                property=best_match,
                match_type=match_type,
                confidence=best_score,
                matched_via=matched_via,
                matcher_name=self.name()
            )

        return None

    def _score_property(self, column: DataFieldAnalysis, prop: OntologyProperty) -> float:
        """Score property match."""
        col_name_lower = column.name.lower().replace('_', ' ')

        for label in prop.get_all_labels():
            label_lower = label.lower().replace('_', ' ')

            # Exact match
            if col_name_lower == label_lower:
                return 1.0

            # High similarity
            if col_name_lower in label_lower or label_lower in col_name_lower:
                return 0.8

        return 0.0


class GraphContextMatcher(ColumnPropertyMatcher):
    """Enhanced matcher using property co-occurrence patterns and context.

    This matcher implements advanced context-aware matching by:
    1. Learning property co-occurrence patterns from the ontology
    2. Boosting confidence when related properties are already matched
    3. Using structural similarity across columns
    4. Propagating context through the matching process

    Example: If firstName and lastName are already matched, boost confidence
    for middleName, birthDate, and other person-related properties.
    """

    def __init__(
        self,
        reasoner: GraphReasoner,
        enabled: bool = True,
        threshold: float = 0.5,
        use_cooccurrence: bool = True,
        cooccurrence_boost: float = 0.15,
        use_probabilistic_reasoning: bool = True,
        propagation_decay: float = 0.8,
        max_evidence_sources: int = 5
    ):
        """Initialize graph context matcher.

        Args:
            reasoner: GraphReasoner instance for ontology analysis
            enabled: Whether this matcher is active
            threshold: Minimum confidence for matches
            use_cooccurrence: Whether to use co-occurrence patterns
            cooccurrence_boost: Maximum boost from co-occurrence (default 0.15)
            use_probabilistic_reasoning: Enable Bayesian-style confidence propagation
            propagation_decay: Decay factor for multi-hop evidence (0.8 = 20% decay per hop)
            max_evidence_sources: Maximum evidence sources to accumulate
        """
        super().__init__(enabled, threshold)
        self.reasoner = reasoner
        self.use_cooccurrence = use_cooccurrence
        self.cooccurrence_boost = cooccurrence_boost
        self.use_probabilistic_reasoning = use_probabilistic_reasoning
        self.propagation_decay = propagation_decay
        self.max_evidence_sources = max_evidence_sources

        # Build co-occurrence cache
        self.cooccurrence_patterns: Dict[str, Set[str]] = {}
        self.cooccurrence_probabilities: Dict[str, Dict[str, float]] = {}
        self.property_similarities: Dict[str, List[Tuple[str, float]]] = {}

        if use_cooccurrence:
            self._build_cooccurrence_cache()

        if use_probabilistic_reasoning:
            self._build_probabilistic_knowledge_base()

    def name(self) -> str:
        return "GraphContextMatcher"

    def priority(self) -> MatchPriority:
        return MatchPriority.HIGH  # High priority because context is authoritative

    def _build_cooccurrence_cache(self):
        """Build cache of properties that tend to co-occur.

        Properties co-occur when they:
        1. Share the same domain (e.g., all Person properties)
        2. Have related ranges (e.g., address components)
        3. Form semantic clusters (e.g., name properties, contact info)
        """
        # Get all properties from reasoner
        try:
            all_properties = list(self.reasoner.properties.values())

            # Group by domain
            domain_groups: Dict[str, List[OntologyProperty]] = defaultdict(list)
            for prop in all_properties:
                if prop.domain:
                    domain_groups[str(prop.domain)].append(prop)

            # Build co-occurrence sets as strings for consistency with tests
            for _domain, props in domain_groups.items():
                for prop in props:
                    cooccurring: Set[str] = set()
                    for other_prop in props:
                        if other_prop.uri != prop.uri:
                            cooccurring.add(str(other_prop.uri))
                    self.cooccurrence_patterns[str(prop.uri)] = cooccurring
        except Exception as e:
            import warnings
            warnings.warn(f"Failed to build co-occurrence cache: {e}")

    def match(
        self,
        column: DataFieldAnalysis,
        properties: List[OntologyProperty],
        context: Optional[MatchContext] = None
    ) -> Optional[MatchResult]:
        """Match column using context and co-occurrence patterns."""
        if not self.enabled:
            return None

        best_match = None
        best_score = 0.0
        base_score = 0.0
        context_boost = 0.0

        for prop in properties:
            # Base score from label similarity
            prop_base_score = self._score_label_similarity(column, prop)

            if prop_base_score < 0.3:  # Skip if label match is too weak
                continue

            # Apply context-based boosting
            prop_context_boost = 0.0
            if context and self.use_cooccurrence:
                prop_context_boost = self._calculate_cooccurrence_score(prop, context)

            # Final score
            final_score = min(prop_base_score + prop_context_boost, 1.0)

            if final_score > best_score and final_score >= self.threshold:
                best_score = final_score
                best_match = prop
                base_score = prop_base_score
                context_boost = prop_context_boost

        if best_match:
            # Determine match via string
            if context and context.matched_properties and context_boost > 0:
                matched_via = f"context_boosted(base={base_score:.3f}, boost={context_boost:.3f})"
            else:
                matched_via = f"label_match(score={best_score:.3f})"

            return MatchResult(
                property=best_match,
                match_type=MatchType.GRAPH_REASONING,
                confidence=best_score,
                matched_via=matched_via,
                matcher_name=self.name()
            )

        return None

    def _calculate_cooccurrence_score(
        self,
        prop: OntologyProperty,
        context: MatchContext
    ) -> float:
        """Calculate confidence boost based on co-occurring properties.

        Args:
            prop: Property being evaluated
            context: Matching context with already matched properties

        Returns:
            Boost value (0.0 to cooccurrence_boost)
        """
        if not context.matched_properties:
            return 0.0

        cooccurring = self.cooccurrence_patterns.get(str(prop.uri), set())
        if not cooccurring:
            return 0.0

        matched_cooccurring = 0
        for matched_prop_uri in context.matched_properties.values():
            if matched_prop_uri in cooccurring:
                matched_cooccurring += 1
        if matched_cooccurring == 0:
            return 0.0
        boost_ratio = min(matched_cooccurring / 3.0, 1.0)
        return boost_ratio * self.cooccurrence_boost

    def _score_label_similarity(
        self,
        column: DataFieldAnalysis,
        prop: OntologyProperty
    ) -> float:
        # Enhanced label similarity with common abbreviations
        col_name_lower = column.name.lower().replace('_', ' ').replace('-', ' ')

        # Abbreviation and synonym expansions
        expansions = {
            'fname': 'first name',
            'first name': 'first name',
            'lname': 'last name',
            'last name': 'last name',
            'mname': 'middle name',
            'middle initial': 'middle name',
            'dob': 'birth date',
            'birth date': 'birth date',
            'birth city': 'birth place',
            'birth place': 'birth place',
            'email address': 'email',
            'phone': 'phone number',
            'phone number': 'phone number',
            'postal code': 'zip code',
            'zipcode': 'zip code',
            'zip': 'zip code',
            'city name': 'city',
            'address': 'street address',
        }

        expanded_terms = set()
        for key, val in expansions.items():
            if key in col_name_lower:
                expanded_terms.add(val)

        all_labels = prop.get_all_labels()
        max_similarity = 0.0
        for label in all_labels:
            label_lower = label.lower().replace('_', ' ').replace('-', ' ')

            # Direct abbreviation/synonym match boost
            if label_lower in expanded_terms:
                max_similarity = max(max_similarity, 0.85)
                continue

            # Exact match
            if col_name_lower == label_lower:
                max_similarity = max(max_similarity, 1.0)
                continue

            # Substring match
            if col_name_lower in label_lower or label_lower in col_name_lower:
                max_similarity = max(max_similarity, 0.8)
                continue

            # Word overlap
            col_words = set(col_name_lower.split())
            label_words = set(label_lower.split())
            if col_words and label_words:
                overlap = len(col_words & label_words)
                total = len(col_words | label_words)
                if total > 0:
                    word_score = overlap / total
                    max_similarity = max(max_similarity, word_score * 0.7)

        return max_similarity

    def _build_probabilistic_knowledge_base(self):
        """Build probabilistic knowledge base for Bayesian reasoning."""
        try:
            # Build co-occurrence probabilities (not just binary relationships)
            all_properties = list(self.reasoner.properties.values())

            # Group by domain for probability calculations
            domain_groups = defaultdict(list)
            for prop in all_properties:
                if prop.domain:
                    domain_groups[str(prop.domain)].append(prop)

            # Calculate conditional probabilities P(prop2|prop1)
            for domain, props in domain_groups.items():
                if len(props) < 2:
                    continue

                total_props = len(props)
                for prop1 in props:
                    prop1_uri = str(prop1.uri)
                    self.cooccurrence_probabilities[prop1_uri] = {}

                    for prop2 in props:
                        if prop1.uri != prop2.uri:
                            prop2_uri = str(prop2.uri)

                            # Base probability: 1/(n-1) for uniform distribution
                            base_prob = 1.0 / (total_props - 1)

                            # Boost based on semantic similarity
                            semantic_similarity = self._calculate_semantic_similarity(prop1, prop2)

                            # Final conditional probability
                            prob = min(base_prob * (1 + semantic_similarity), 0.95)
                            self.cooccurrence_probabilities[prop1_uri][prop2_uri] = prob

            # Build property similarity graph for multi-hop reasoning
            self._build_property_similarity_graph(all_properties)

        except Exception as e:
            import warnings
            warnings.warn(f"Failed to build probabilistic knowledge base: {e}")

    def _calculate_semantic_similarity(self, prop1: OntologyProperty, prop2: OntologyProperty) -> float:
        """Calculate semantic similarity between two properties for probabilistic reasoning."""
        similarity = 0.0

        # Label similarity (word overlap)
        labels1 = []
        labels2 = []

        for label in prop1.get_all_labels():
            labels1.extend(label.lower().split())
        for label in prop2.get_all_labels():
            labels2.extend(label.lower().split())

        if labels1 and labels2:
            words1 = set(labels1)
            words2 = set(labels2)
            if words1 and words2:
                overlap = len(words1 & words2)
                total = len(words1 | words2)
                similarity += (overlap / total) * 0.5

        # Range similarity
        if prop1.range_type == prop2.range_type and prop1.range_type:
            similarity += 0.3

        # SKOS relationship similarity
        if hasattr(prop1, 'related') and hasattr(prop2, 'related'):
            prop1_relations = set(prop1.related + prop1.broader + prop1.narrower)
            prop2_relations = set(prop2.related + prop2.broader + prop2.narrower)

            if str(prop2.uri) in prop1_relations or str(prop1.uri) in prop2_relations:
                similarity += 0.4

        return min(similarity, 1.0)

    def _build_property_similarity_graph(self, properties: List[OntologyProperty]):
        """Build graph of property similarities for multi-hop reasoning."""
        for prop1 in properties:
            similarities = []
            prop1_uri = str(prop1.uri)

            for prop2 in properties:
                if prop1.uri != prop2.uri:
                    sim = self._calculate_semantic_similarity(prop1, prop2)
                    if sim > 0.1:  # Only store significant similarities
                        similarities.append((str(prop2.uri), sim))

            # Sort by similarity and keep top 10
            similarities.sort(key=lambda x: x[1], reverse=True)
            self.property_similarities[prop1_uri] = similarities[:10]

