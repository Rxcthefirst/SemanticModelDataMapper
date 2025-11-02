"""SKOS coverage validator and analyzer.

This module analyzes ontologies to check SKOS label coverage,
identify properties missing labels, and suggest improvements for
better semantic alignment.
"""

from typing import Dict, List, Optional, Set, Tuple
from collections import defaultdict
from rdflib import Graph, Namespace, URIRef
from rdflib.namespace import RDF, RDFS, OWL, SKOS
from pydantic import BaseModel, Field


class PropertyCoverage(BaseModel):
    """SKOS label coverage for a single property."""
    property_uri: str
    property_label: Optional[str] = None
    has_pref_label: bool = False
    has_alt_labels: bool = False
    has_hidden_labels: bool = False
    pref_labels: List[str] = Field(default_factory=list)
    alt_labels: List[str] = Field(default_factory=list)
    hidden_labels: List[str] = Field(default_factory=list)
    total_skos_labels: int = 0
    coverage_score: float = 0.0  # 0.0 to 1.0


class ClassCoverage(BaseModel):
    """SKOS coverage for a class and its properties."""
    class_uri: str
    class_label: Optional[str] = None
    total_properties: int = 0
    properties_with_skos: int = 0
    properties_without_skos: int = 0
    coverage_percentage: float = 0.0
    properties: List[PropertyCoverage] = Field(default_factory=list)


class SKOSCoverageReport(BaseModel):
    """Complete SKOS coverage analysis for an ontology."""
    ontology_file: str
    total_classes: int = 0
    total_properties: int = 0
    properties_with_skos: int = 0
    properties_without_skos: int = 0
    overall_coverage_percentage: float = 0.0
    
    # Breakdown by class
    class_coverage: List[ClassCoverage] = Field(default_factory=list)
    
    # Properties missing labels
    properties_missing_all_labels: List[str] = Field(default_factory=list)
    properties_missing_pref_label: List[str] = Field(default_factory=list)
    properties_missing_hidden_labels: List[str] = Field(default_factory=list)
    
    # Statistics
    avg_labels_per_property: float = 0.0
    properties_with_multiple_labels: int = 0
    
    # Recommendations
    recommendations: List[str] = Field(default_factory=list)


class SKOSCoverageValidator:
    """Validates and analyzes SKOS label coverage in ontologies."""
    
    def __init__(self, ontology_path: str):
        """Initialize the validator.
        
        Args:
            ontology_path: Path to the ontology file
        """
        self.ontology_path = ontology_path
        self.graph = Graph()
        self.graph.parse(ontology_path)
        
    def analyze(self, min_coverage: float = 0.7) -> SKOSCoverageReport:
        """Perform comprehensive SKOS coverage analysis.
        
        Args:
            min_coverage: Minimum acceptable coverage percentage (0.0-1.0)
            
        Returns:
            SKOSCoverageReport with complete analysis
        """
        report = SKOSCoverageReport(ontology_file=self.ontology_path)
        
        # Get all classes
        classes = self._get_all_classes()
        report.total_classes = len(classes)
        
        # Analyze each class
        all_properties: Set[URIRef] = set()
        
        for class_uri in classes:
            class_cov = self._analyze_class(class_uri)
            report.class_coverage.append(class_cov)
            all_properties.update(prop.property_uri for prop in class_cov.properties)
        
        # If no classes or properties found via domain, analyze all properties
        if not all_properties:
            all_properties = self._get_all_properties()
        
        report.total_properties = len(all_properties)
        
        # Analyze property-level coverage
        property_coverages = []
        for prop_uri in all_properties:
            prop_cov = self._analyze_property(str(prop_uri))
            property_coverages.append(prop_cov)
            
            if prop_cov.total_skos_labels > 0:
                report.properties_with_skos += 1
            else:
                report.properties_without_skos += 1
                report.properties_missing_all_labels.append(prop_cov.property_uri)
            
            if not prop_cov.has_pref_label:
                report.properties_missing_pref_label.append(prop_cov.property_uri)
            
            if not prop_cov.has_hidden_labels:
                report.properties_missing_hidden_labels.append(prop_cov.property_uri)
            
            if prop_cov.total_skos_labels > 1:
                report.properties_with_multiple_labels += 1
        
        # Calculate overall coverage
        if report.total_properties > 0:
            report.overall_coverage_percentage = report.properties_with_skos / report.total_properties
            
            total_labels = sum(p.total_skos_labels for p in property_coverages)
            report.avg_labels_per_property = total_labels / report.total_properties
        
        # Generate recommendations
        report.recommendations = self._generate_recommendations(report, min_coverage)
        
        return report
    
    def _get_all_classes(self) -> List[URIRef]:
        """Get all OWL/RDFS classes in the ontology.
        
        Returns:
            List of class URIs
        """
        classes = set()
        
        # OWL classes
        for s in self.graph.subjects(RDF.type, OWL.Class):
            classes.add(s)
        
        # RDFS classes
        for s in self.graph.subjects(RDF.type, RDFS.Class):
            classes.add(s)
        
        return list(classes)
    
    def _get_all_properties(self) -> Set[URIRef]:
        """Get all properties in the ontology.
        
        Returns:
            Set of property URIs
        """
        properties = set()
        
        # OWL properties
        for s in self.graph.subjects(RDF.type, OWL.ObjectProperty):
            properties.add(s)
        for s in self.graph.subjects(RDF.type, OWL.DatatypeProperty):
            properties.add(s)
        for s in self.graph.subjects(RDF.type, RDF.Property):
            properties.add(s)
        
        return properties
    
    def _analyze_class(self, class_uri: URIRef) -> ClassCoverage:
        """Analyze SKOS coverage for a specific class.
        
        Args:
            class_uri: URI of the class
            
        Returns:
            ClassCoverage object
        """
        coverage = ClassCoverage(class_uri=str(class_uri))
        
        # Get class label
        label = self.graph.value(class_uri, RDFS.label)
        if label:
            coverage.class_label = str(label)
        
        # Get properties with this class as domain
        properties = list(self.graph.subjects(RDFS.domain, class_uri))
        coverage.total_properties = len(properties)
        
        for prop_uri in properties:
            prop_cov = self._analyze_property(str(prop_uri))
            coverage.properties.append(prop_cov)
            
            if prop_cov.total_skos_labels > 0:
                coverage.properties_with_skos += 1
        
        coverage.properties_without_skos = (
            coverage.total_properties - coverage.properties_with_skos
        )
        
        if coverage.total_properties > 0:
            coverage.coverage_percentage = (
                coverage.properties_with_skos / coverage.total_properties
            )
        
        return coverage
    
    def _analyze_property(self, property_uri: str) -> PropertyCoverage:
        """Analyze SKOS coverage for a specific property.
        
        Args:
            property_uri: URI of the property
            
        Returns:
            PropertyCoverage object
        """
        prop_uri_ref = URIRef(property_uri)
        coverage = PropertyCoverage(property_uri=property_uri)
        
        # Get rdfs:label
        label = self.graph.value(prop_uri_ref, RDFS.label)
        if label:
            coverage.property_label = str(label)
        
        # Check SKOS labels
        pref_labels = list(self.graph.objects(prop_uri_ref, SKOS.prefLabel))
        coverage.pref_labels = [str(l) for l in pref_labels]
        coverage.has_pref_label = len(pref_labels) > 0
        
        alt_labels = list(self.graph.objects(prop_uri_ref, SKOS.altLabel))
        coverage.alt_labels = [str(l) for l in alt_labels]
        coverage.has_alt_labels = len(alt_labels) > 0
        
        hidden_labels = list(self.graph.objects(prop_uri_ref, SKOS.hiddenLabel))
        coverage.hidden_labels = [str(l) for l in hidden_labels]
        coverage.has_hidden_labels = len(hidden_labels) > 0
        
        coverage.total_skos_labels = (
            len(pref_labels) + len(alt_labels) + len(hidden_labels)
        )
        
        # Calculate coverage score (weighted)
        score = 0.0
        if coverage.has_pref_label:
            score += 0.5  # prefLabel is most important
        if coverage.has_alt_labels:
            score += 0.25
        if coverage.has_hidden_labels:
            score += 0.25
        coverage.coverage_score = score
        
        return coverage
    
    def _generate_recommendations(
        self, 
        report: SKOSCoverageReport, 
        min_coverage: float
    ) -> List[str]:
        """Generate recommendations based on coverage analysis.
        
        Args:
            report: Coverage report
            min_coverage: Minimum acceptable coverage
            
        Returns:
            List of recommendation strings
        """
        recommendations = []
        
        if report.overall_coverage_percentage < min_coverage:
            gap = min_coverage - report.overall_coverage_percentage
            recommendations.append(
                f"Overall coverage ({report.overall_coverage_percentage:.1%}) is below target "
                f"({min_coverage:.1%}). Need to improve {gap:.1%} to reach goal."
            )
        
        if report.properties_missing_all_labels:
            recommendations.append(
                f"{len(report.properties_missing_all_labels)} properties have no SKOS labels. "
                "Consider adding at least skos:prefLabel for each."
            )
        
        if report.properties_missing_hidden_labels:
            hidden_pct = len(report.properties_missing_hidden_labels) / report.total_properties
            if hidden_pct > 0.5:
                recommendations.append(
                    f"{len(report.properties_missing_hidden_labels)} properties lack skos:hiddenLabel. "
                    "Hidden labels improve matching with abbreviated or legacy column names."
                )
        
        if report.avg_labels_per_property < 2.0:
            recommendations.append(
                f"Average of {report.avg_labels_per_property:.1f} labels per property. "
                "Consider adding alternative and hidden labels to improve matching flexibility."
            )
        
        # Class-specific recommendations
        low_coverage_classes = [
            c for c in report.class_coverage 
            if c.coverage_percentage < min_coverage and c.total_properties > 0
        ]
        
        if low_coverage_classes:
            recommendations.append(
                f"{len(low_coverage_classes)} classes have coverage below {min_coverage:.1%}:"
            )
            for cls in low_coverage_classes[:3]:  # Show top 3
                recommendations.append(
                    f"  • {cls.class_label or cls.class_uri}: "
                    f"{cls.coverage_percentage:.1%} "
                    f"({cls.properties_without_skos} properties need labels)"
                )
        
        if not recommendations:
            recommendations.append(
                f"✓ Excellent SKOS coverage! {report.overall_coverage_percentage:.1%} of properties have labels."
            )
        
        return recommendations
