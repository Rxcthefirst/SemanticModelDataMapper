"""Main CLI application."""

from pathlib import Path
from typing import List, Optional

import typer
from rich.console import Console
from rich.table import Table

from ..config.loader import load_mapping_config
from ..emitter.graph_builder import RDFGraphBuilder, serialize_graph
from ..models.errors import ProcessingReport
from ..parsers.data_source import create_parser
from ..validator.shacl import validate_rdf, write_validation_report, validate_against_ontology
from ..validator.config import validate_namespace_prefixes, validate_required_fields
from ..generator.mapping_generator import MappingGenerator, GeneratorConfig
from ..generator.spreadsheet_analyzer import SpreadsheetAnalyzer
from ..generator.ontology_analyzer import OntologyAnalyzer
from ..generator.ontology_enricher import OntologyEnricher
from ..models.enrichment import (
    EnrichmentAction, InteractivePromptResponse, SKOSAddition, EnrichmentResult
)
from ..models.alignment import AlignmentReport
from ..analyzer.alignment_stats import AlignmentStatsAnalyzer
from ..validator.skos_coverage import SKOSCoverageValidator
import json

app = typer.Typer(
    name="rdfmap",
    help="Convert spreadsheet data to RDF triples aligned with ontologies",
    no_args_is_help=True,
)
console = Console()


@app.command()
def convert(
    mapping: Path = typer.Option(
        ...,
        "--mapping",
        "-m",
        help="Path to mapping configuration file (YAML/JSON)",
        exists=True,
        dir_okay=False,
    ),
    ontology: Optional[Path] = typer.Option(
        None,
        "--ontology",
        help="Path to ontology file (supports TTL, RDF/XML, JSON-LD, N-Triples, etc.)",
        exists=True,
        dir_okay=False,
    ),
    format: Optional[str] = typer.Option(
        None,
        "--format",
        "-f",
        help="Output format: ttl, xml, jsonld, nt (default: ttl)",
    ),
    output: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        help="Output file path",
        dir_okay=False,
    ),
    validate_flag: bool = typer.Option(
        False,
        "--validate",
        help="Run SHACL validation after conversion",
    ),
    report: Optional[Path] = typer.Option(
        None,
        "--report",
        help="Path to write validation report (JSON)",
        dir_okay=False,
    ),
    limit: Optional[int] = typer.Option(
        None,
        "--limit",
        help="Process only first N rows (for testing)",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Parse and validate without writing output",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable detailed logging",
    ),
    log_file: Optional[Path] = typer.Option(
        None,
        "--log",
        help="Write log to file",
        dir_okay=False,
    ),
) -> None:
    """Convert spreadsheet data to RDF triples."""
    try:
        # Load mapping configuration
        console.print(f"[blue]Loading mapping configuration from {mapping}...[/blue]")
        config = load_mapping_config(mapping)
        
        # Validate configuration
        console.print("[blue]Validating configuration...[/blue]")
        
        # Check namespace prefixes
        prefix_errors = validate_namespace_prefixes(config)
        if prefix_errors:
            console.print("[red]✗ Configuration validation failed: undefined namespace prefixes[/red]")
            for context, prefix in prefix_errors:
                console.print(f"  • In {context}: prefix '{prefix}' is not declared in namespaces")
            raise typer.Exit(code=1)
        
        # Check required fields in IRI templates
        field_warnings = validate_required_fields(config)
        if field_warnings:
            console.print("[yellow]⚠ Configuration warnings:[/yellow]")
            for context, warning in field_warnings:
                console.print(f"  • In {context}: {warning}")
        
        if verbose:
            console.print(f"[green]Configuration loaded and validated successfully[/green]")
            console.print(f"  Sheets: {len(config.sheets)}")
            console.print(f"  Namespaces: {len(config.namespaces)}")
        
        # Initialize processing report
        processing_report = ProcessingReport()
        
        # Build RDF graph
        builder = RDFGraphBuilder(config, processing_report)
        
        # Process each sheet
        for sheet in config.sheets:
            console.print(f"[blue]Processing sheet: {sheet.name}[/blue]")
            
            # Create parser
            parser = create_parser(
                Path(sheet.source),
                delimiter=config.options.delimiter,
                has_header=config.options.header,
            )
            
            if verbose:
                columns = parser.get_column_names()
                console.print(f"  Columns: {', '.join(columns)}")
            
            # Process data in chunks
            row_offset = 0
            for chunk in parser.parse(chunk_size=config.options.chunk_size):
                # Apply limit if specified
                if limit and row_offset >= limit:
                    break
                
                if limit:
                    remaining = limit - row_offset
                    chunk = chunk.head(remaining)
                
                # Add to graph
                builder.add_dataframe(chunk, sheet, offset=row_offset)
                
                row_offset += len(chunk)
                
                if verbose:
                    console.print(f"  Processed {row_offset} rows...")
        
        # Finalize report
        processing_report.finalize()
        processing_report.successful_rows = (
            processing_report.total_rows - processing_report.failed_rows
        )
        
        # Display processing summary
        _display_processing_summary(processing_report, verbose)
        
        # Get graph
        graph = builder.get_graph()
        
        console.print(f"[green]Generated {len(graph)} RDF triples[/green]")
        
        # Validate if requested
        validation_report = None
        if validate_flag and config.validation and config.validation.shacl:
            console.print("[blue]Running SHACL validation...[/blue]")
            
            shapes_file = Path(config.validation.shacl.shapes_file)
            if not shapes_file.exists():
                console.print(f"[yellow]Warning: Shapes file not found: {shapes_file}[/yellow]")
            else:
                validation_report = validate_rdf(
                    graph,
                    shapes_file=shapes_file,
                    inference=config.validation.shacl.inference,
                )
                
                _display_validation_results(validation_report, verbose)
                
                # Write validation report if requested
                if report and validation_report:
                    write_validation_report(validation_report, report)
                    console.print(f"[green]Validation report written to {report}[/green]")
        
        # Validate against ontology if provided
        if ontology:
            console.print("[blue]Running ontology validation...[/blue]")
            
            ontology_report = validate_against_ontology(
                graph,
                ontology_file=ontology,
            )
            
            _display_validation_results(ontology_report, verbose)
            
            if not ontology_report.conforms:
                console.print("[red]✗ Ontology validation failed[/red]")
                if validate_flag:  # Only exit with error if --validate was used
                    raise typer.Exit(code=1)
            else:
                console.print("[green]✓ Ontology validation passed[/green]")
        
        # Display SHACL validation results if validation was performed
        if validate_flag and validation_report:
            _display_validation_results(validation_report, verbose)
            
            # Write validation report if requested
            if report:
                write_validation_report(validation_report, report)
                console.print(f"[green]Validation report written to {report}[/green]")
        
        # Write output
        if not dry_run and output:
            # Use provided format or default to ttl
            output_format = format or "ttl"
            
            console.print(f"[blue]Writing {output_format.upper()} to {output}...[/blue]")
            serialize_graph(graph, output_format, output)
            console.print(f"[green]Output written successfully[/green]")
        elif dry_run:
            console.print("[yellow]Dry run mode: no output written[/yellow]")
        elif not output:
            console.print("[yellow]No output file specified (use --output)[/yellow]")
        
        # Exit with error code if there were processing errors
        if processing_report.failed_rows > 0:
            if config.options.on_error == "fail-fast":
                raise typer.Exit(code=1)
            else:
                console.print(
                    f"[yellow]Warning: {processing_report.failed_rows} rows had errors[/yellow]"
                )
        
        # Exit with error code if SHACL validation failed
        if validate_flag and validation_report and not validation_report.conforms:
            console.print("[red]Validation failed[/red]")
            raise typer.Exit(code=1)
        
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        if verbose:
            import traceback
            console.print(traceback.format_exc())
        raise typer.Exit(code=1)


@app.command()
def validate(
    rdf_file: Path = typer.Option(
        ...,
        "--rdf",
        help="Path to RDF file to validate",
        exists=True,
        dir_okay=False,
    ),
    shapes: Path = typer.Option(
        ...,
        "--shapes",
        help="Path to SHACL shapes file",
        exists=True,
        dir_okay=False,
    ),
    report: Optional[Path] = typer.Option(
        None,
        "--report",
        help="Path to write validation report (JSON)",
        dir_okay=False,
    ),
    inference: Optional[str] = typer.Option(
        None,
        "--inference",
        help="Inference mode (rdfs, owlrl, both)",
    ),
) -> None:
    """Validate RDF file against SHACL shapes."""
    try:
        console.print(f"[blue]Loading RDF from {rdf_file}...[/blue]")
        
        from rdflib import Graph
        
        data_graph = Graph()
        data_graph.parse(rdf_file)
        
        console.print(f"[green]Loaded {len(data_graph)} triples[/green]")
        
        console.print("[blue]Running SHACL validation...[/blue]")
        
        validation_report = validate_rdf(
            data_graph,
            shapes_file=shapes,
            inference=inference,
        )
        
        _display_validation_results(validation_report, verbose=True)
        
        if report:
            write_validation_report(validation_report, report)
            console.print(f"[green]Report written to {report}[/green]")
        
        if not validation_report.conforms:
            raise typer.Exit(code=1)
        
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)


@app.command()
def info(
    mapping: Path = typer.Option(
        ...,
        "--mapping",
        "-m",
        help="Path to mapping configuration file",
        exists=True,
        dir_okay=False,
    ),
) -> None:
    """Display information about mapping configuration."""
    try:
        config = load_mapping_config(mapping)
        
        console.print(f"\n[bold]Mapping Configuration: {mapping}[/bold]\n")
        
        # Namespaces
        console.print("[bold cyan]Namespaces:[/bold cyan]")
        for prefix, uri in config.namespaces.items():
            console.print(f"  {prefix}: {uri}")
        
        # Defaults
        console.print(f"\n[bold cyan]Base IRI:[/bold cyan] {config.defaults.base_iri}")
        if config.defaults.language:
            console.print(f"[bold cyan]Default Language:[/bold cyan] {config.defaults.language}")
        
        # Sheets
        console.print(f"\n[bold cyan]Sheets ({len(config.sheets)}):[/bold cyan]")
        for sheet in config.sheets:
            console.print(f"\n  [bold]{sheet.name}[/bold]")
            console.print(f"    Source: {sheet.source}")
            console.print(f"    Class: {sheet.row_resource.class_type}")
            console.print(f"    IRI Template: {sheet.row_resource.iri_template}")
            console.print(f"    Columns: {len(sheet.columns)}")
            console.print(f"    Linked Objects: {len(sheet.objects)}")
        
        # Validation
        if config.validation and config.validation.shacl:
            console.print(f"\n[bold cyan]Validation:[/bold cyan]")
            console.print(f"  SHACL Enabled: {config.validation.shacl.enabled}")
            console.print(f"  Shapes File: {config.validation.shacl.shapes_file}")
        
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)


def _display_processing_summary(report: ProcessingReport, verbose: bool) -> None:
    """Display processing summary table."""
    table = Table(title="Processing Summary")
    
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")
    
    table.add_row("Total Rows", str(report.total_rows))
    table.add_row("Successful", str(report.successful_rows))
    table.add_row("Failed", str(report.failed_rows))
    table.add_row("Warnings", str(report.warnings))
    
    console.print(table)
    
    # Show error samples
    if report.errors and verbose:
        console.print("\n[bold]Errors (sample):[/bold]")
        for error in report.errors[:10]:  # Show first 10
            console.print(f"  Row {error.row}: {error.error}")
        
        if len(report.errors) > 10:
            console.print(f"  ... and {len(report.errors) - 10} more errors")


def _display_validation_results(report, verbose: bool) -> None:
    """Display validation results."""
    if report.conforms:
        console.print("[bold green]✓ Validation passed[/bold green]")
    else:
        console.print("[bold red]✗ Validation failed[/bold red]")
        console.print(f"\n[bold]Violations ({len(report.results)}):[/bold]")
        
        for result in report.results[:20]:  # Show first 20
            console.print(f"\n  [red]●[/red] {result.focus_node}")
            if result.result_path:
                console.print(f"    Path: {result.result_path}")
            console.print(f"    {result.result_message}")
            console.print(f"    Severity: {result.severity}")
        
        if len(report.results) > 20:
            console.print(f"\n  ... and {len(report.results) - 20} more violations")


@app.command()
def generate(
    ontology: Path = typer.Option(
        ...,
        "--ontology",
        "-ont",
        help="Path to ontology file (TTL, RDF/XML, etc.)",
        exists=True,
        dir_okay=False,
    ),
    spreadsheet: Path = typer.Option(
        ...,
        "--spreadsheet",
        "-s",
        help="Path to spreadsheet file (CSV or XLSX)",
        exists=True,
        dir_okay=False,
    ),
    output: Path = typer.Option(
        ...,
        "--output",
        "-o",
        help="Path to write generated mapping configuration",
        dir_okay=False,
    ),
    base_iri: str = typer.Option(
        "http://example.org/",
        "--base-iri",
        "-b",
        help="Base IRI for generated resources",
    ),
    target_class: Optional[str] = typer.Option(
        None,
        "--class",
        "-c",
        help="Target ontology class (URI or label). If omitted, will auto-detect.",
    ),
    format: str = typer.Option(
        "yaml",
        "--format",
        "-f",
        help="Output format: yaml or json",
    ),
    analyze_only: bool = typer.Option(
        False,
        "--analyze-only",
        help="Only analyze and show suggestions, don't generate mapping",
    ),
    export_schema: bool = typer.Option(
        False,
        "--export-schema",
        help="Export JSON Schema for mapping validation",
    ),
    alignment_report: bool = typer.Option(
        False,
        "--alignment-report",
        help="Generate semantic alignment report with mapping quality metrics",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable detailed logging",
    ),
):
    """
    Generate a mapping configuration from an ontology and spreadsheet.
    
    This command analyzes your ontology and spreadsheet to automatically
    generate a mapping configuration file. It will:
    
    - Extract classes and properties from the ontology
    - Analyze column types and patterns in the spreadsheet
    - Match columns to ontology properties
    - Suggest IRI templates based on identifier columns
    - Detect potential linked objects
    
    The generated configuration can then be refined manually if needed.
    """
    try:
        console.print("[blue]Analyzing ontology...[/blue]")
        onto_analyzer = OntologyAnalyzer(str(ontology))
        console.print(f"  Found {len(onto_analyzer.classes)} classes")
        console.print(f"  Found {len(onto_analyzer.properties)} properties")
        
        console.print("\n[blue]Analyzing spreadsheet...[/blue]")
        sheet_analyzer = SpreadsheetAnalyzer(str(spreadsheet))
        console.print(f"  Columns: {len(sheet_analyzer.columns)}")
        console.print(f"  Identifier columns: {[c.name for c in sheet_analyzer.get_identifier_columns()]}")
        
        if analyze_only:
            console.print("\n[bold]Spreadsheet Analysis:[/bold]")
            console.print(sheet_analyzer.summary())
            
            if target_class:
                # Show properties for target class
                cls = None
                for c in onto_analyzer.classes.values():
                    if c.label == target_class or str(c.uri).endswith(target_class):
                        cls = c
                        break
                
                if cls:
                    console.print(f"\n[bold]Properties for class {cls.label}:[/bold]")
                    props = onto_analyzer.get_properties_for_class(cls.uri)
                    for prop in props:
                        console.print(f"  - {prop.label or prop.uri} (range: {prop.range_type})")
            
            return
        
        console.print("\n[blue]Generating mapping configuration...[/blue]")
        
        config = GeneratorConfig(
            base_iri=base_iri,
            include_comments=True,
            auto_detect_relationships=True,
        )
        
        generator = MappingGenerator(
            str(ontology),
            str(spreadsheet),
            config,
        )
        
        # Generate mapping (with alignment report if requested)
        if alignment_report:
            mapping, report = generator.generate_with_alignment_report(
                target_class=target_class,
                output_path=str(output)
            )
        else:
            mapping = generator.generate(target_class=target_class, output_path=str(output))
            report = None
        
        if verbose:
            console.print("\n[bold]Generated Mapping:[/bold]")
            import json
            console.print(json.dumps(mapping, indent=2))
        
        # Save to file
        if format.lower() == "json":
            generator.save_json(str(output))
        else:
            generator.save_yaml(str(output))
        
        console.print(f"\n[green]✓ Mapping configuration written to {output}[/green]")
        
        # Export and display alignment report if generated
        if report:
            report_file = output.parent / f"{output.stem}_alignment_report.json"
            generator.export_alignment_report(str(report_file))
            console.print(f"[green]✓ Alignment report written to {report_file}[/green]")
            
            # Display summary
            console.print("\n[bold blue]Semantic Alignment Summary[/bold blue]")
            console.print(f"  Mapped Columns: {report.statistics.mapped_columns}/{report.statistics.total_columns} ({report.statistics.mapping_success_rate:.1%})")
            console.print(f"  Average Confidence: {report.statistics.average_confidence:.2f}")
            console.print(f"  High Confidence: {report.statistics.high_confidence_matches}")
            console.print(f"  Medium Confidence: {report.statistics.medium_confidence_matches}")
            console.print(f"  Low Confidence: {report.statistics.low_confidence_matches}")
            
            if report.unmapped_columns:
                console.print(f"\n[yellow]⚠️  {len(report.unmapped_columns)} unmapped columns:[/yellow]")
                for col in report.unmapped_columns[:5]:  # Show first 5
                    console.print(f"  - {col.column_name}")
                if len(report.unmapped_columns) > 5:
                    console.print(f"  ... and {len(report.unmapped_columns) - 5} more")
            
            if report.weak_matches:
                console.print(f"\n[yellow]⚠️  {len(report.weak_matches)} weak matches need review (see report)[/yellow]")
            
            if report.skos_enrichment_suggestions:
                console.print(f"\n[cyan]💡 {len(report.skos_enrichment_suggestions)} SKOS enrichment suggestions available[/cyan]")
                console.print(f"   Review {report_file} for details on improving your ontology")
        
        # Export JSON Schema if requested
        if export_schema:
            schema_file = output.parent / f"{output.stem}_schema.json"
            schema = generator.get_json_schema()
            
            import json
            with open(schema_file, 'w') as f:
                json.dump(schema, f, indent=2)
            
            console.print(f"[green]✓ JSON Schema exported to {schema_file}[/green]")
            console.print("\n[yellow]You can use this schema to validate your mapping configurations.[/yellow]")
        
        # Show next steps
        console.print("\n[bold]Next Steps:[/bold]")
        console.print(f"1. Review the generated mapping: {output}")
        console.print(f"2. Refine column-to-property mappings if needed")
        console.print(f"3. Run conversion:")
        console.print(f"   [cyan]rdfmap convert --mapping {output} --format ttl --output output.ttl[/cyan]")
        
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        if verbose:
            import traceback
            console.print(traceback.format_exc())
        raise typer.Exit(code=1)


@app.command()
def enrich(
    ontology: Path = typer.Option(
        ...,
        "--ontology",
        "-ont",
        help="Path to ontology file to enrich",
        exists=True,
        dir_okay=False,
    ),
    alignment_report: Path = typer.Option(
        ...,
        "--alignment-report",
        "-r",
        help="Path to alignment report JSON file",
        exists=True,
        dir_okay=False,
    ),
    output: Path = typer.Option(
        ...,
        "--output",
        "-o",
        help="Path to write enriched ontology",
        dir_okay=False,
    ),
    interactive: bool = typer.Option(
        False,
        "--interactive",
        "-i",
        help="Interactive mode with prompts for each suggestion",
    ),
    auto_apply: bool = typer.Option(
        False,
        "--auto-apply",
        help="Automatically apply all suggestions above confidence threshold",
    ),
    confidence_threshold: float = typer.Option(
        0.6,
        "--confidence-threshold",
        "-t",
        help="Minimum confidence threshold (0.0-1.0) for suggestions",
    ),
    agent: Optional[str] = typer.Option(
        None,
        "--agent",
        help="User/agent name for provenance tracking (default: current user)",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable detailed logging",
    ),
):
    """
    Enrich ontology with SKOS labels based on alignment report suggestions.
    
    This command applies semantic alignment suggestions to your ontology by
    adding SKOS labels (prefLabel, altLabel, hiddenLabel) with full provenance
    tracking. It can run in:
    
    - Interactive mode: Review each suggestion with prompts
    - Auto-apply mode: Automatically apply high-confidence suggestions
    - Batch mode: Process all suggestions non-interactively
    
    All enrichments are tracked with provenance metadata including timestamps,
    agents, and rationales.
    """
    try:
        # Load alignment report
        console.print(f"[blue]Loading alignment report from {alignment_report}...[/blue]")
        with open(alignment_report) as f:
            report_data = json.load(f)
        
        report = AlignmentReport(**report_data)
        
        # Count suggestions
        total_suggestions = len(report.skos_enrichment_suggestions)
        
        if total_suggestions == 0:
            console.print("[yellow]No SKOS enrichment suggestions found in report.[/yellow]")
            return
        
        console.print(f"  Found {total_suggestions} SKOS enrichment suggestions")
        console.print(f"  Confidence threshold: {confidence_threshold:.2f}")
        
        # Initialize enricher
        console.print(f"\n[blue]Loading ontology from {ontology}...[/blue]")
        enricher = OntologyEnricher(
            ontology_path=str(ontology),
            agent=agent
        )
        
        if verbose:
            console.print(f"  Loaded {len(enricher.graph)} triples")
        
        # Process enrichments
        if interactive:
            console.print("\n[bold cyan]Interactive Enrichment Mode[/bold cyan]")
            console.print("Review each suggestion and choose an action:\n")
            result = _interactive_enrichment(enricher, report, confidence_threshold)
        elif auto_apply:
            console.print(f"\n[bold cyan]Auto-applying suggestions with confidence >= {confidence_threshold}[/bold cyan]")
            result = enricher.enrich_from_alignment_report(
                report,
                confidence_threshold=confidence_threshold,
                auto_apply=True
            )
        else:
            console.print("[yellow]Neither --interactive nor --auto-apply specified.[/yellow]")
            console.print("Use --interactive for manual review or --auto-apply for automatic application.")
            return
        
        # Save enriched ontology
        if result.operations_applied:
            console.print(f"\n[blue]Saving enriched ontology to {output}...[/blue]")
            enricher.save(str(output))
            console.print(f"[green]✓ Enriched ontology saved[/green]")
        else:
            console.print("[yellow]No changes applied. Ontology not modified.[/yellow]")
            return
        
        # Display summary
        console.print("\n[bold green]Enrichment Summary[/bold green]")
        console.print(f"  Total suggestions: {result.total_operations}")
        console.print(f"  Applied: {len(result.operations_applied)}")
        console.print(f"  Rejected/Skipped: {len(result.operations_rejected)}")
        console.print(f"  Acceptance rate: {result.acceptance_rate:.1%}")
        
        # Show what was added
        label_counts = {}
        for op in result.operations_applied:
            label_type = op.skos_addition.label_type.value
            label_counts[label_type] = label_counts.get(label_type, 0) + 1
        
        if label_counts:
            console.print("\n  Labels added:")
            for label_type, count in label_counts.items():
                console.print(f"    - {label_type}: {count}")
        
        # Show provenance info
        if result.operations_applied:
            first_op = result.operations_applied[0]
            console.print("\n  Provenance:")
            console.print(f"    Agent: {first_op.provenance.agent}")
            console.print(f"    Timestamp: {first_op.provenance.timestamp.isoformat()}")
            console.print(f"    Tool: {first_op.provenance.tool_version}")
        
        # Show turtle additions
        if verbose and result.turtle_additions:
            console.print("\n[bold]Generated Turtle:[/bold]")
            console.print(result.turtle_additions)
        
        # Next steps
        console.print("\n[bold]Next Steps:[/bold]")
        console.print(f"1. Review enriched ontology: {output}")
        console.print(f"2. Commit to version control")
        console.print(f"3. Re-run mapping generation with enriched ontology:")
        console.print(f"   [cyan]rdfmap generate --ontology {output} --spreadsheet <data.csv> --output mapping.yaml[/cyan]")
        
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        if verbose:
            import traceback
            console.print(traceback.format_exc())
        raise typer.Exit(code=1)


def _interactive_enrichment(
    enricher: OntologyEnricher,
    report: AlignmentReport,
    confidence_threshold: float
) -> EnrichmentResult:
    """Run interactive enrichment workflow with user prompts."""
    
    counter = [0]  # Mutable counter for closure
    total = len(report.skos_enrichment_suggestions)
    
    def prompt_user(skos_addition: SKOSAddition) -> InteractivePromptResponse:
        """Prompt user for a single enrichment decision."""
        counter[0] += 1
        
        console.print(f"\n[bold][{counter[0]}/{total}] Column: {skos_addition.source_column}[/bold]")
        console.print(f"  Suggested property: [cyan]{skos_addition.property_label}[/cyan]")
        console.print(f"  Property URI: {skos_addition.property_uri}")
        console.print(f"  Confidence: {skos_addition.confidence:.2f}")
        console.print(f"  Rationale: {skos_addition.rationale}")
        
        # Show existing labels
        existing = enricher.get_property_labels(skos_addition.property_uri)
        if any(existing.values()):
            console.print("\n  Existing labels:")
            for label_type, labels in existing.items():
                if labels:
                    console.print(f"    {label_type}: {', '.join(labels)}")
        
        # Confidence indicator
        if skos_addition.confidence >= 0.8:
            confidence_indicator = "[green]●[/green] High confidence"
        elif skos_addition.confidence >= 0.5:
            confidence_indicator = "[yellow]●[/yellow] Medium confidence"
        else:
            confidence_indicator = "[red]●[/red] Low confidence - review carefully"
        console.print(f"\n  {confidence_indicator}")
        
        # Prompt for action
        console.print(f"\n  Add [cyan]{skos_addition.label_type.value}[/cyan] '{skos_addition.label_value}' to this property?")
        console.print("  [Y]es / [n]o / [e]dit / [s]kip all / [?]help")
        
        while True:
            action_input = typer.prompt("  Action", default="y").lower().strip()
            
            if action_input in ("?", "help"):
                console.print("\n  Actions:")
                console.print("    y/yes   - Accept and add this label")
                console.print("    n/no    - Reject this suggestion")
                console.print("    e/edit  - Edit the label value before adding")
                console.print("    s/skip  - Skip all remaining suggestions")
                console.print("    ?/help  - Show this help")
                continue
            
            if action_input == "s" or action_input == "skip":
                return InteractivePromptResponse(
                    action=EnrichmentAction.SKIPPED,
                    skip_remaining=True
                )
            
            if action_input in ("n", "no"):
                return InteractivePromptResponse(action=EnrichmentAction.REJECTED)
            
            if action_input in ("e", "edit"):
                edited = typer.prompt("  Edit label value", default=skos_addition.label_value)
                response = InteractivePromptResponse(
                    action=EnrichmentAction.EDITED,
                    edited_label=edited
                )
                break
            
            if action_input in ("y", "yes", ""):
                response = InteractivePromptResponse(action=EnrichmentAction.ACCEPTED)
                break
            
            console.print("  [red]Invalid action. Type ? for help.[/red]")
        
        # Ask for optional annotations
        if response.action in (EnrichmentAction.ACCEPTED, EnrichmentAction.EDITED):
            console.print("\n  Add optional annotations? (press Enter to skip)")
            
            scope_note = typer.prompt("  Scope note (usage guidance)", default="", show_default=False)
            if scope_note.strip():
                response.scope_note = scope_note.strip()
            
            example = typer.prompt("  Example value", default="", show_default=False)
            if example.strip():
                response.example = example.strip()
            
            definition = typer.prompt("  Definition", default="", show_default=False)
            if definition.strip():
                response.definition = definition.strip()
        
        return response
    
    # Run enrichment with interactive callback
    result = enricher.enrich_from_alignment_report(
        report,
        confidence_threshold=confidence_threshold,
        interactive_callback=prompt_user
    )
    
    return result


@app.command()
def stats(
    reports_dir: Path = typer.Option(
        ...,
        "--reports-dir",
        "-r",
        help="Directory containing alignment report JSON files",
        exists=True,
        file_okay=False,
    ),
    output: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        help="Path to write statistics JSON file",
        dir_okay=False,
    ),
    format: str = typer.Option(
        "text",
        "--format",
        "-f",
        help="Output format: text, json, or both",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable detailed logging",
    ),
):
    """
    Analyze alignment reports to track trends and improvements over time.
    
    This command analyzes multiple alignment reports from a directory to:
    
    - Track mapping success rates over time
    - Identify most problematic columns
    - Show improvement trends
    - Highlight columns that improved after enrichment
    - Calculate SKOS enrichment impact
    
    This is useful for demonstrating the value of ontology enrichment
    and tracking the continuous improvement of your semantic alignment.
    """
    try:
        console.print(f"[blue]Loading alignment reports from {reports_dir}...[/blue]")
        
        analyzer = AlignmentStatsAnalyzer()
        count = analyzer.load_reports(reports_dir)
        
        if count == 0:
            console.print("[yellow]No alignment reports found in directory.[/yellow]")
            console.print("Tip: Generate reports with `rdfmap generate --alignment-report`")
            return
        
        console.print(f"  Loaded {count} reports")
        
        console.print("\n[blue]Analyzing trends and statistics...[/blue]")
        stats = analyzer.analyze()
        
        # Text output
        if format.lower() in ("text", "both"):
            console.print("\n")
            summary = analyzer.generate_summary_report(stats)
            console.print(summary)
        
        # JSON output
        if output or format.lower() in ("json", "both"):
            output_path = output or reports_dir / "alignment_statistics.json"
            
            with open(output_path, 'w') as f:
                json.dump(stats.model_dump(mode='json'), f, indent=2, default=str)
            
            console.print(f"\n[green]✓ Statistics written to {output_path}[/green]")
        
        # Detailed breakdown if verbose
        if verbose and stats.timeline:
            console.print("\n[bold]Timeline Details:[/bold]")
            
            table = Table(title="Alignment Report Timeline")
            table.add_column("Date", style="cyan")
            table.add_column("Report", style="magenta")
            table.add_column("Success Rate", justify="right")
            table.add_column("Avg Confidence", justify="right")
            table.add_column("Unmapped", justify="right")
            
            for point in stats.timeline:
                table.add_row(
                    point.timestamp.strftime("%Y-%m-%d"),
                    point.report_file[:30],
                    f"{point.mapping_success_rate:.1%}",
                    f"{point.average_confidence:.2f}",
                    str(point.unmapped_columns)
                )
            
            console.print(table)
        
        # Show next steps
        console.print("\n[bold]Insights:[/bold]")
        
        if stats.trend_analysis:
            if stats.trend_analysis.overall_trend == "improving":
                console.print("  ✓ Your alignment is improving over time!")
                console.print(f"    Success rate increased by {stats.trend_analysis.success_rate_change:+.1%}")
            elif stats.trend_analysis.overall_trend == "declining":
                console.print("  ⚠ Alignment quality has declined")
                console.print("    Consider reviewing recent ontology changes")
            else:
                console.print("  → Alignment quality is stable")
        
        if stats.most_problematic_columns:
            console.print(f"\n  Focus enrichment efforts on these {len(stats.most_problematic_columns)} problematic columns")
            console.print("  Run: [cyan]rdfmap enrich --interactive[/cyan] to improve them")
        
        if stats.total_skos_suggestions_generated > 0:
            console.print(f"\n  {stats.total_skos_suggestions_generated} SKOS enrichment suggestions available")
            console.print("  These represent opportunities to improve your ontology")
        
    except FileNotFoundError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        if verbose:
            import traceback
            console.print(traceback.format_exc())
        raise typer.Exit(code=1)


@app.command()
def validate_ontology(
    ontology: Path = typer.Option(
        ...,
        "--ontology",
        "-ont",
        help="Path to ontology file to validate",
        exists=True,
        dir_okay=False,
    ),
    min_coverage: float = typer.Option(
        0.7,
        "--min-coverage",
        "-m",
        help="Minimum acceptable SKOS coverage (0.0-1.0)",
    ),
    output: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        help="Path to write coverage report JSON",
        dir_okay=False,
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable detailed logging",
    ),
):
    """
    Validate SKOS label coverage in an ontology.
    
    This command analyzes your ontology to:
    
    - Check SKOS label coverage (prefLabel, altLabel, hiddenLabel)
    - Identify properties missing labels
    - Calculate coverage percentages by class
    - Generate recommendations for improvement
    
    Good SKOS coverage (70%+) significantly improves semantic alignment
    quality by providing more matching opportunities for column names.
    """
    try:
        console.print(f"[blue]Analyzing SKOS coverage in {ontology}...[/blue]")
        
        validator = SKOSCoverageValidator(str(ontology))
        report = validator.analyze(min_coverage=min_coverage)
        
        # Display summary
        console.print("\n[bold cyan]SKOS COVERAGE REPORT[/bold cyan]")
        console.print("=" * 70)
        console.print(f"Ontology: {report.ontology_file}")
        console.print(f"Total Classes: {report.total_classes}")
        console.print(f"Total Properties: {report.total_properties}")
        console.print("")
        
        # Coverage stats
        coverage_color = "green" if report.overall_coverage_percentage >= min_coverage else "yellow"
        console.print(f"[bold]Overall SKOS Coverage:[/bold] [{coverage_color}]{report.overall_coverage_percentage:.1%}[/{coverage_color}]")
        console.print(f"  Properties with SKOS labels: {report.properties_with_skos}")
        console.print(f"  Properties without SKOS labels: {report.properties_without_skos}")
        console.print(f"  Average labels per property: {report.avg_labels_per_property:.1f}")
        console.print("")
        
        # Class breakdown
        if report.class_coverage and verbose:
            console.print("[bold]Coverage by Class:[/bold]")
            
            table = Table()
            table.add_column("Class", style="cyan")
            table.add_column("Properties", justify="right")
            table.add_column("With SKOS", justify="right")
            table.add_column("Coverage", justify="right")
            
            for cls_cov in sorted(report.class_coverage, key=lambda x: x.coverage_percentage):
                coverage_str = f"{cls_cov.coverage_percentage:.1%}"
                if cls_cov.coverage_percentage >= min_coverage:
                    coverage_str = f"[green]{coverage_str}[/green]"
                else:
                    coverage_str = f"[yellow]{coverage_str}[/yellow]"
                
                table.add_row(
                    cls_cov.class_label or cls_cov.class_uri.split('#')[-1],
                    str(cls_cov.total_properties),
                    str(cls_cov.properties_with_skos),
                    coverage_str
                )
            
            console.print(table)
            console.print("")
        
        # Missing labels
        if report.properties_missing_all_labels:
            console.print(f"[yellow]⚠ {len(report.properties_missing_all_labels)} properties have NO SKOS labels:[/yellow]")
            for prop_uri in report.properties_missing_all_labels[:5]:
                prop_name = prop_uri.split('#')[-1] if '#' in prop_uri else prop_uri.split('/')[-1]
                console.print(f"  • {prop_name}")
            if len(report.properties_missing_all_labels) > 5:
                console.print(f"  ... and {len(report.properties_missing_all_labels) - 5} more")
            console.print("")
        
        # Recommendations
        if report.recommendations:
            console.print("[bold]Recommendations:[/bold]")
            for rec in report.recommendations:
                if rec.startswith("✓"):
                    console.print(f"[green]{rec}[/green]")
                elif rec.startswith("  •"):
                    console.print(f"  [dim]{rec}[/dim]")
                else:
                    console.print(f"[yellow]  • {rec}[/yellow]")
            console.print("")
        
        # Export JSON
        if output:
            with open(output, 'w') as f:
                json.dump(report.model_dump(mode='json'), f, indent=2)
            console.print(f"[green]✓ Coverage report written to {output}[/green]")
        
        # Pass/Fail
        if report.overall_coverage_percentage >= min_coverage:
            console.print(f"[bold green]✓ PASS[/bold green] - Coverage meets minimum threshold ({min_coverage:.1%})")
            exit_code = 0
        else:
            console.print(f"[bold yellow]⚠ NEEDS IMPROVEMENT[/bold yellow] - Coverage below threshold ({min_coverage:.1%})")
            console.print("\nNext steps:")
            console.print("  1. Review properties missing labels (above)")
            console.print("  2. Use alignment reports to identify needed labels:")
            console.print("     [cyan]rdfmap generate --alignment-report ...[/cyan]")
            console.print("  3. Enrich ontology with missing labels:")
            console.print("     [cyan]rdfmap enrich --interactive ...[/cyan]")
            exit_code = 1
        
        raise typer.Exit(code=exit_code)
        
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        if verbose:
            import traceback
            console.print(traceback.format_exc())
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()



