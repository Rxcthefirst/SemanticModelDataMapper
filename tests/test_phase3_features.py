"""Tests for alignment statistics analyzer and SKOS coverage validator.

These tests verify Phase 3 functionality for tracking alignment
improvement over time and validating ontology SKOS coverage.
"""

import json
import tempfile
from pathlib import Path
from datetime import datetime, timedelta

import pytest
from rdflib import Graph, Namespace, Literal
from rdflib.namespace import RDF, RDFS, OWL, SKOS

# Alignment stats analyzer imports
from rdfmap.analyzer.alignment_stats import (
    AlignmentStatsAnalyzer,
    AlignmentStatistics as AnalyzerStatistics,
    ColumnStats,
    TimeSeriesPoint,
    TrendAnalysis,
)
from rdfmap.models.alignment import (
    AlignmentReport,
    AlignmentStatistics,
    UnmappedColumn,
    WeakMatch,
    SKOSEnrichmentSuggestion,
    MatchType,
    ConfidenceLevel,
)

# SKOS coverage validator imports
from rdfmap.validator.skos_coverage import (
    SKOSCoverageValidator,
    PropertyCoverage,
    ClassCoverage,
    SKOSCoverageReport,
)


# ============================================================================
# ALIGNMENT STATS ANALYZER TESTS
# ============================================================================

@pytest.fixture
def temp_report_dir():
    """Create temporary directory for test reports."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


def create_alignment_report(
    generated_at: datetime,
    mapped: int,
    unmapped: int,
    unmapped_names: list[str],
    weak_match_names: list[tuple[str, float]],
    skos_suggestions_count: int = 0
) -> AlignmentReport:
    """Helper to create an alignment report."""
    total = mapped + unmapped
    
    stats = AlignmentStatistics(
        total_columns=total,
        mapped_columns=mapped,
        unmapped_columns=unmapped,
        high_confidence_matches=int(mapped * 0.5),
        medium_confidence_matches=int(mapped * 0.3),
        low_confidence_matches=int(mapped * 0.2),
        very_low_confidence_matches=0,
        mapping_success_rate=mapped / total if total > 0 else 0.0,
        average_confidence=0.70,
    )
    
    unmapped_cols = [
        UnmappedColumn(column_name=name, sample_values=["val1", "val2"])
        for name in unmapped_names
    ]
    
    weak_matches = [
        WeakMatch(
            column_name=name,
            matched_property=f"http://example.org/hr#{name}",
            match_type=MatchType.FUZZY,
            confidence_score=conf,
            confidence_level=ConfidenceLevel.LOW,
            matched_via="fuzzy match",
            sample_values=["val1"],
        )
        for name, conf in weak_match_names
    ]
    
    skos_suggestions = [
        SKOSEnrichmentSuggestion(
            property_uri=f"http://example.org/hr#prop{i}",
            property_label=f"prop{i}",
            suggested_label_type="skos:hiddenLabel",
            suggested_label_value=f"label{i}",
            turtle_snippet=f'ex:prop{i} skos:hiddenLabel "label{i}" .',
            justification="Improve matching",
        )
        for i in range(skos_suggestions_count)
    ]
    
    return AlignmentReport(
        generated_at=generated_at,
        ontology_file="test.ttl",
        spreadsheet_file="test.csv",
        target_class="Person",
        statistics=stats,
        unmapped_columns=unmapped_cols,
        weak_matches=weak_matches,
        skos_enrichment_suggestions=skos_suggestions,
    )


class TestAlignmentStatsAnalyzer:
    """Test AlignmentStatsAnalyzer class."""
    
    def test_load_reports_from_directory(self, temp_report_dir):
        """Test loading multiple reports from directory."""
        # Create 3 reports
        base_date = datetime(2025, 10, 1)
        for i in range(3):
            report = create_alignment_report(
                generated_at=base_date + timedelta(days=i*7),
                mapped=6 + i,
                unmapped=4 - i,
                unmapped_names=[f"col{j}" for j in range(4-i)],
                weak_match_names=[],
            )
            
            report_path = temp_report_dir / f"alignment_report_{i+1}.json"
            with open(report_path, "w") as f:
                json.dump(report.model_dump(mode="json"), f, default=str)
        
        analyzer = AlignmentStatsAnalyzer()
        count = analyzer.load_reports(temp_report_dir)
        
        assert count == 3
        assert len(analyzer.reports) == 3
    
    def test_analyze_with_improving_trend(self, temp_report_dir):
        """Test analysis showing improvement over time."""
        base_date = datetime(2025, 10, 1)
        
        # Report 1: 60% success (6/10)
        report1 = create_alignment_report(
            generated_at=base_date,
            mapped=6,
            unmapped=4,
            unmapped_names=["emp_num", "mgr", "dept_code", "salary_band"],
            weak_match_names=[("start_date", 0.45)],
            skos_suggestions_count=2,
        )
        
        # Report 2: 80% success (8/10) - improved
        report2 = create_alignment_report(
            generated_at=base_date + timedelta(days=7),
            mapped=8,
            unmapped=2,
            unmapped_names=["dept_code", "salary_band"],
            weak_match_names=[],
            skos_suggestions_count=1,
        )
        
        # Report 3: 90% success (9/10) - even better
        report3 = create_alignment_report(
            generated_at=base_date + timedelta(days=14),
            mapped=9,
            unmapped=1,
            unmapped_names=["salary_band"],
            weak_match_names=[],
            skos_suggestions_count=0,
        )
        
        # Save reports
        for i, report in enumerate([report1, report2, report3], 1):
            path = temp_report_dir / f"alignment_report_{i}.json"
            with open(path, "w") as f:
                json.dump(report.model_dump(mode="json"), f, default=str)
        
        # Analyze
        analyzer = AlignmentStatsAnalyzer()
        analyzer.load_reports(temp_report_dir)
        stats = analyzer.analyze()
        
        # Check overall stats
        assert stats.total_reports_analyzed == 3
        assert stats.unique_columns_seen > 0
        
        # Check timeline
        assert len(stats.timeline) == 3
        assert stats.timeline[0].mapping_success_rate == 0.6
        assert stats.timeline[2].mapping_success_rate == 0.9
        
        # Check trend
        assert stats.trend_analysis is not None
        assert stats.trend_analysis.overall_trend == "improving"
        assert stats.trend_analysis.success_rate_change > 0
        
        # Check SKOS suggestions
        assert stats.total_skos_suggestions_generated == 3
    
    def test_identify_problematic_columns(self, temp_report_dir):
        """Test identification of problematic columns."""
        base_date = datetime(2025, 10, 1)
        
        # Create reports where "compensation" column is always unmapped
        for i in range(3):
            report = create_alignment_report(
                generated_at=base_date + timedelta(days=i*7),
                mapped=8,
                unmapped=2,
                unmapped_names=["compensation_bucket", f"temp_{i}"],
                weak_match_names=[],
            )
            
            path = temp_report_dir / f"alignment_report_{i+1}.json"
            with open(path, "w") as f:
                json.dump(report.model_dump(mode="json"), f, default=str)
        
        analyzer = AlignmentStatsAnalyzer()
        analyzer.load_reports(temp_report_dir)
        stats = analyzer.analyze()
        
        # compensation_bucket should be in never_mapped list
        assert "compensation_bucket" in stats.never_mapped_columns
        
        # Should be in problematic columns
        problematic_names = [c.column_name for c in stats.most_problematic_columns]
        assert "compensation_bucket" in problematic_names
    
    def test_empty_directory(self, temp_report_dir):
        """Test handling of empty directory."""
        analyzer = AlignmentStatsAnalyzer()
        count = analyzer.load_reports(temp_report_dir)
        
        assert count == 0
        stats = analyzer.analyze()
        assert stats.total_reports_analyzed == 0
    
    def test_export_to_json(self, temp_report_dir):
        """Test JSON export of statistics."""
        base_date = datetime(2025, 10, 1)
        
        report = create_alignment_report(
            generated_at=base_date,
            mapped=7,
            unmapped=3,
            unmapped_names=["col1", "col2", "col3"],
            weak_match_names=[],
        )
        
        report_path = temp_report_dir / "alignment_report_1.json"
        with open(report_path, "w") as f:
            json.dump(report.model_dump(mode="json"), f, default=str)
        
        analyzer = AlignmentStatsAnalyzer()
        analyzer.load_reports(temp_report_dir)
        stats = analyzer.analyze()
        
        output_path = temp_report_dir / "stats.json"
        analyzer.export_to_json(stats, output_path)
        
        assert output_path.exists()
        
        # Verify JSON is valid
        with open(output_path) as f:
            data = json.load(f)
        
        assert data["total_reports_analyzed"] == 1


# ============================================================================
# SKOS COVERAGE VALIDATOR TESTS
# ============================================================================

@pytest.fixture
def temp_ontology_file():
    """Create temporary ontology file."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".ttl", delete=False) as f:
        yield Path(f.name)


@pytest.fixture
def ontology_with_good_coverage(temp_ontology_file):
    """Create ontology with good SKOS coverage."""
    EX = Namespace("http://example.org/hr#")
    
    g = Graph()
    g.bind("ex", EX)
    g.bind("skos", SKOS)
    
    # Person class
    g.add((EX.Person, RDF.type, OWL.Class))
    g.add((EX.Person, RDFS.label, Literal("Person")))
    
    # firstName - complete coverage
    g.add((EX.firstName, RDF.type, OWL.DatatypeProperty))
    g.add((EX.firstName, RDFS.domain, EX.Person))
    g.add((EX.firstName, SKOS.prefLabel, Literal("first name")))
    g.add((EX.firstName, SKOS.altLabel, Literal("given name")))
    g.add((EX.firstName, SKOS.hiddenLabel, Literal("fname")))
    g.add((EX.firstName, SKOS.hiddenLabel, Literal("first_name")))
    
    # lastName - good coverage
    g.add((EX.lastName, RDF.type, OWL.DatatypeProperty))
    g.add((EX.lastName, RDFS.domain, EX.Person))
    g.add((EX.lastName, SKOS.prefLabel, Literal("last name")))
    g.add((EX.lastName, SKOS.altLabel, Literal("surname")))
    g.add((EX.lastName, SKOS.hiddenLabel, Literal("lname")))
    
    g.serialize(destination=str(temp_ontology_file), format="turtle")
    return temp_ontology_file


@pytest.fixture
def ontology_with_poor_coverage(temp_ontology_file):
    """Create ontology with poor SKOS coverage."""
    EX = Namespace("http://example.org/hr#")
    
    g = Graph()
    g.bind("ex", EX)
    
    # Person class
    g.add((EX.Person, RDF.type, OWL.Class))
    
    # Properties with no/minimal SKOS labels
    g.add((EX.firstName, RDF.type, OWL.DatatypeProperty))
    g.add((EX.firstName, RDFS.domain, EX.Person))
    # No SKOS labels
    
    g.add((EX.lastName, RDF.type, OWL.DatatypeProperty))
    g.add((EX.lastName, RDFS.domain, EX.Person))
    # No SKOS labels
    
    g.add((EX.email, RDF.type, OWL.DatatypeProperty))
    g.add((EX.email, RDFS.domain, EX.Person))
    g.add((EX.email, SKOS.prefLabel, Literal("email")))
    # Only one SKOS label
    
    g.serialize(destination=str(temp_ontology_file), format="turtle")
    return temp_ontology_file


class TestSKOSCoverageValidator:
    """Test SKOSCoverageValidator class."""
    
    def test_initialization(self, ontology_with_good_coverage):
        """Test validator initialization."""
        validator = SKOSCoverageValidator(str(ontology_with_good_coverage))
        
        assert validator.ontology_path == str(ontology_with_good_coverage)
        assert len(validator.graph) > 0
    
    def test_analyze_good_coverage(self, ontology_with_good_coverage):
        """Test analysis of ontology with good SKOS coverage."""
        validator = SKOSCoverageValidator(str(ontology_with_good_coverage))
        report = validator.analyze(min_coverage=0.7)
        
        # Should have 2 properties
        assert report.total_properties == 2
        assert report.properties_with_skos == 2
        assert report.properties_without_skos == 0
        assert report.overall_coverage_percentage == 1.0
        
        # No missing labels
        assert len(report.properties_missing_all_labels) == 0
        
        # Good average labels per property
        assert report.avg_labels_per_property > 2.0
    
    def test_analyze_poor_coverage(self, ontology_with_poor_coverage):
        """Test analysis of ontology with poor SKOS coverage."""
        validator = SKOSCoverageValidator(str(ontology_with_poor_coverage))
        report = validator.analyze(min_coverage=0.7)
        
        # Should have 3 properties
        assert report.total_properties == 3
        
        # Only email has SKOS label
        assert report.properties_with_skos == 1
        assert report.properties_without_skos == 2
        
        # Poor coverage
        assert report.overall_coverage_percentage < 0.5
        
        # Should identify missing labels
        assert len(report.properties_missing_all_labels) == 2
        
        # Should generate recommendations
        assert len(report.recommendations) > 0
        
        # Should fail threshold
        assert report.overall_coverage_percentage < 0.7
    
    def test_property_coverage_details(self, ontology_with_good_coverage):
        """Test detailed property coverage analysis."""
        validator = SKOSCoverageValidator(str(ontology_with_good_coverage))
        report = validator.analyze()
        
        # Find firstName property
        first_name_coverage = None
        for class_cov in report.class_coverage:
            for prop_cov in class_cov.properties:
                if "firstName" in prop_cov.property_uri:
                    first_name_coverage = prop_cov
                    break
        
        assert first_name_coverage is not None
        assert first_name_coverage.has_pref_label
        assert first_name_coverage.has_alt_labels
        assert first_name_coverage.has_hidden_labels
        assert first_name_coverage.total_skos_labels >= 4
        assert first_name_coverage.coverage_score > 0.8
    
    def test_recommendations_generation(self, ontology_with_poor_coverage):
        """Test generation of improvement recommendations."""
        validator = SKOSCoverageValidator(str(ontology_with_poor_coverage))
        report = validator.analyze(min_coverage=0.7)
        
        assert len(report.recommendations) > 0
        
        # Should recommend improving coverage
        has_coverage_rec = any("coverage" in rec.lower() for rec in report.recommendations)
        assert has_coverage_rec
    
    def test_empty_ontology(self, temp_ontology_file):
        """Test handling of empty ontology."""
        g = Graph()
        g.serialize(destination=str(temp_ontology_file), format="turtle")
        
        validator = SKOSCoverageValidator(str(temp_ontology_file))
        report = validator.analyze()
        
        assert report.total_properties == 0
        assert report.overall_coverage_percentage == 0.0


# ============================================================================
# DATA MODEL TESTS
# ============================================================================

class TestColumnStats:
    """Test ColumnStats model."""
    
    def test_column_stats_creation(self):
        """Test creating column stats."""
        stats = ColumnStats(
            column_name="test_column",
            total_appearances=5,
            times_mapped=3,
            times_unmapped=2,
            mapping_success_rate=0.6,
            avg_confidence=0.75,
        )
        
        assert stats.column_name == "test_column"
        assert stats.mapping_success_rate == 0.6


class TestTimeSeriesPoint:
    """Test TimeSeriesPoint model."""
    
    def test_time_series_point_creation(self):
        """Test creating time series point."""
        point = TimeSeriesPoint(
            timestamp=datetime(2025, 10, 1),
            report_file="report1.json",
            total_columns=10,
            mapped_columns=7,
            unmapped_columns=3,
            mapping_success_rate=0.7,
            average_confidence=0.68,
            high_confidence_matches=4,
            medium_confidence_matches=2,
            low_confidence_matches=1,
            very_low_confidence_matches=0,
        )
        
        assert point.mapping_success_rate == 0.7


class TestPropertyCoverage:
    """Test PropertyCoverage model."""
    
    def test_property_coverage_creation(self):
        """Test creating property coverage."""
        coverage = PropertyCoverage(
            property_uri="http://example.org/hr#firstName",
            has_pref_label=True,
            has_alt_labels=True,
            total_skos_labels=4,
            coverage_score=0.95,
        )
        
        assert coverage.property_uri == "http://example.org/hr#firstName"
        assert coverage.total_skos_labels == 4
