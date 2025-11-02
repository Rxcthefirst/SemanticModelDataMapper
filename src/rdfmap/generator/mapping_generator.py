"""Mapping configuration generator combining ontology and spreadsheet analysis."""

from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
import os
import yaml
import json
from pydantic import BaseModel, Field

from .ontology_analyzer import OntologyAnalyzer, OntologyClass, OntologyProperty
from .spreadsheet_analyzer import SpreadsheetAnalyzer, ColumnAnalysis
from ..models.alignment import (
    AlignmentReport,
    AlignmentStatistics,
    UnmappedColumn,
    WeakMatch,
    SKOSEnrichmentSuggestion,
    MatchType,
    calculate_confidence_score,
    get_confidence_level,
)


class GeneratorConfig(BaseModel):
    """Configuration for the mapping generator."""
    
    base_iri: str = Field(..., description="Base IRI for generated resources")
    default_class_prefix: str = Field("resource", description="Default prefix for resource IRIs")
    include_comments: bool = Field(True, description="Include comments in generated config")
    auto_detect_relationships: bool = Field(
        True, description="Attempt to detect relationships between entities"
    )
    min_confidence: float = Field(
        0.5, description="Minimum confidence score for automatic suggestions (0-1)"
    )


class MappingGenerator:
    """Generates mapping configuration from ontology and spreadsheet analysis."""
    
    def __init__(
        self,
        ontology_file: str,
        spreadsheet_file: str,
        config: GeneratorConfig,
    ):
        """
        Initialize the mapping generator.
        
        Args:
            ontology_file: Path to ontology file
            spreadsheet_file: Path to spreadsheet file
            config: Generator configuration
        """
        self.config = config
        self.ontology_file = ontology_file
        self.spreadsheet_file = spreadsheet_file
        self.ontology = OntologyAnalyzer(ontology_file)
        self.spreadsheet = SpreadsheetAnalyzer(spreadsheet_file)
        
        self.mapping: Dict[str, Any] = {}
        self.alignment_report: Optional[AlignmentReport] = None
        
        # Tracking for alignment report
        self._mapped_columns: Dict[str, Tuple[OntologyProperty, MatchType, float]] = {}
        self._unmapped_columns: List[str] = []
    
    def generate(
        self,
        target_class: Optional[str] = None,
        output_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate a mapping configuration.
        
        Args:
            target_class: URI or label of the target ontology class.
                         If None, will attempt to auto-detect.
            output_path: Path where the config will be saved. Used to compute
                        relative paths for data sources.
        
        Returns:
            Dictionary representation of the mapping configuration
        """
        self.output_path = Path(output_path) if output_path else None
        # Find target class
        if target_class:
            cls = self._resolve_class(target_class)
            if not cls:
                raise ValueError(f"Could not find class: {target_class}")
        else:
            cls = self._auto_detect_class()
            if not cls:
                raise ValueError("Could not auto-detect target class. Please specify target_class.")
        
        # Build mapping
        self.mapping = {
            "namespaces": self._generate_namespaces(),
            "defaults": self._generate_defaults(),
            "sheets": [self._generate_sheet_mapping(cls)],
            "options": self._generate_options(),
        }
        
        return self.mapping
    
    def _resolve_class(self, identifier: str) -> Optional[OntologyClass]:
        """Resolve a class by URI or label."""
        # Try as label first
        cls = self.ontology.get_class_by_label(identifier)
        if cls:
            return cls
        
        # Try to find by URI match
        for cls in self.ontology.classes.values():
            if str(cls.uri) == identifier or str(cls.uri).endswith(f"#{identifier}") or str(cls.uri).endswith(f"/{identifier}"):
                return cls
        
        return None
    
    def _auto_detect_class(self) -> Optional[OntologyClass]:
        """Attempt to auto-detect the target class based on file name."""
        # Extract name from file
        file_stem = Path(self.spreadsheet.file_path).stem
        
        # Suggest based on file name
        suggestions = self.ontology.suggest_class_for_name(file_stem)
        
        if suggestions:
            # Return first suggestion
            return suggestions[0]
        
        # Fall back to first class in ontology
        if self.ontology.classes:
            return next(iter(self.ontology.classes.values()))
        
        return None
    
    def _generate_namespaces(self) -> Dict[str, str]:
        """Generate namespace declarations."""
        namespaces = self.ontology.get_namespaces()
        
        # Ensure xsd is included
        if "xsd" not in namespaces:
            namespaces["xsd"] = "http://www.w3.org/2001/XMLSchema#"
        
        return namespaces
    
    def _generate_defaults(self) -> Dict[str, Any]:
        """Generate defaults section."""
        return {
            "base_iri": self.config.base_iri,
        }
    
    def _generate_options(self) -> Dict[str, Any]:
        """Generate processing options."""
        return {
            "on_error": "report",
            "skip_empty_values": True,
        }
    
    def _generate_sheet_mapping(self, target_class: OntologyClass) -> Dict[str, Any]:
        """Generate sheet mapping for the target class."""
        sheet_name = Path(self.spreadsheet.file_path).stem
        
        # Calculate relative path for source if output_path is provided
        source_path = Path(self.spreadsheet.file_path)
        if self.output_path:
            # Get relative path from config location to data file
            config_dir = self.output_path.parent
            try:
                # Use os.path.relpath to handle paths not in subpath
                rel_path = os.path.relpath(source_path.resolve(), config_dir.resolve())
                source_path = Path(rel_path)
            except (ValueError, OSError):
                # If not possible (e.g., different drives on Windows), use absolute path
                pass
        
        # Generate IRI template
        iri_template = self._generate_iri_template(target_class)
        
        # Map columns to properties
        column_mappings = self._generate_column_mappings(target_class)
        
        # Detect linked objects
        object_mappings = self._generate_object_mappings(target_class)
        
        sheet = {
            "name": sheet_name,
            "source": str(source_path),
            "row_resource": {
                "class": self._format_uri(target_class.uri),
                "iri_template": iri_template,
            },
            "columns": column_mappings,
        }
        
        if object_mappings:
            sheet["objects"] = object_mappings
        
        return sheet
    
    def _generate_iri_template(self, target_class: OntologyClass) -> str:
        """Generate IRI template for the target class."""
        # Get suggested identifier columns
        id_cols = self.spreadsheet.suggest_iri_template_columns()
        
        if not id_cols:
            # Fallback to first column
            id_cols = [self.spreadsheet.get_column_names()[0]]
        
        # Use class name or default prefix
        class_name = target_class.label or self.config.default_class_prefix
        class_name = class_name.lower().replace(" ", "_")
        
        # Build template
        template_parts = [f"{class_name}:{{{col}}}" for col in id_cols]
        return template_parts[0] if len(template_parts) == 1 else "_".join(template_parts)
    
    def _generate_column_mappings(self, target_class: OntologyClass) -> Dict[str, Any]:
        """Generate column to property mappings."""
        mappings = {}
        
        # Get datatype properties for this class
        properties = self.ontology.get_datatype_properties(target_class.uri)
        
        # Match columns to properties
        for col_name in self.spreadsheet.get_column_names():
            col_analysis = self.spreadsheet.get_analysis(col_name)
            
            # Find matching property
            match_result = self._match_column_to_property(col_name, col_analysis, properties)
            
            if match_result:
                matched_prop, match_type, matched_via = match_result
                confidence = calculate_confidence_score(match_type)
                
                # Track for alignment report
                self._mapped_columns[col_name] = (matched_prop, match_type, confidence)
                
                mapping = {
                    "as": self._format_uri(matched_prop.uri),
                }
                
                # Add datatype if available
                if col_analysis.suggested_datatype:
                    mapping["datatype"] = col_analysis.suggested_datatype
                
                # Add required flag
                if col_analysis.is_required:
                    mapping["required"] = True
                
                # Add comment if enabled
                if self.config.include_comments and matched_prop.comment:
                    mapping["_comment"] = matched_prop.comment
                
                mappings[col_name] = mapping
            else:
                # Track unmapped column
                self._unmapped_columns.append(col_name)
        
        return mappings
    
    def _match_column_to_property(
        self,
        col_name: str,
        col_analysis: ColumnAnalysis,
        properties: List[OntologyProperty],
    ) -> Optional[Tuple[OntologyProperty, MatchType, str]]:
        """
        Match a column to an ontology property using multiple strategies.
        
        Matching priority:
        1. Exact match with SKOS prefLabel
        2. Exact match with rdfs:label
        3. Exact match with SKOS altLabel
        4. Exact match with SKOS hiddenLabel
        5. Exact match with local name
        6. Partial match with any label
        7. Fuzzy match with local name
        
        Returns:
            Tuple of (property, match_type, matched_via) or None if no match found
        """
        col_lower = col_name.lower().replace("_", "").replace(" ", "")
        
        # Priority 1: Exact match with SKOS prefLabel
        for prop in properties:
            if prop.pref_label:
                pref_label_clean = prop.pref_label.lower().replace("_", "").replace(" ", "")
                if col_lower == pref_label_clean:
                    return (prop, MatchType.EXACT_PREF_LABEL, prop.pref_label)
        
        # Priority 2: Exact match with rdfs:label
        for prop in properties:
            if prop.label:
                prop_label_clean = prop.label.lower().replace("_", "").replace(" ", "")
                if col_lower == prop_label_clean:
                    return (prop, MatchType.EXACT_LABEL, prop.label)
        
        # Priority 3: Exact match with SKOS altLabel
        for prop in properties:
            for alt_label in prop.alt_labels:
                alt_label_clean = alt_label.lower().replace("_", "").replace(" ", "")
                if col_lower == alt_label_clean:
                    return (prop, MatchType.EXACT_ALT_LABEL, alt_label)
        
        # Priority 4: Exact match with SKOS hiddenLabel
        for prop in properties:
            for hidden_label in prop.hidden_labels:
                hidden_label_clean = hidden_label.lower().replace("_", "").replace(" ", "")
                if col_lower == hidden_label_clean:
                    return (prop, MatchType.EXACT_HIDDEN_LABEL, hidden_label)
        
        # Priority 5: Exact match with local name
        for prop in properties:
            local_name = str(prop.uri).split("#")[-1].split("/")[-1]
            local_clean = local_name.lower().replace("_", "")
            if col_lower == local_clean:
                return (prop, MatchType.EXACT_LOCAL_NAME, local_name)
        
        # Priority 6: Partial match with any label (pref, rdfs, alt)
        for prop in properties:
            all_labels = []
            if prop.pref_label:
                all_labels.append(prop.pref_label)
            if prop.label:
                all_labels.append(prop.label)
            all_labels.extend(prop.alt_labels)
            
            for label in all_labels:
                label_clean = label.lower().replace("_", "").replace(" ", "")
                if col_lower in label_clean or label_clean in col_lower:
                    return (prop, MatchType.PARTIAL, label)
        
        # Priority 7: Fuzzy match with local name
        for prop in properties:
            local_name = str(prop.uri).split("#")[-1].split("/")[-1]
            local_clean = local_name.lower().replace("_", "")
            if col_lower in local_clean or local_clean in col_lower:
                return (prop, MatchType.FUZZY, local_name)
        
        return None
    
    def _generate_object_mappings(self, target_class: OntologyClass) -> Dict[str, Any]:
        """Generate linked object mappings (object properties)."""
        if not self.config.auto_detect_relationships:
            return {}
        
        object_mappings = {}
        
        # Get object properties for this class
        obj_properties = self.ontology.get_object_properties(target_class.uri)
        
        # For each object property, check if we can create a linked object
        for prop in obj_properties:
            if not prop.range_type or prop.range_type not in self.ontology.classes:
                continue
            
            range_class = self.ontology.classes[prop.range_type]
            
            # Check if we have columns that could belong to this object
            potential_cols = self._find_columns_for_object(range_class)
            
            if potential_cols:
                obj_name = prop.label or str(prop.uri).split("#")[-1].split("/")[-1]
                
                object_mappings[obj_name] = {
                    "predicate": self._format_uri(prop.uri),
                    "class": self._format_uri(range_class.uri),
                    "iri_template": self._generate_iri_template(range_class),
                    "properties": [
                        {
                            "column": col_name,
                            "as": self._format_uri(prop.uri),
                        }
                        for col_name, prop in potential_cols
                    ],
                }
        
        return object_mappings
    
    def _find_columns_for_object(
        self, range_class: OntologyClass
    ) -> List[tuple[str, OntologyProperty]]:
        """Find columns that could belong to a linked object class."""
        potential = []
        range_props = self.ontology.get_datatype_properties(range_class.uri)
        
        for col_name in self.spreadsheet.get_column_names():
            col_analysis = self.spreadsheet.get_analysis(col_name)
            match_result = self._match_column_to_property(col_name, col_analysis, range_props)
            
            if match_result:
                matched_prop, _, _ = match_result  # Unpack tuple
                potential.append((col_name, matched_prop))
        
        return potential
    
    def _format_uri(self, uri) -> str:
        """Format a URI as a CURIE if possible."""
        uri_str = str(uri)
        
        # Try to use namespaces to create CURIE
        for prefix, namespace in self.ontology.get_namespaces().items():
            if uri_str.startswith(namespace):
                local_name = uri_str[len(namespace):]
                return f"{prefix}:{local_name}"
        
        # Return full URI if no prefix found
        return uri_str
    
    def save_yaml(self, output_file: str):
        """Save the mapping to a YAML file."""
        if not self.mapping:
            raise ValueError("No mapping generated. Call generate() first.")
        
        # Regenerate with correct output path if different
        if not hasattr(self, 'output_path') or self.output_path != Path(output_file):
            # Regenerate to get correct relative paths
            target_class = None
            for sheet in self.mapping.get('sheets', []):
                class_uri = sheet['row_resource']['class']
                # Find the class
                for cls in self.ontology.classes.values():
                    if self._format_uri(cls.uri) == class_uri:
                        target_class = cls
                        break
                if target_class:
                    break
            
            if target_class:
                self.generate(target_class=target_class.label, output_path=output_file)
        
        with open(output_file, 'w') as f:
            yaml.dump(self.mapping, f, default_flow_style=False, sort_keys=False)
    
    def save_json(self, output_file: str):
        """Save the mapping to a JSON file."""
        if not self.mapping:
            raise ValueError("No mapping generated. Call generate() first.")
        
        with open(output_file, 'w') as f:
            json.dump(self.mapping, f, indent=2)
    
    def get_json_schema(self) -> Dict[str, Any]:
        """
        Generate JSON Schema from the Pydantic mapping configuration model.
        
        This can be used to validate generated mapping configurations.
        """
        from ..models.mapping import MappingConfig
        
        return MappingConfig.model_json_schema()
    
    def _build_alignment_report(self, target_class: OntologyClass) -> AlignmentReport:
        """Build alignment report after mapping generation."""
        # Collect unmapped column details
        unmapped_details = []
        for col_name in self._unmapped_columns:
            col_analysis = self.spreadsheet.get_analysis(col_name)
            unmapped_details.append(
                UnmappedColumn(
                    column_name=col_name,
                    sample_values=col_analysis.sample_values[:5],
                    inferred_datatype=col_analysis.suggested_datatype,
                    reason="No matching property found in ontology"
                )
            )
        
        # Collect weak matches and suggestions
        weak_matches = []
        skos_suggestions = []
        
        confidence_scores = []
        for col_name, (prop, match_type, confidence) in self._mapped_columns.items():
            confidence_scores.append(confidence)
            confidence_level = get_confidence_level(confidence)
            
            # Track weak matches (confidence < 0.8)
            if confidence < 0.8:
                col_analysis = self.spreadsheet.get_analysis(col_name)
                
                # Generate SKOS enrichment suggestion
                suggestion = self._generate_skos_suggestion(
                    col_name, prop, match_type
                )
                
                weak_match = WeakMatch(
                    column_name=col_name,
                    matched_property=str(prop.uri),
                    match_type=match_type,
                    confidence_score=confidence,
                    confidence_level=confidence_level,
                    matched_via=prop.label or str(prop.uri).split("#")[-1],
                    sample_values=col_analysis.sample_values[:5],
                    suggestions=[suggestion] if suggestion else []
                )
                weak_matches.append(weak_match)
                
                if suggestion:
                    skos_suggestions.append(suggestion)
        
        # Calculate statistics
        total_columns = len(self.spreadsheet.get_column_names())
        mapped_columns = len(self._mapped_columns)
        unmapped_columns = len(self._unmapped_columns)
        
        high_conf = sum(1 for c in confidence_scores if c >= 0.8)
        medium_conf = sum(1 for c in confidence_scores if 0.5 <= c < 0.8)
        low_conf = sum(1 for c in confidence_scores if 0.3 <= c < 0.5)
        very_low_conf = sum(1 for c in confidence_scores if c < 0.3)
        
        avg_confidence = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0.0
        success_rate = mapped_columns / total_columns if total_columns > 0 else 0.0
        
        statistics = AlignmentStatistics(
            total_columns=total_columns,
            mapped_columns=mapped_columns,
            unmapped_columns=unmapped_columns,
            high_confidence_matches=high_conf,
            medium_confidence_matches=medium_conf,
            low_confidence_matches=low_conf,
            very_low_confidence_matches=very_low_conf,
            mapping_success_rate=success_rate,
            average_confidence=avg_confidence
        )
        
        return AlignmentReport(
            ontology_file=self.ontology_file,
            spreadsheet_file=self.spreadsheet_file,
            target_class=target_class.label or str(target_class.uri),
            statistics=statistics,
            unmapped_columns=unmapped_details,
            weak_matches=weak_matches,
            skos_enrichment_suggestions=skos_suggestions
        )
    
    def _generate_skos_suggestion(
        self,
        col_name: str,
        prop: OntologyProperty,
        match_type: MatchType
    ) -> Optional[SKOSEnrichmentSuggestion]:
        """Generate SKOS enrichment suggestion for weak matches."""
        # Determine appropriate label type based on match type
        if match_type in [MatchType.PARTIAL, MatchType.FUZZY]:
            # Suggest hiddenLabel for partial/fuzzy matches (database columns, abbreviations)
            label_type = "skos:hiddenLabel"
            justification = f"Column name '{col_name}' is a variation that could benefit from a hiddenLabel for better automatic matching"
        elif match_type == MatchType.EXACT_LOCAL_NAME:
            # Suggest altLabel for exact local name matches without proper labels
            label_type = "skos:altLabel"
            justification = f"Column name '{col_name}' matches property name but lacks proper SKOS labels"
        else:
            # No suggestion needed for high-quality matches
            return None
        
        # Get property local name for readability
        local_name = str(prop.uri).split("#")[-1].split("/")[-1]
        property_label = prop.label or prop.pref_label or local_name
        
        # Generate Turtle snippet
        prop_prefix = self._format_uri(prop.uri)
        turtle_snippet = f'{prop_prefix} {label_type} "{col_name}" .'
        
        return SKOSEnrichmentSuggestion(
            property_uri=str(prop.uri),
            property_label=property_label,
            suggested_label_type=label_type,
            suggested_label_value=col_name,
            turtle_snippet=turtle_snippet,
            justification=justification
        )
    
    def generate_with_alignment_report(
        self,
        target_class: Optional[str] = None,
        output_path: Optional[str] = None
    ) -> Tuple[Dict[str, Any], AlignmentReport]:
        """
        Generate mapping configuration with alignment report.
        
        Args:
            target_class: URI or label of the target ontology class
            output_path: Path where the config will be saved
            
        Returns:
            Tuple of (mapping_dict, alignment_report)
        """
        # Generate mapping first
        mapping = self.generate(target_class=target_class, output_path=output_path)
        
        # Find resolved target class
        resolved_class = None
        if target_class:
            resolved_class = self._resolve_class(target_class)
        else:
            resolved_class = self._auto_detect_class()
        
        # Build alignment report
        if resolved_class:
            self.alignment_report = self._build_alignment_report(resolved_class)
        
        return mapping, self.alignment_report
    
    def export_alignment_report(self, output_file: str):
        """Export alignment report to JSON file.
        
        Args:
            output_file: Path to save the JSON report
        """
        if not self.alignment_report:
            raise ValueError("No alignment report available. Call generate_with_alignment_report() first.")
        
        with open(output_file, 'w') as f:
            json.dump(self.alignment_report.to_dict(), f, indent=2)
    
    def print_alignment_summary(self):
        """Print a human-readable alignment summary to console."""
        if not self.alignment_report:
            raise ValueError("No alignment report available. Call generate_with_alignment_report() first.")
        
        print(self.alignment_report.summary_message())
