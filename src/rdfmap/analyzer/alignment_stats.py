"""Alignment statistics aggregator and trend analyzer.

This module provides tools to analyze multiple alignment reports over time,
track improvement trends, identify problematic columns, and generate
statistics for demonstrating the value of ontology enrichment.
"""

import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from collections import defaultdict, Counter
from pydantic import BaseModel, Field

from ..models.alignment import AlignmentReport, MatchType, ConfidenceLevel


class ColumnStats(BaseModel):
    """Statistics for a specific column across multiple reports."""
    column_name: str
    total_appearances: int = 0
    times_mapped: int = 0
    times_unmapped: int = 0
    mapping_success_rate: float = 0.0
    avg_confidence: float = 0.0
    match_types: Dict[str, int] = Field(default_factory=dict)
    last_seen: Optional[datetime] = None
    improvement_trend: Optional[str] = None  # "improving", "stable", "declining"


class TimeSeriesPoint(BaseModel):
    """A single point in the alignment timeline."""
    timestamp: datetime
    report_file: str
    total_columns: int
    mapped_columns: int
    unmapped_columns: int
    mapping_success_rate: float
    average_confidence: float
    high_confidence_matches: int
    medium_confidence_matches: int
    low_confidence_matches: int
    very_low_confidence_matches: int


class TrendAnalysis(BaseModel):
    """Trend analysis results."""
    overall_trend: str  # "improving", "stable", "declining"
    success_rate_change: float  # Percentage point change
    confidence_change: float
    initial_success_rate: float
    current_success_rate: float
    initial_avg_confidence: float
    current_avg_confidence: float
    total_improvement: float  # Combined metric


class AlignmentStatistics(BaseModel):
    """Aggregated statistics across multiple alignment reports."""
    
    # Timeline
    timeline: List[TimeSeriesPoint] = Field(default_factory=list)
    
    # Overall statistics
    total_reports_analyzed: int = 0
    date_range_start: Optional[datetime] = None
    date_range_end: Optional[datetime] = None
    
    # Column-level statistics
    unique_columns_seen: int = 0
    most_problematic_columns: List[ColumnStats] = Field(default_factory=list)
    most_improved_columns: List[ColumnStats] = Field(default_factory=list)
    never_mapped_columns: List[str] = Field(default_factory=list)
    
    # Aggregate metrics
    overall_success_rate: float = 0.0
    overall_avg_confidence: float = 0.0
    trend_analysis: Optional[TrendAnalysis] = None
    
    # SKOS enrichment impact
    total_skos_suggestions_generated: int = 0
    skos_suggestions_by_type: Dict[str, int] = Field(default_factory=dict)


class AlignmentStatsAnalyzer:
    """Analyzes multiple alignment reports to track trends and improvements."""
    
    def __init__(self):
        """Initialize the analyzer."""
        self.reports: List[Tuple[Path, AlignmentReport]] = []
        self.column_history: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        
    def load_reports(self, report_dir: Path) -> int:
        """Load all alignment reports from a directory.
        
        Args:
            report_dir: Directory containing alignment report JSON files
            
        Returns:
            Number of reports loaded
        """
        if not report_dir.exists():
            raise FileNotFoundError(f"Report directory not found: {report_dir}")
        
        json_files = list(report_dir.glob("*alignment_report*.json"))
        
        for json_file in json_files:
            try:
                with open(json_file) as f:
                    data = json.load(f)
                    report = AlignmentReport(**data)
                    self.reports.append((json_file, report))
            except Exception as e:
                print(f"Warning: Failed to load {json_file}: {e}")
                continue
        
        # Sort by timestamp
        self.reports.sort(key=lambda x: x[1].generated_at)
        
        return len(self.reports)
    
    def add_report(self, report_path: Path, report: AlignmentReport):
        """Add a single report to the analysis.
        
        Args:
            report_path: Path to the report file
            report: Parsed AlignmentReport object
        """
        self.reports.append((report_path, report))
        self.reports.sort(key=lambda x: x[1].generated_at)
    
    def analyze(self) -> AlignmentStatistics:
        """Perform comprehensive analysis of all loaded reports.
        
        Returns:
            AlignmentStatistics with complete analysis
        """
        if not self.reports:
            return AlignmentStatistics()
        
        stats = AlignmentStatistics()
        stats.total_reports_analyzed = len(self.reports)
        stats.date_range_start = self.reports[0][1].generated_at
        stats.date_range_end = self.reports[-1][1].generated_at
        
        # Build timeline
        for report_path, report in self.reports:
            point = TimeSeriesPoint(
                timestamp=report.generated_at,
                report_file=report_path.name,
                total_columns=report.statistics.total_columns,
                mapped_columns=report.statistics.mapped_columns,
                unmapped_columns=report.statistics.unmapped_columns,
                mapping_success_rate=report.statistics.mapping_success_rate,
                average_confidence=report.statistics.average_confidence,
                high_confidence_matches=report.statistics.high_confidence_matches,
                medium_confidence_matches=report.statistics.medium_confidence_matches,
                low_confidence_matches=report.statistics.low_confidence_matches,
                very_low_confidence_matches=report.statistics.very_low_confidence_matches
            )
            stats.timeline.append(point)
        
        # Analyze column-level trends
        self._build_column_history()
        column_stats = self._analyze_columns()
        
        stats.unique_columns_seen = len(self.column_history)
        stats.most_problematic_columns = column_stats["problematic"][:10]
        stats.most_improved_columns = column_stats["improved"][:10]
        stats.never_mapped_columns = column_stats["never_mapped"]
        
        # Calculate overall metrics
        if stats.timeline:
            total_success = sum(p.mapping_success_rate for p in stats.timeline)
            total_confidence = sum(p.average_confidence for p in stats.timeline)
            stats.overall_success_rate = total_success / len(stats.timeline)
            stats.overall_avg_confidence = total_confidence / len(stats.timeline)
        
        # Trend analysis
        if len(stats.timeline) >= 2:
            stats.trend_analysis = self._analyze_trend(stats.timeline)
        
        # SKOS suggestions
        stats.total_skos_suggestions_generated = sum(
            len(report.skos_enrichment_suggestions)
            for _, report in self.reports
        )
        
        # Count SKOS suggestion types
        skos_types = Counter()
        for _, report in self.reports:
            for suggestion in report.skos_enrichment_suggestions:
                label_type = suggestion.suggested_label_type.split(':')[-1]
                skos_types[label_type] += 1
        stats.skos_suggestions_by_type = dict(skos_types)
        
        return stats
    
    def _build_column_history(self):
        """Build history of each column across all reports."""
        for report_path, report in self.reports:
            # Track unmapped columns
            for unmapped in report.unmapped_columns:
                self.column_history[unmapped.column_name].append({
                    'timestamp': report.generated_at,
                    'status': 'unmapped',
                    'confidence': 0.0,
                    'report': report_path.name
                })
            
            # Track weak matches
            for weak in report.weak_matches:
                self.column_history[weak.column_name].append({
                    'timestamp': report.generated_at,
                    'status': 'weak',
                    'confidence': weak.confidence_score,
                    'match_type': weak.match_type.value,
                    'report': report_path.name
                })
    
    def _analyze_columns(self) -> Dict[str, List[ColumnStats]]:
        """Analyze column-level statistics.
        
        Returns:
            Dictionary with 'problematic', 'improved', and 'never_mapped' lists
        """
        column_stats_list = []
        never_mapped = []
        
        for col_name, history in self.column_history.items():
            stats = ColumnStats(column_name=col_name)
            stats.total_appearances = len(history)
            stats.times_unmapped = sum(1 for h in history if h['status'] == 'unmapped')
            stats.times_mapped = stats.total_appearances - stats.times_unmapped
            
            if stats.total_appearances > 0:
                stats.mapping_success_rate = stats.times_mapped / stats.total_appearances
            
            confidences = [h['confidence'] for h in history if 'confidence' in h]
            if confidences:
                stats.avg_confidence = sum(confidences) / len(confidences)
            
            # Match types
            match_types = [h['match_type'] for h in history if 'match_type' in h]
            stats.match_types = dict(Counter(match_types))
            
            stats.last_seen = history[-1]['timestamp']
            
            # Determine trend
            if len(history) >= 2:
                recent_mapped = sum(1 for h in history[-3:] if h['status'] != 'unmapped')
                early_mapped = sum(1 for h in history[:3] if h['status'] != 'unmapped')
                recent_rate = recent_mapped / min(3, len(history[-3:]))
                early_rate = early_mapped / min(3, len(history[:3]))
                
                if recent_rate > early_rate + 0.2:
                    stats.improvement_trend = "improving"
                elif recent_rate < early_rate - 0.2:
                    stats.improvement_trend = "declining"
                else:
                    stats.improvement_trend = "stable"
            
            if stats.times_mapped == 0:
                never_mapped.append(col_name)
            
            column_stats_list.append(stats)
        
        # Sort by problematic (low success rate, high appearances)
        problematic = sorted(
            [s for s in column_stats_list if s.mapping_success_rate < 0.5],
            key=lambda s: (s.mapping_success_rate, -s.total_appearances)
        )
        
        # Sort by improvement
        improved = sorted(
            [s for s in column_stats_list if s.improvement_trend == "improving"],
            key=lambda s: (-s.mapping_success_rate, -s.total_appearances)
        )
        
        return {
            "problematic": problematic,
            "improved": improved,
            "never_mapped": never_mapped
        }
    
    def _analyze_trend(self, timeline: List[TimeSeriesPoint]) -> TrendAnalysis:
        """Analyze overall trend from timeline data.
        
        Args:
            timeline: List of time series points
            
        Returns:
            TrendAnalysis object
        """
        initial = timeline[0]
        current = timeline[-1]
        
        success_rate_change = current.mapping_success_rate - initial.mapping_success_rate
        confidence_change = current.average_confidence - initial.average_confidence
        
        # Combined improvement metric (weighted average)
        total_improvement = (success_rate_change * 0.6) + (confidence_change * 0.4)
        
        if total_improvement > 0.05:
            overall_trend = "improving"
        elif total_improvement < -0.05:
            overall_trend = "declining"
        else:
            overall_trend = "stable"
        
        return TrendAnalysis(
            overall_trend=overall_trend,
            success_rate_change=success_rate_change,
            confidence_change=confidence_change,
            initial_success_rate=initial.mapping_success_rate,
            current_success_rate=current.mapping_success_rate,
            initial_avg_confidence=initial.average_confidence,
            current_avg_confidence=current.average_confidence,
            total_improvement=total_improvement
        )
    
    def generate_summary_report(self, stats: AlignmentStatistics) -> str:
        """Generate a human-readable summary report.
        
        Args:
            stats: Analyzed statistics
            
        Returns:
            Formatted report string
        """
        lines = []
        lines.append("=" * 70)
        lines.append("SEMANTIC ALIGNMENT STATISTICS REPORT")
        lines.append("=" * 70)
        lines.append("")
        
        # Overview
        lines.append("OVERVIEW")
        lines.append("-" * 70)
        lines.append(f"Total Reports Analyzed: {stats.total_reports_analyzed}")
        if stats.date_range_start and stats.date_range_end:
            lines.append(f"Date Range: {stats.date_range_start.strftime('%Y-%m-%d')} → {stats.date_range_end.strftime('%Y-%m-%d')}")
        lines.append(f"Unique Columns Tracked: {stats.unique_columns_seen}")
        lines.append(f"Overall Success Rate: {stats.overall_success_rate:.1%}")
        lines.append(f"Overall Avg Confidence: {stats.overall_avg_confidence:.2f}")
        lines.append("")
        
        # Trend Analysis
        if stats.trend_analysis:
            trend = stats.trend_analysis
            lines.append("TREND ANALYSIS")
            lines.append("-" * 70)
            
            trend_indicator = {
                "improving": "📈 IMPROVING",
                "stable": "➡️  STABLE",
                "declining": "📉 DECLINING"
            }.get(trend.overall_trend, trend.overall_trend.upper())
            
            lines.append(f"Overall Trend: {trend_indicator}")
            lines.append(f"Success Rate: {trend.initial_success_rate:.1%} → {trend.current_success_rate:.1%} ({trend.success_rate_change:+.1%})")
            lines.append(f"Avg Confidence: {trend.initial_avg_confidence:.2f} → {trend.current_avg_confidence:.2f} ({trend.confidence_change:+.2f})")
            lines.append(f"Total Improvement Score: {trend.total_improvement:+.2f}")
            lines.append("")
        
        # Most Problematic Columns
        if stats.most_problematic_columns:
            lines.append("MOST PROBLEMATIC COLUMNS")
            lines.append("-" * 70)
            for i, col in enumerate(stats.most_problematic_columns[:5], 1):
                lines.append(f"{i}. {col.column_name}")
                lines.append(f"   Success Rate: {col.mapping_success_rate:.1%} ({col.times_mapped}/{col.total_appearances} mapped)")
                lines.append(f"   Avg Confidence: {col.avg_confidence:.2f}")
                if col.improvement_trend:
                    lines.append(f"   Trend: {col.improvement_trend}")
            lines.append("")
        
        # Most Improved Columns
        if stats.most_improved_columns:
            lines.append("MOST IMPROVED COLUMNS")
            lines.append("-" * 70)
            for i, col in enumerate(stats.most_improved_columns[:5], 1):
                lines.append(f"{i}. {col.column_name}")
                lines.append(f"   Current Success Rate: {col.mapping_success_rate:.1%}")
                lines.append(f"   Appearances: {col.total_appearances}")
            lines.append("")
        
        # Never Mapped
        if stats.never_mapped_columns:
            lines.append(f"NEVER MAPPED COLUMNS ({len(stats.never_mapped_columns)})")
            lines.append("-" * 70)
            for col in stats.never_mapped_columns[:10]:
                lines.append(f"  • {col}")
            if len(stats.never_mapped_columns) > 10:
                lines.append(f"  ... and {len(stats.never_mapped_columns) - 10} more")
            lines.append("")
        
        # SKOS Enrichment
        lines.append("SKOS ENRICHMENT IMPACT")
        lines.append("-" * 70)
        lines.append(f"Total Suggestions Generated: {stats.total_skos_suggestions_generated}")
        if stats.skos_suggestions_by_type:
            lines.append("Suggestions by Type:")
            for label_type, count in sorted(stats.skos_suggestions_by_type.items()):
                lines.append(f"  • {label_type}: {count}")
        lines.append("")
        
        lines.append("=" * 70)
        
        return "\n".join(lines)
    
    def export_to_json(self, stats: AlignmentStatistics, output_path: Path):
        """Export statistics to JSON file.
        
        Args:
            stats: Analyzed statistics to export
            output_path: Path for output JSON file
        """
        with open(output_path, 'w') as f:
            json.dump(stats.model_dump(mode='json'), f, indent=2, default=str)
