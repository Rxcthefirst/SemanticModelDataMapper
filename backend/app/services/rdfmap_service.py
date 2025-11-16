"""RDFMap service layer - wraps core library functionality."""

import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
import yaml

# Import from correct module paths
from rdfmap.generator.mapping_generator import MappingGenerator, GeneratorConfig
from rdfmap.generator.ontology_analyzer import OntologyAnalyzer
from rdfmap.generator.data_analyzer import DataSourceAnalyzer
from rdfmap.emitter.graph_builder import RDFGraphBuilder, serialize_graph
from rdfmap.models.errors import ProcessingReport
from rdfmap.parsers.data_source import create_parser
from rdfmap.config.loader import load_mapping_config

logger = logging.getLogger(__name__)


class RDFMapService:
    """Service class for RDFMap operations."""

    def __init__(self, uploads_dir: str = "/app/uploads", data_dir: str = "/app/data"):
        self.uploads_dir = Path(uploads_dir)
        self.data_dir = Path(data_dir)

    def analyze_data_file(self, data_file_path: str) -> Dict[str, Any]:
        """
        Analyze a data file and return column information.

        Args:
            data_file_path: Path to data file

        Returns:
            Dictionary with column names, types, sample values
        """
        try:
            # Use parser to get basic info - convert string to Path
            from pathlib import Path as PathlibPath
            file_path = PathlibPath(data_file_path) if isinstance(data_file_path, str) else data_file_path
            parser = create_parser(file_path)
            dataframes = list(parser.parse())

            if not dataframes:
                return {"total_columns": 0, "columns": [], "row_count": 0}

            df = dataframes[0]

            # Get column information from dataframe
            columns = []
            for col_name in df.columns:
                col_data = df[col_name]

                # Get sample values (first 5 non-null)
                sample_values = col_data.drop_nulls().head(5).to_list()

                columns.append({
                    "name": col_name,
                    "inferred_type": str(col_data.dtype),
                    "sample_values": [str(v) for v in sample_values],
                    "is_identifier": False,  # TODO: detect identifiers
                    "is_foreign_key": False,  # TODO: detect FKs
                })

            return {
                "total_columns": len(columns),
                "columns": columns,
                "row_count": len(df),
            }
        except Exception as e:
            logger.error(f"Error analyzing data file: {e}")
            raise

    def analyze_ontology(self, ontology_file_path: str) -> Dict[str, Any]:
        """
        Analyze an ontology file and return structure information.

        Args:
            ontology_file_path: Path to ontology file

        Returns:
            Dictionary with classes, properties, and their metadata
        """
        try:
            analyzer = OntologyAnalyzer(ontology_file_path)

            # Get classes
            classes = []
            for class_uri, ont_class in analyzer.classes.items():
                classes.append({
                    "uri": class_uri,
                    "label": ont_class.label,
                    "comment": ont_class.comment,
                    "skos_labels": {
                        "pref_label": ont_class.skos_pref_label,
                        "alt_labels": ont_class.skos_alt_labels,
                        "hidden_labels": ont_class.skos_hidden_labels,
                    }
                })

            # Get properties
            properties = []
            for prop_uri, ont_prop in analyzer.properties.items():
                properties.append({
                    "uri": prop_uri,
                    "label": ont_prop.label,
                    "comment": ont_prop.comment,
                    "property_type": ont_prop.property_type,
                    "domain": ont_prop.domain,
                    "range": ont_prop.range,
                    "is_functional": getattr(ont_prop, 'is_functional', False),
                    "is_inverse_functional": getattr(ont_prop, 'is_inverse_functional', False),
                    "skos_labels": {
                        "pref_label": ont_prop.skos_pref_label,
                        "alt_labels": ont_prop.skos_alt_labels,
                        "hidden_labels": ont_prop.skos_hidden_labels,
                    }
                })

            return {
                "total_classes": len(classes),
                "total_properties": len(properties),
                "classes": classes,
                "properties": properties,
            }
        except Exception as e:
            logger.error(f"Error analyzing ontology: {e}")
            raise

    def _refine_mortgage_mapping(self, mapping_config: dict) -> dict:
        """Heuristic refinement for mortgage loan dataset to produce clean mapping.
        Applies only if typical mortgage columns are present and existing mapping has duplicated properties.
        """
        return mapping_config

    def summarize_mapping(self, mapping_config: dict) -> dict:
        """Produce summary (counts, per-sheet mapping stats)."""
        if not isinstance(mapping_config, dict):
            return {}
        summary_sheets = []
        total_columns = 0
        mapped_columns = 0
        for sheet in mapping_config.get('sheets', []):
            cols = sheet.get('columns', {}) or {}
            # FIX: correct variable names in comprehension
            mapped = [name for name, val in cols.items() if isinstance(val, dict) and val.get('as')]
            summary_sheets.append({
                'sheet': sheet.get('name'),
                'total_columns': len(cols),
                'mapped_columns': len(mapped),
                'mapped_column_names': mapped,
            })
            total_columns += len(cols)
            mapped_columns += len(mapped)
        rate = (mapped_columns/total_columns*100.0) if total_columns else 0.0
        return {
            'statistics': {
                'total_columns': total_columns,
                'mapped_columns': mapped_columns,
                'mapping_rate': rate,
            },
            'sheets': summary_sheets
        }

    def generate_mappings(
        self,
        project_id: str,
        ontology_file_path: str,
        data_file_path: str,
        target_class: Optional[str] = None,
        base_iri: str = "http://example.org/",
        use_semantic: bool = True,
        min_confidence: float = 0.5,
    ) -> Dict[str, Any]:
        """
        Generate automatic mappings between data and ontology.

        Args:
            project_id: Project identifier
            ontology_file_path: Path to ontology file
            data_file_path: Path to data file
            target_class: Optional target class URI
            base_iri: Base IRI for generated resources
            use_semantic: Whether to use semantic matching
            min_confidence: Minimum confidence threshold

        Returns:
            Dictionary with generated mappings and alignment report
        """
        try:
            logger.info(f"Generating mappings for project {project_id}")
            config = GeneratorConfig(base_iri=base_iri, min_confidence=min_confidence)
            generator = MappingGenerator(
                ontology_file=ontology_file_path,
                data_file=data_file_path,
                config=config,
                use_semantic_matching=use_semantic,
            )
            mapping_config, alignment_report = generator.generate_with_alignment_report(target_class=target_class)
            project_dir = self.data_dir / project_id
            project_dir.mkdir(parents=True, exist_ok=True)
            mapping_file = project_dir / "mapping_config.yaml"
            if isinstance(mapping_config, dict):
                mapping_config.setdefault('defaults', {}).setdefault('base_iri', base_iri)
            generator.mapping = mapping_config
            generator.save_yaml(str(mapping_file))
            summary = self.summarize_mapping(mapping_config)
            return {
                "mapping_config": mapping_config,
                "mapping_file": str(mapping_file),
                "alignment_report": alignment_report.to_dict() if alignment_report else {},
                "mapping_summary": summary,
                "formatted_yaml": open(mapping_file).read(),
            }

        except Exception as e:
            logger.error(f"Error generating mappings: {e}", exc_info=True)
            raise

    def convert_to_rdf(
        self,
        project_id: str,
        mapping_file_path: Optional[str] = None,
        output_format: str = "turtle",
        validate: bool = True,
    ) -> Dict[str, Any]:
        """
        Convert data to RDF using mapping configuration.

        Args:
            project_id: Project identifier
            mapping_file_path: Path to mapping config (uses saved if None)
            output_format: RDF format (turtle, json-ld, xml, nt)
            validate: Whether to validate output

        Returns:
            Dictionary with output file path and validation results
        """
        try:
            logger.info(f"Converting project {project_id} to RDF")

            # Load mapping config (validated pydantic model)
            if not mapping_file_path:
                project_dir = self.data_dir / project_id
                mapping_file_path = str(project_dir / "mapping_config.yaml")

            config = load_mapping_config(mapping_file_path)

            # Initialize report and builder
            report = ProcessingReport()
            builder = RDFGraphBuilder(config, report)

            # For each sheet, parse its source into DataFrames and add to builder
            for sheet in config.sheets:
                source_path = Path(sheet.source)
                parser = create_parser(source_path)
                dataframes = list(parser.parse())
                for df in dataframes:
                    builder.add_dataframe(df, sheet)

            # Determine output format extension
            format_extensions = {
                "turtle": "ttl",
                "json-ld": "jsonld",
                "xml": "rdf",
                "nt": "nt",
                "n3": "n3",
            }
            ext = format_extensions.get(output_format, "ttl")

            # Save RDF output
            project_dir = self.data_dir / project_id
            output_file = project_dir / f"output.{ext}"

            graph = builder.get_graph()
            if graph is None:
                raise ValueError("Graph not available (streaming mode not enabled in this path)")

            serialize_graph(graph, output_format, output_file)
            logger.info(f"RDF output saved to {output_file} with {builder.get_triple_count()} triples")

            # Validation (optional)
            validation_results = None
            if validate:
                try:
                    from rdfmap.validator.shacl import validate_rdf
                    # Determine ontology path if present in config imports
                    ontology_path = None
                    if config.imports and len(config.imports) > 0:
                        ontology_path = config.imports[0]

                    if ontology_path:
                        validation_results = validate_rdf(
                            str(output_file),
                            ontology_path,
                        )
                    else:
                        validation_results = {"status": "skipped", "reason": "No ontology specified in config imports"}
                except Exception as ve:
                    logger.warning(f"Validation failed: {ve}")
                    validation_results = {"status": "error", "error": str(ve)}

            return {
                "output_file": str(output_file),
                "format": output_format,
                "triple_count": builder.get_triple_count(),
                "validation": validation_results,
                "errors": [str(e) for e in report.errors] if report.errors else [],
                "warnings": [str(w) for w in report.warnings] if report.warnings else [],
            }

        except Exception as e:
            logger.error(f"Error converting to RDF: {e}", exc_info=True)
            raise
