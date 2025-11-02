"""Mapping configuration generator combining ontology and spreadsheet analysis."""

from typing import Dict, List, Optional, Any
from pathlib import Path
import os
import yaml
import json
from pydantic import BaseModel, Field

from .ontology_analyzer import OntologyAnalyzer, OntologyClass, OntologyProperty
from .spreadsheet_analyzer import SpreadsheetAnalyzer, ColumnAnalysis


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
        self.ontology = OntologyAnalyzer(ontology_file)
        self.spreadsheet = SpreadsheetAnalyzer(spreadsheet_file)
        
        self.mapping: Dict[str, Any] = {}
    
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
            matched_prop = self._match_column_to_property(col_name, col_analysis, properties)
            
            if matched_prop:
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
        
        return mappings
    
    def _match_column_to_property(
        self,
        col_name: str,
        col_analysis: ColumnAnalysis,
        properties: List[OntologyProperty],
    ) -> Optional[OntologyProperty]:
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
        """
        col_lower = col_name.lower().replace("_", "").replace(" ", "")
        
        # Priority 1: Exact match with SKOS prefLabel
        for prop in properties:
            if prop.pref_label:
                pref_label_clean = prop.pref_label.lower().replace("_", "").replace(" ", "")
                if col_lower == pref_label_clean:
                    return prop
        
        # Priority 2: Exact match with rdfs:label
        for prop in properties:
            if prop.label:
                prop_label_clean = prop.label.lower().replace("_", "").replace(" ", "")
                if col_lower == prop_label_clean:
                    return prop
        
        # Priority 3: Exact match with SKOS altLabel
        for prop in properties:
            for alt_label in prop.alt_labels:
                alt_label_clean = alt_label.lower().replace("_", "").replace(" ", "")
                if col_lower == alt_label_clean:
                    return prop
        
        # Priority 4: Exact match with SKOS hiddenLabel
        for prop in properties:
            for hidden_label in prop.hidden_labels:
                hidden_label_clean = hidden_label.lower().replace("_", "").replace(" ", "")
                if col_lower == hidden_label_clean:
                    return prop
        
        # Priority 5: Exact match with local name
        for prop in properties:
            local_name = str(prop.uri).split("#")[-1].split("/")[-1]
            local_clean = local_name.lower().replace("_", "")
            if col_lower == local_clean:
                return prop
        
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
                    return prop
        
        # Priority 7: Fuzzy match with local name
        for prop in properties:
            local_name = str(prop.uri).split("#")[-1].split("/")[-1]
            local_clean = local_name.lower().replace("_", "")
            if col_lower in local_clean or local_clean in col_lower:
                return prop
        
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
            matched_prop = self._match_column_to_property(col_name, col_analysis, range_props)
            
            if matched_prop:
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
