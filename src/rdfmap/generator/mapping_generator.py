"""Mapping configuration generator combining ontology and data source analysis."""

from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
import os
import yaml
import json
from difflib import SequenceMatcher
from pydantic import BaseModel, Field

from .ontology_analyzer import OntologyAnalyzer, OntologyClass, OntologyProperty
from .data_analyzer import DataSourceAnalyzer, DataFieldAnalysis
from .semantic_matcher import SemanticMatcher
from .matchers import create_default_pipeline, MatcherPipeline, MatchContext
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
    imports: Optional[List[str]] = Field(
        None, description="List of ontology files to import (file paths or URIs)"
    )
    default_class_prefix: str = Field("resource", description="Default prefix for resource IRIs")
    include_comments: bool = Field(True, description="Include comments in generated config")
    auto_detect_relationships: bool = Field(
        True, description="Attempt to detect relationships between entities"
    )
    min_confidence: float = Field(
        0.5, description="Minimum confidence score for automatic suggestions (0-1)"
    )


class MappingGenerator:
    """Generates mapping configuration from ontology and data source analysis (CSV, XLSX, JSON, XML)."""

    def __init__(
        self,
        ontology_file: str,
        data_file: str,
        config: GeneratorConfig,
        matcher_pipeline: Optional[MatcherPipeline] = None,
        use_semantic_matching: bool = True,
    ):
        """
        Initialize the mapping generator.
        
        Args:
            ontology_file: Path to ontology file
            data_file: Path to data file (CSV, XLSX, JSON, or XML)
            config: Generator configuration
            matcher_pipeline: Optional custom matcher pipeline (creates default if None)
            use_semantic_matching: Whether to use semantic embeddings (default: True)
        """
        self.config = config
        self.ontology_file = ontology_file
        self.data_file = data_file
        self.ontology = OntologyAnalyzer(ontology_file, imports=config.imports)
        self.data_source = DataSourceAnalyzer(data_file)
        # Initialize matcher pipeline
        if matcher_pipeline:
            self.matcher_pipeline = matcher_pipeline
        else:
            self.matcher_pipeline = create_default_pipeline(
                use_semantic=use_semantic_matching,
                semantic_threshold=config.min_confidence
            )
        self.semantic_matcher = SemanticMatcher() if use_semantic_matching else None

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
        
        # Add imports if specified
        if self.config.imports:
            self.mapping["imports"] = self.config.imports

        return self.mapping
    
    def generate_multisheet(
        self,
        output_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generate mapping configuration for Excel workbook with multiple sheets.

        Automatically detects relationships between sheets and generates
        appropriate mappings for each sheet.

        Args:
            output_path: Path where the config will be saved

        Returns:
            Dictionary representation of the mapping configuration
        """
        from .multisheet_analyzer import MultiSheetAnalyzer

        self.output_path = Path(output_path) if output_path else None

        # Check if data source has multiple sheets
        if not self.data_source.has_multiple_sheets:
            # Fall back to single-sheet generation
            return self.generate(output_path=output_path)

        # Analyze multi-sheet structure
        ms_analyzer = MultiSheetAnalyzer(str(self.data_source.file_path))
        relationships = ms_analyzer.detect_relationships()

        # Get primary sheet
        primary_sheet = ms_analyzer.get_primary_sheet()

        # Build mapping
        self.mapping = {
            "namespaces": self._generate_namespaces(),
            "defaults": self._generate_defaults(),
            "sheets": [],
            "options": self._generate_options(),
        }

        # Add imports if specified
        if self.config.imports:
            self.mapping["imports"] = self.config.imports

        # Generate mapping for each sheet
        for sheet_name in ms_analyzer.get_sheet_names():
            sheet_info = ms_analyzer.get_sheet_info(sheet_name)

            # Try to find a matching class for this sheet
            target_class = self._find_class_for_sheet(sheet_name)

            if not target_class:
                # Skip sheets we can't map
                continue

            # Generate sheet mapping
            sheet_mapping = self._generate_multisheet_mapping(
                sheet_name,
                target_class,
                sheet_info,
                relationships,
                is_primary=(sheet_name == primary_sheet)
            )

            self.mapping["sheets"].append(sheet_mapping)

        return self.mapping

    def _find_class_for_sheet(self, sheet_name: str) -> Optional[OntologyClass]:
        """Find an ontology class that matches a sheet name.

        Args:
            sheet_name: Name of the sheet

        Returns:
            Matching OntologyClass or None
        """
        # Try to suggest classes based on sheet name
        suggestions = self.ontology.suggest_class_for_name(sheet_name)

        if suggestions:
            return suggestions[0]

        return None

    def _generate_multisheet_mapping(
        self,
        sheet_name: str,
        target_class: OntologyClass,
        sheet_info: Any,  # SheetInfo from multisheet_analyzer
        relationships: List[Any],  # List of SheetRelationship
        is_primary: bool = False
    ) -> Dict[str, Any]:
        """Generate mapping for a single sheet in multi-sheet context.

        Args:
            sheet_name: Name of the sheet
            target_class: Target ontology class
            sheet_info: Sheet information from analyzer
            relationships: Detected relationships
            is_primary: Whether this is the primary sheet

        Returns:
            Sheet mapping dictionary
        """
        # Create a temporary DataSourceAnalyzer for this sheet
        # (For now, we'll generate based on the class)

        # Build basic sheet structure
        sheet_mapping = {
            "name": sheet_name,
            "source": str(self.data_source.file_path),
            "row_resource": {
                "class": self._format_uri(target_class.uri),
                "iri_template": self._generate_iri_template(target_class),
            },
            "columns": {},
            "objects": {}
        }

        # Add sheet-specific metadata
        if not is_primary:
            sheet_mapping["_metadata"] = {
                "sheet_name": sheet_name,
                "role": "referenced_entity"
            }

        # Find relationships where this sheet is the source
        outgoing_rels = [r for r in relationships if r.source_sheet == sheet_name]

        if outgoing_rels:
            # Add relationship hints
            sheet_mapping["_relationships"] = [
                {
                    "target_sheet": rel.target_sheet,
                    "foreign_key": rel.source_column,
                    "referenced_key": rel.target_column,
                    "type": rel.relationship_type
                }
                for rel in outgoing_rels
            ]

        # For now, generate basic column mappings
        # (Full implementation would load sheet data and match columns)
        # This is a placeholder that should be enhanced

        return sheet_mapping

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
        file_stem = Path(self.data_source.file_path).stem

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
        """Generate namespace declarations - only essential ones."""
        # Start with essential standard namespaces
        namespaces = {
            "xsd": "http://www.w3.org/2001/XMLSchema#",
            "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
        }

        # Add ontology-specific namespaces
        ontology_ns = self.ontology.get_namespaces()

        # Exclude these standard/common vocabularies
        excluded_prefixes = {'owl', 'rdf', 'xsd', 'rdfs', 'xml', 'skos', 'dcterms', 'dc',
                            'foaf', 'doap', 'geo', 'void', 'dcat', 'prov', 'qb', 'csvw'}
        excluded_domains = ['w3.org', 'schema.org', 'purl.org', 'brickschema', 'xmlns.com',
                           'usefulinc.com', 'opengis.net', 'rdfs.org']

        for prefix, uri in ontology_ns.items():
            # Only include non-standard namespaces (domain-specific ones)
            if prefix not in excluded_prefixes and \
               not any(domain in uri for domain in excluded_domains):
                namespaces[prefix] = uri

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
        sheet_name = Path(self.data_source.file_path).stem

        # Calculate relative path for source if output_path is provided
        source_path = Path(self.data_source.file_path)
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

    def _generate_iri_template(self, target_class: OntologyClass, for_object: bool = False,
                               object_class: Optional[OntologyClass] = None) -> str:
        """Generate IRI template for the target class.

        Args:
            target_class: The class to generate template for
            for_object: Whether this is for a linked object
            object_class: If for_object, the object's class

        Returns:
            IRI template string using {base_iri} placeholder
        """
        # Get suggested identifier columns
        id_cols = self.data_source.suggest_iri_template_columns()

        if not id_cols:
            # Fallback to first column
            id_cols = [self.data_source.get_column_names()[0]]

        # Use class name or default prefix
        if for_object and object_class:
            class_name = object_class.label or "object"
            # For objects, try to find ID column that matches the object class
            class_name_lower = class_name.lower()
            object_id_cols = [col for col in self.data_source.get_column_names()
                            if col.lower() == class_name_lower + 'id']
            if object_id_cols:
                id_cols = [object_id_cols[0]]
        else:
            class_name = target_class.label or self.config.default_class_prefix

        class_name = class_name.lower().replace(" ", "_")
        
        # Build template with {base_iri} placeholder
        id_part = "/".join([f"{{{col}}}" for col in id_cols])
        return f"{{base_iri}}{class_name}/{id_part}"

    def _generate_column_mappings(self, target_class: OntologyClass) -> Dict[str, Any]:
        """Generate column to property mappings."""
        mappings = {}
        used_properties = set()

        # Get datatype properties for this class
        properties = self.ontology.get_datatype_properties(target_class.uri)
        
        # First, identify which columns belong to linked objects
        columns_in_objects = set()
        fk_id_columns = set()  # Track FK ID columns separately
        if self.config.auto_detect_relationships:
            obj_properties = self.ontology.get_object_properties(target_class.uri)
            for prop in obj_properties:
                if not prop.range_type or prop.range_type not in self.ontology.classes:
                    continue
                range_class = self.ontology.classes[prop.range_type]
                class_name = range_class.label.lower() if range_class.label else ""

                # Find columns for this object
                potential_cols = self._find_columns_for_object(range_class)
                columns_in_objects.update(col_name for col_name, _ in potential_cols)

                # Also track FK ID columns (e.g., BorrowerID, PropertyID)
                for col_name in self.data_source.get_column_names():
                    col_lower = col_name.lower()
                    if col_lower.endswith('id') and col_lower == class_name + 'id':
                        fk_id_columns.add(col_name)

        # Match columns to properties (excluding those in linked objects and FK IDs)
        for col_name in self.data_source.get_column_names():
            # Skip columns that belong to linked objects or are FK IDs
            if col_name in columns_in_objects or col_name in fk_id_columns:
                continue

            col_analysis = self.data_source.get_analysis(col_name)

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
                # Track unmapped column (only if not in objects)
                self._unmapped_columns.append(col_name)
        
        return mappings

    def _match_column_to_property(
        self,
        col_name: str,
        col_analysis: DataFieldAnalysis,
        properties: List[OntologyProperty],
    ) -> Optional[Tuple[OntologyProperty, MatchType, str]]:
        """
        Match a column to an ontology property using the matcher pipeline.

        Returns:
            Tuple of (property, match_type, matched_via) or None if no match found
        """
        # Create match context
        context = MatchContext(
            column=col_analysis,
            all_columns=[self.data_source.get_analysis(c) for c in self.data_source.get_column_names()],
            available_properties=properties,
            domain_hints=None  # TODO: Add domain detection
        )

        # Use matcher pipeline
        result = self.matcher_pipeline.match(col_analysis, properties, context)

        if result:
            return (result.property, result.match_type, result.matched_via)

        return None
    
    def _build_ontology_context(self, target_class: OntologyClass) -> 'OntologyContext':
        """Build comprehensive ontology context for human mapping decisions.

        Args:
            target_class: The target ontology class

        Returns:
            OntologyContext with all relevant information for analysts
        """
        from ..models.alignment import OntologyContext, ClassContext

        # Build target class context
        target_properties = self.ontology.get_datatype_properties(target_class.uri)
        target_prop_contexts = [self._build_property_context(prop, str(target_class.uri)) for prop in target_properties]

        target_context = ClassContext(
            uri=str(target_class.uri),
            label=target_class.label,
            comment=target_class.comment,
            local_name=str(target_class.uri).split("#")[-1].split("/")[-1],
            properties=target_prop_contexts
        )

        # Build related classes context (classes that have relationships with target class)
        related_contexts = []
        obj_properties = self.ontology.get_object_properties(target_class.uri)

        for obj_prop in obj_properties:
            if obj_prop.range_type and obj_prop.range_type in self.ontology.classes:
                related_class = self.ontology.classes[obj_prop.range_type]
                related_properties = self.ontology.get_datatype_properties(obj_prop.range_type)
                related_prop_contexts = [self._build_property_context(prop, obj_prop.range_type) for prop in related_properties]

                related_context = ClassContext(
                    uri=str(related_class.uri),
                    label=related_class.label,
                    comment=related_class.comment,
                    local_name=str(related_class.uri).split("#")[-1].split("/")[-1],
                    properties=related_prop_contexts
                )
                related_contexts.append(related_context)

        # Get all properties in ontology (for comprehensive reference)
        all_properties = []
        for class_uri, ontology_class in self.ontology.classes.items():
            class_properties = self.ontology.get_properties_for_class(class_uri)
            for prop in class_properties:
                if not any(p.uri == prop.uri for p in all_properties):  # Avoid duplicates
                    all_properties.append(prop)

        all_prop_contexts = [self._build_property_context(prop) for prop in all_properties]

        # Get object properties for relationship mapping
        all_obj_properties = []
        for class_uri, ontology_class in self.ontology.classes.items():
            obj_props = self.ontology.get_object_properties(class_uri)
            for prop in obj_props:
                if not any(p.uri == prop.uri for p in all_obj_properties):  # Avoid duplicates
                    all_obj_properties.append(prop)

        obj_prop_contexts = [self._build_property_context(prop) for prop in all_obj_properties]

        return OntologyContext(
            target_class=target_context,
            related_classes=related_contexts,
            all_properties=all_prop_contexts,
            object_properties=obj_prop_contexts
        )

    def _build_property_context(self, prop: OntologyProperty, domain_class: str = None) -> 'PropertyContext':
        """Build context information for a property."""
        from ..models.alignment import PropertyContext

        return PropertyContext(
            uri=str(prop.uri),
            label=prop.label,
            pref_label=prop.pref_label,
            alt_labels=prop.alt_labels,
            hidden_labels=prop.hidden_labels,
            comment=prop.comment,
            domain_class=domain_class,
            range_type=prop.range_type,
            local_name=str(prop.uri).split("#")[-1].split("/")[-1]
        )

    def _find_obvious_skos_suggestions(
        self,
        col_name: str, 
        target_class: OntologyClass
    ) -> Optional['SKOSEnrichmentSuggestion']:
        """Find only obvious, high-confidence SKOS suggestions for clear cases.

        This method only suggests SKOS labels for very clear abbreviation patterns
        that are unambiguous and commonly used.

        Args:
            col_name: Column name to match
            target_class: Target ontology class
            
        Returns:
            SKOSEnrichmentSuggestion for obvious cases, None otherwise
        """
        from ..models.alignment import SKOSEnrichmentSuggestion

        properties = self.ontology.get_datatype_properties(target_class.uri)

        # Very conservative abbreviation mappings (only obvious ones)
        obvious_mappings = {
            'emp_num': ['employeeNumber', 'employee_number'],
            'emp_id': ['employeeNumber', 'employee_number', 'employeeId'],
            'hire_dt': ['hireDate', 'hire_date'],
            'start_dt': ['startDate', 'start_date'],
            'end_dt': ['endDate', 'end_date'],
            'mgr_id': ['managerId', 'manager_id'],
            'office_loc': ['officeLocation', 'office_location'],
            'annual_comp': ['annualCompensation', 'annual_compensation', 'salary'],
            'status_cd': ['statusCode', 'status_code', 'employmentStatus'],
            'dept_code': ['departmentCode', 'department_code'],
            'org_code': ['organizationCode', 'organization_code'],
            'job_ttl': ['jobTitle', 'job_title'],
            'pos_ttl': ['positionTitle', 'position_title']
        }

        col_lower = col_name.lower()
        if col_lower not in obvious_mappings:
            return None

        possible_matches = obvious_mappings[col_lower]

        # Look for exact matches with property local names or labels
        for prop in properties:
            local_name = str(prop.uri).split("#")[-1].split("/")[-1]

            # Check if property local name matches any of the possible matches
            if local_name.lower() in [m.lower().replace('_', '') for m in possible_matches]:
                return SKOSEnrichmentSuggestion(
                    property_uri=str(prop.uri),
                    property_label=prop.label or local_name,
                    suggested_label_type="skos:hiddenLabel",
                    suggested_label_value=col_name,
                    turtle_snippet=f'{self._format_uri(prop.uri)} skos:hiddenLabel "{col_name}" .',
                    justification=f"Column '{col_name}' is a common abbreviation for property '{prop.label or local_name}'. This is a standard database column naming pattern."
                )

            # Check labels too
            if prop.label:
                label_normalized = prop.label.lower().replace(' ', '').replace('_', '')
                if label_normalized in [m.lower().replace('_', '') for m in possible_matches]:
                    return SKOSEnrichmentSuggestion(
                        property_uri=str(prop.uri),
                        property_label=prop.label or local_name,
                        suggested_label_type="skos:hiddenLabel",
                        suggested_label_value=col_name,
                        turtle_snippet=f'{self._format_uri(prop.uri)} skos:hiddenLabel "{col_name}" .',
                        justification=f"Column '{col_name}' is a common abbreviation for property '{prop.label}'. This is a standard database column naming pattern."
                    )

        return None

    def _build_ontology_context(self, target_class: OntologyClass) -> 'OntologyContext':
        """Build comprehensive ontology context for human mapping decisions.

        Args:
            target_class: The target ontology class

        Returns:
            OntologyContext with all relevant information for analysts
        """
        from ..models.alignment import OntologyContext, ClassContext

        # Build target class context
        target_properties = self.ontology.get_datatype_properties(target_class.uri)
        target_prop_contexts = [self._build_property_context(prop, str(target_class.uri)) for prop in target_properties]

        target_context = ClassContext(
            uri=str(target_class.uri),
            label=target_class.label,
            comment=target_class.comment,
            local_name=str(target_class.uri).split("#")[-1].split("/")[-1],
            properties=target_prop_contexts
        )

        # Build related classes context (classes that have relationships with target class)
        related_contexts = []
        obj_properties = self.ontology.get_object_properties(target_class.uri)

        for obj_prop in obj_properties:
            if obj_prop.range_type and obj_prop.range_type in self.ontology.classes:
                related_class = self.ontology.classes[obj_prop.range_type]
                related_properties = self.ontology.get_datatype_properties(obj_prop.range_type)
                related_prop_contexts = [self._build_property_context(prop, obj_prop.range_type) for prop in related_properties]

                related_context = ClassContext(
                    uri=str(related_class.uri),
                    label=related_class.label,
                    comment=related_class.comment,
                    local_name=str(related_class.uri).split("#")[-1].split("/")[-1],
                    properties=related_prop_contexts
                )
                related_contexts.append(related_context)

        # Get all properties in ontology (for comprehensive reference)
        all_properties = []
        for class_uri, ontology_class in self.ontology.classes.items():
            class_properties = self.ontology.get_properties_for_class(class_uri)
            for prop in class_properties:
                if not any(p.uri == prop.uri for p in all_properties):  # Avoid duplicates
                    all_properties.append(prop)

        all_prop_contexts = [self._build_property_context(prop) for prop in all_properties]

        # Get object properties for relationship mapping
        all_obj_properties = []
        for class_uri, ontology_class in self.ontology.classes.items():
            obj_props = self.ontology.get_object_properties(class_uri)
            for prop in obj_props:
                if not any(p.uri == prop.uri for p in all_obj_properties):  # Avoid duplicates
                    all_obj_properties.append(prop)

        obj_prop_contexts = [self._build_property_context(prop) for prop in all_obj_properties]

        return OntologyContext(
            target_class=target_context,
            related_classes=related_contexts,
            all_properties=all_prop_contexts,
            object_properties=obj_prop_contexts
        )

    def _build_property_context(self, prop: OntologyProperty, domain_class: str = None) -> 'PropertyContext':
        """Build context information for a property."""
        from ..models.alignment import PropertyContext

        return PropertyContext(
            uri=str(prop.uri),
            label=prop.label,
            pref_label=prop.pref_label,
            alt_labels=prop.alt_labels,
            hidden_labels=prop.hidden_labels,
            comment=prop.comment,
            domain_class=domain_class,
            range_type=prop.range_type,
            local_name=str(prop.uri).split("#")[-1].split("/")[-1]
        )

    def _is_likely_abbreviation(self, col_pattern: str, prop_pattern: str) -> bool:
        """Check if column pattern is likely an abbreviation of property pattern."""
        col_lower = col_pattern.lower()
        prop_lower = prop_pattern.lower()

        # Common abbreviation patterns
        abbreviation_pairs = [
            ('fname', 'firstname'), ('fname', 'first_name'), ('fname', 'given_name'),
            ('lname', 'lastname'), ('lname', 'last_name'), ('lname', 'surname'), ('lname', 'family_name'),
            ('mname', 'middlename'), ('mname', 'middle_name'),
            ('email_addr', 'emailaddress'), ('email_addr', 'email_address'),
            ('phone_num', 'phonenumber'), ('phone_num', 'phone_number'),
            ('emp_num', 'employeenumber'), ('emp_num', 'employee_number'),
            ('mgr_id', 'managerid'), ('mgr_id', 'manager_id'), ('mgr_id', 'manager'),
            ('dept_code', 'departmentcode'), ('dept_code', 'department_code'),
            ('org_name', 'organizationname'), ('org_name', 'organization_name'),
            ('hire_dt', 'hiredate'), ('hire_dt', 'hire_date'),
            ('status_cd', 'statuscode'), ('status_cd', 'status_code'),
            ('office_loc', 'officelocation'), ('office_loc', 'office_location'),
            ('annual_comp', 'annualcompensation'), ('annual_comp', 'annual_compensation'),
            ('cost_ctr', 'costcenter'), ('cost_ctr', 'cost_center')
        ]

        # Normalize both for comparison
        col_norm = col_lower.replace('_', '').replace('-', '').replace(' ', '')
        prop_norm = prop_lower.replace('_', '').replace('-', '').replace(' ', '')

        # Check exact abbreviation matches
        for abbr, full in abbreviation_pairs:
            abbr_norm = abbr.replace('_', '')
            full_norm = full.replace('_', '')

            if (col_norm == abbr_norm and prop_norm == full_norm) or \
               (col_norm == full_norm and prop_norm == abbr_norm):
                return True

        # Check if column is significantly shorter and contains key letters from property
        if len(col_norm) <= len(prop_norm) * 0.6:  # Column is much shorter
            # Extract first letters and consonants from property
            prop_initials = ''.join([c for i, c in enumerate(prop_norm)
                                   if i == 0 or prop_norm[i-1] in 'aeiou'])

            # Check if column matches these initials closely
            if len(col_norm) >= 3 and len(prop_initials) >= 3:
                initial_similarity = SequenceMatcher(None, col_norm, prop_initials).ratio()
                if initial_similarity > 0.7:
                    return True

        return False

    def _is_semantically_reasonable_match(self, col_name: str, prop: OntologyProperty, similarity: float) -> bool:
        """Check if a column-to-property match is semantically reasonable."""
        col_lower = col_name.lower()
        prop_label = (prop.label or prop.pref_label or str(prop.uri).split('#')[-1]).lower()
        prop_local = str(prop.uri).split('#')[-1].split('/')[-1].lower()

        # For low similarity matches, apply stricter semantic checks
        if similarity < 0.6:
            # Prevent completely unrelated matches
            unrelated_pairs = [
                (['cost', 'ctr', 'center'], ['manager', 'person', 'employee']),
                (['phone', 'telephone'], ['number', 'id', 'identifier', 'employee']),
                (['email', 'mail'], ['salary', 'compensation', 'amount']),
                (['address', 'addr'], ['salary', 'compensation', 'number']),
                (['department', 'dept'], ['person', 'name', 'manager']),
            ]

            for col_keywords, prop_keywords in unrelated_pairs:
                if any(kw in col_lower for kw in col_keywords) and any(kw in prop_label or kw in prop_local for kw in prop_keywords):
                    return False

        # For medium similarity, still apply some checks
        elif similarity < 0.8:
            # Allow more flexibility but still prevent obvious mismatches
            obvious_mismatches = [
                (['cost', 'ctr'], ['manager', 'person']),
                (['phone'], ['employee', 'number', 'identifier']),
            ]

            for col_keywords, prop_keywords in obvious_mismatches:
                if any(kw in col_lower for kw in col_keywords) and any(kw in prop_label or kw in prop_local for kw in prop_keywords):
                    return False

        # High similarity matches are generally acceptable
        return True

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
                
                # Build properties list with full metadata
                properties = []
                for col_name, matched_prop in potential_cols:
                    col_analysis = self.data_source.get_analysis(col_name)
                    prop_mapping = {
                        "column": col_name,
                        "as": self._format_uri(matched_prop.uri),  # Use matched_prop not prop!
                    }

                    # Add datatype if available
                    if col_analysis.suggested_datatype:
                        prop_mapping["datatype"] = col_analysis.suggested_datatype

                    # Add required flag
                    if col_analysis.is_required:
                        prop_mapping["required"] = True

                    properties.append(prop_mapping)

                # Post-process properties list to remove duplicates of same target property
                unique_props = []
                seen_prop_targets = set()
                for p in properties:
                    tgt = p.get('as')
                    if tgt in seen_prop_targets:
                        continue
                    seen_prop_targets.add(tgt)
                    unique_props.append(p)
                object_mappings[obj_name] = {
                    'predicate': self._format_uri(prop.uri),
                    'class': self._format_uri(range_class.uri),
                    'iri_template': self._generate_iri_template(range_class, for_object=True, object_class=range_class),
                    'properties': unique_props,
                }
        
        return object_mappings
    
    def _find_columns_for_object(
        self, range_class: OntologyClass
    ) -> List[tuple[str, OntologyProperty]]:
        """Find columns that could belong to a linked object class.

        Only includes columns where the column NAME contains the class name.
        E.g., BorrowerID, BorrowerName for Borrower class
              PropertyID, PropertyAddress for Property class

        Skips pure ID columns (e.g., BorrowerID, PropertyID) as these are foreign keys.
        """
        potential = []
        range_props = self.ontology.get_datatype_properties(range_class.uri)
        class_name = range_class.label.lower() if range_class.label else ""

        for col_name in self.data_source.get_column_names():
            col_analysis = self.data_source.get_analysis(col_name)
            col_lower = col_name.lower()

            # Check if column name contains the class name
            # E.g., "borrowerid" contains "borrower", "propertyaddress" contains "property"
            if class_name not in col_lower:
                continue

            # Skip pure ID columns (they're foreign keys, not properties to map)
            # E.g., BorrowerID, PropertyID
            if col_lower.endswith('id') and col_lower == class_name + 'id':
                continue

            # Try to match to object's properties
            match_result = self._match_column_to_property(col_name, col_analysis, range_props)
            
            if match_result:
                matched_prop, _, _ = match_result
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
        """Save the mapping to a YAML file with clean formatting."""
        if not self.mapping:
            raise ValueError("No mapping generated. Call generate() first.")
        
        # Use custom formatter for clean output
        from .yaml_formatter import save_formatted_mapping
        save_formatted_mapping(self.mapping, output_file, wizard_config=None)

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
        # Build comprehensive ontology context
        ontology_context = self._build_ontology_context(target_class)

        # Collect unmapped column details
        unmapped_details = []
        skos_suggestions = []
        
        for col_name in self._unmapped_columns:
            col_analysis = self.data_source.get_analysis(col_name)
            unmapped_details.append(
                UnmappedColumn(
                    column_name=col_name,
                    sample_values=col_analysis.sample_values[:5],
                    inferred_datatype=col_analysis.suggested_datatype,
                    reason="No matching property found in ontology",
                    ontology_context=ontology_context  # Provide full context for human review
                )
            )
            
            # Only suggest SKOS labels for obvious, unambiguous cases
            obvious_suggestion = self._find_obvious_skos_suggestions(col_name, target_class)
            if obvious_suggestion:
                skos_suggestions.append(obvious_suggestion)

        # Collect weak matches (and add their suggestions to existing list)
        weak_matches = []
        
        confidence_scores = []
        for col_name, (prop, match_type, confidence) in self._mapped_columns.items():
            confidence_scores.append(confidence)
            confidence_level = get_confidence_level(confidence)
            
            # Track weak matches (confidence < 0.8)
            if confidence < 0.8:
                col_analysis = self.data_source.get_analysis(col_name)

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
        total_columns = len(self.data_source.get_column_names())
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
            spreadsheet_file=self.data_file,
            target_class=target_class.label or str(target_class.uri),
            statistics=statistics,
            unmapped_columns=unmapped_details,
            weak_matches=weak_matches,
            skos_enrichment_suggestions=skos_suggestions,
            ontology_context=ontology_context
        )

    def _generate_skos_suggestion(
        self,
        col_name: str,
        prop: OntologyProperty,
        match_type: MatchType
    ) -> Optional[SKOSEnrichmentSuggestion]:
        """Generate SKOS enrichment suggestion for weak matches."""
        import re

        # Get property local name for readability
        local_name = str(prop.uri).split("#")[-1].split("/")[-1]
        property_label = prop.label or prop.pref_label or local_name

        # Determine appropriate label type and justification based on match type and patterns
        if match_type in [MatchType.PARTIAL, MatchType.FUZZY]:
            # Analyze the column name to provide better suggestions
            col_lower = col_name.lower()

            # Check if it's clearly an abbreviation
            is_abbreviation = (
                len(col_name) <= 8 and
                any(abbr in col_lower for abbr in ['num', 'id', 'dt', 'cd', 'ttl', 'loc', 'addr', 'emp', 'mgr', 'dept', 'org'])
            )

            # Check if it uses underscores/separators (database style)
            is_database_style = '_' in col_name or '-' in col_name

            if is_abbreviation:
                label_type = "skos:hiddenLabel"
                justification = f"Column name '{col_name}' appears to be an abbreviation for property '{property_label}'. Adding as hiddenLabel will enable matching with abbreviated column names"
            elif is_database_style:
                label_type = "skos:hiddenLabel"
                justification = f"Column name '{col_name}' uses database-style naming that relates to property '{property_label}'. Adding as hiddenLabel will improve matching with legacy database columns"
            else:
                label_type = "skos:altLabel"
                justification = f"Column name '{col_name}' is an alternative form of property '{property_label}'. Adding as altLabel will enable matching with this variation"

        elif match_type == MatchType.EXACT_LOCAL_NAME:
            # For exact local name matches without proper SKOS labels, suggest improving the ontology
            if not prop.pref_label and not prop.alt_labels:
                label_type = "skos:prefLabel"
                # Convert camelCase to human-readable format
                readable_label = re.sub(r'([a-z])([A-Z])', r'\1 \2', local_name).title()
                justification = f"Property '{local_name}' matches column '{col_name}' but lacks SKOS labels. Adding prefLabel '{readable_label}' will improve semantic clarity"
                col_name = readable_label  # Suggest human-readable label instead of column name
            else:
                label_type = "skos:altLabel"
                justification = f"Column name '{col_name}' exactly matches the property local name. Adding as altLabel provides an explicit alternative form"

        else:
            # No suggestion needed for high-quality matches
            return None

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

    def export_alignment_html(self, output_file: str):
        """Export alignment report to HTML file.

        Args:
            output_file: Path to save the HTML report
        """
        if not self.alignment_report:
            raise ValueError("No alignment report available. Call generate_with_alignment_report() first.")

        self.alignment_report.export_html(output_file)

    def print_alignment_summary(self, show_details: bool = True):
        """Print a human-readable alignment summary to console.

        Args:
            show_details: Whether to show detailed match tables (default: True)
        """
        if not self.alignment_report:
            raise ValueError("No alignment report available. Call generate_with_alignment_report() first.")

        # Use Rich terminal output if available, otherwise fall back to simple text
        self.alignment_report.print_rich_terminal(show_details=show_details)

