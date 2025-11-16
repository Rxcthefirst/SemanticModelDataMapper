"""Ontology analyzer for extracting classes and properties."""

from typing import Dict, List, Optional
from rdflib import Graph, Namespace, RDF, RDFS, OWL
from rdflib.term import URIRef

# SKOS namespace
SKOS = Namespace("http://www.w3.org/2004/02/skos/core#")


class OntologyClass:
    """Represents a class from the ontology."""
    
    def __init__(
        self, 
        uri: URIRef, 
        label: Optional[str] = None, 
        comment: Optional[str] = None,
        pref_label: Optional[str] = None,
        alt_labels: Optional[List[str]] = None,
        hidden_labels: Optional[List[str]] = None
    ):
        self.uri = uri
        self.label = label
        self.comment = comment
        self.pref_label = pref_label  # SKOS preferred label
        self.alt_labels = alt_labels or []  # SKOS alternative labels
        self.hidden_labels = hidden_labels or []  # SKOS hidden labels
        self.properties: List['OntologyProperty'] = []
    
    def get_all_labels(self) -> List[str]:
        """Get all labels (preferred, rdfs, alternative) for matching."""
        labels = []
        if self.pref_label:
            labels.append(self.pref_label)
        if self.label:
            labels.append(self.label)
        labels.extend(self.alt_labels)
        # Note: hidden labels are not included in general matching
        return labels
    
    def __repr__(self):
        return f"OntologyClass({self.uri}, label={self.label})"


class OntologyProperty:
    """Represents a property from the ontology."""
    
    def __init__(
        self,
        uri: URIRef,
        label: Optional[str] = None,
        comment: Optional[str] = None,
        domain: Optional[URIRef] = None,
        range_type: Optional[URIRef] = None,
        is_object_property: bool = False,
        pref_label: Optional[str] = None,
        alt_labels: Optional[List[str]] = None,
        hidden_labels: Optional[List[str]] = None,
        broader: Optional[List[str]] = None,
        narrower: Optional[List[str]] = None,
        related: Optional[List[str]] = None,
        exact_matches: Optional[List[str]] = None,
        close_matches: Optional[List[str]] = None,
        definition: Optional[str] = None
    ):
        self.uri = uri
        self.label = label
        self.comment = comment
        self.domain = domain
        self.range_type = range_type
        self.is_object_property = is_object_property
        self.pref_label = pref_label  # SKOS preferred label
        self.alt_labels = alt_labels or []  # SKOS alternative labels
        self.hidden_labels = hidden_labels or []  # SKOS hidden labels
        self.broader = broader or []
        self.narrower = narrower or []
        self.related = related or []
        self.exact_matches = exact_matches or []
        self.close_matches = close_matches or []
        self.definition = definition

    def get_all_labels(self) -> List[str]:
        """Get all labels (preferred, rdfs, alternative, hidden) for matching."""
        labels = []
        if self.pref_label:
            labels.append(self.pref_label)
        if self.label:
            labels.append(self.label)
        labels.extend(self.alt_labels)
        labels.extend(self.hidden_labels)  # Include hidden labels for column matching
        if self.definition:
            labels.append(self.definition)
        return labels
    
    def __repr__(self):
        return f"OntologyProperty({self.uri}, domain={self.domain}, range={self.range_type})"


class OntologyAnalyzer:
    """Analyzes an ontology to extract classes and properties for mapping generation."""
    
    def __init__(self, ontology_file: str, imports: Optional[List[str]] = None):
        """
        Initialize the analyzer with an ontology file and optional imports.

        Args:
            ontology_file: Path to primary ontology file (any RDFLib-supported format)
            imports: Optional list of additional ontology files/URIs to import
        """
        self.graph = Graph()
        self.ontology_file = ontology_file
        self.imports = imports or []

        # Load primary ontology
        self.graph.parse(ontology_file)
        
        # Load imported ontologies
        for import_source in self.imports:
            try:
                self.graph.parse(import_source)
            except Exception as e:
                # Log warning but don't fail - some imports might be optional
                print(f"Warning: Failed to load imported ontology '{import_source}': {e}")

        self.classes: Dict[URIRef, OntologyClass] = {}
        self.properties: Dict[URIRef, OntologyProperty] = {}
        self.property_restrictions: Dict[str, List[Dict[str, any]]] = {}

        self._analyze()
    
    def _analyze(self):
        """Analyze the ontology to extract classes and properties."""
        self._extract_classes()
        self._extract_properties()
        self._link_properties_to_classes()
        self._extract_owl_restrictions()

    def _extract_classes(self):
        """Extract all OWL/RDFS classes from the ontology."""
        for cls_uri in self.graph.subjects(RDF.type, OWL.Class):
            label = self._get_label(cls_uri)
            comment = self._get_comment(cls_uri)
            pref_label = self._get_pref_label(cls_uri)
            alt_labels = self._get_alt_labels(cls_uri)
            hidden_labels = self._get_hidden_labels(cls_uri)
            self.classes[cls_uri] = OntologyClass(
                cls_uri, label, comment, pref_label, alt_labels, hidden_labels
            )
        
        # Also check for RDFS classes
        for cls_uri in self.graph.subjects(RDF.type, RDFS.Class):
            if cls_uri not in self.classes:
                label = self._get_label(cls_uri)
                comment = self._get_comment(cls_uri)
                pref_label = self._get_pref_label(cls_uri)
                alt_labels = self._get_alt_labels(cls_uri)
                hidden_labels = self._get_hidden_labels(cls_uri)
                self.classes[cls_uri] = OntologyClass(
                    cls_uri, label, comment, pref_label, alt_labels, hidden_labels
                )
    
    def _extract_properties(self):
        """Extract all properties (data and object) from the ontology."""
        # Object properties
        for prop_uri in self.graph.subjects(RDF.type, OWL.ObjectProperty):
            self._extract_property(prop_uri, is_object_property=True)
        
        # Data properties
        for prop_uri in self.graph.subjects(RDF.type, OWL.DatatypeProperty):
            self._extract_property(prop_uri, is_object_property=False)
        
        # RDF properties
        for prop_uri in self.graph.subjects(RDF.type, RDF.Property):
            if prop_uri not in self.properties:
                self._extract_property(prop_uri, is_object_property=False)
    
    def _extract_property(self, prop_uri: URIRef, is_object_property: bool):
        """Extract property details."""
        label = self._get_label(prop_uri)
        comment = self._get_comment(prop_uri)
        pref_label = self._get_pref_label(prop_uri)
        alt_labels = self._get_alt_labels(prop_uri)
        hidden_labels = self._get_hidden_labels(prop_uri)
        
        # Get domain
        domain = None
        for d in self.graph.objects(prop_uri, RDFS.domain):
            domain = d
            break  # Take first domain
        
        # Get range
        range_type = None
        for r in self.graph.objects(prop_uri, RDFS.range):
            range_type = r
            break  # Take first range
        
        broader = [str(b) for b in self.graph.objects(prop_uri, SKOS.broader)]
        narrower = [str(n) for n in self.graph.objects(prop_uri, SKOS.narrower)]
        related = [str(r) for r in self.graph.objects(prop_uri, SKOS.related)]
        exact_matches = [str(e) for e in self.graph.objects(prop_uri, SKOS.exactMatch)]
        close_matches = [str(c) for c in self.graph.objects(prop_uri, SKOS.closeMatch)]
        definition_vals = [str(d) for d in self.graph.objects(prop_uri, SKOS.definition)]
        definition = definition_vals[0] if definition_vals else None

        self.properties[prop_uri] = OntologyProperty(
            prop_uri,
            label,
            comment,
            domain,
            range_type,
            is_object_property,
            pref_label,
            alt_labels,
            hidden_labels,
            broader,
            narrower,
            related,
            exact_matches,
            close_matches,
            definition,
        )
    
    def _link_properties_to_classes(self):
        """Link properties to their domain classes."""
        for prop in self.properties.values():
            if prop.domain and prop.domain in self.classes:
                self.classes[prop.domain].properties.append(prop)
    
    def _get_label(self, uri: URIRef) -> Optional[str]:
        """Get rdfs:label for a URI."""
        for label in self.graph.objects(uri, RDFS.label):
            return str(label)
        return None
    
    def _get_comment(self, uri: URIRef) -> Optional[str]:
        """Get rdfs:comment for a URI."""
        for comment in self.graph.objects(uri, RDFS.comment):
            return str(comment)
        return None
    
    def _get_pref_label(self, uri: URIRef) -> Optional[str]:
        """Get SKOS preferred label for a URI."""
        for label in self.graph.objects(uri, SKOS.prefLabel):
            return str(label)
        return None
    
    def _get_alt_labels(self, uri: URIRef) -> List[str]:
        """Get all SKOS alternative labels for a URI."""
        return [str(label) for label in self.graph.objects(uri, SKOS.altLabel)]
    
    def _get_hidden_labels(self, uri: URIRef) -> List[str]:
        """Get all SKOS hidden labels for a URI."""
        return [str(label) for label in self.graph.objects(uri, SKOS.hiddenLabel)]
    
    def get_class_by_uri(self, uri: URIRef) -> Optional[OntologyClass]:
        """Get a class by its URI."""
        return self.classes.get(uri)
    
    def get_class_by_label(self, label: str) -> Optional[OntologyClass]:
        """Get a class by its label (case-insensitive)."""
        label_lower = label.lower()
        for cls in self.classes.values():
            if cls.label and cls.label.lower() == label_lower:
                return cls
        return None
    
    def get_properties_for_class(self, class_uri: URIRef) -> List[OntologyProperty]:
        """Get all properties with the given class as domain."""
        cls = self.classes.get(class_uri)
        return cls.properties if cls else []
    
    def get_datatype_properties(self, class_uri: Optional[URIRef] = None) -> List[OntologyProperty]:
        """Get all datatype properties, optionally filtered by class domain."""
        props = [p for p in self.properties.values() if not p.is_object_property]
        if class_uri:
            props = [p for p in props if p.domain == class_uri]
        return props
    
    def get_object_properties(self, class_uri: Optional[URIRef] = None) -> List[OntologyProperty]:
        """Get all object properties, optionally filtered by class domain."""
        props = [p for p in self.properties.values() if p.is_object_property]
        if class_uri:
            props = [p for p in props if p.domain == class_uri]
        return props
    
    def suggest_class_for_name(self, name: str) -> List[OntologyClass]:
        """
        Suggest classes based on a name (e.g., from a sheet name or column pattern).
        
        Returns classes whose labels or URIs contain the given name (case-insensitive).
        """
        name_lower = name.lower()
        suggestions = []
        
        for cls in self.classes.values():
            # Check label
            if cls.label and name_lower in cls.label.lower():
                suggestions.append(cls)
                continue
            
            # Check URI local name
            local_name = str(cls.uri).split("#")[-1].split("/")[-1]
            if name_lower in local_name.lower():
                suggestions.append(cls)
        
        return suggestions
    
    def get_namespaces(self) -> Dict[str, str]:
        """Extract namespace prefixes and URIs from the ontology."""
        namespaces = {}
        for prefix, namespace in self.graph.namespaces():
            if prefix:  # Skip default namespace
                namespaces[prefix] = str(namespace)
        return namespaces

    def _extract_owl_restrictions(self):
        """Parse OWL restrictions (onProperty, some/allValuesFrom, cardinality) and store them per property."""
        from rdflib import RDF, OWL
        for cls_uri in self.classes.keys():
            for restriction in self.graph.objects(cls_uri, RDFS.subClassOf):
                # Accept both BNodes and URIRefs typed as OWL.Restriction
                if (restriction, RDF.type, OWL.Restriction) in self.graph:
                    prop = None
                    range_target = None
                    all_values = None
                    some_values = None
                    cardinality = None
                    min_card = None
                    max_card = None
                    for p in self.graph.objects(restriction, OWL.onProperty):
                        prop = str(p)
                    for v in self.graph.objects(restriction, OWL.someValuesFrom):
                        some_values = str(v)
                    for v in self.graph.objects(restriction, OWL.allValuesFrom):
                        all_values = str(v)
                    for v in self.graph.objects(restriction, OWL.hasValue):
                        range_target = str(v)
                    for v in self.graph.objects(restriction, OWL.cardinality):
                        try: cardinality = int(str(v))
                        except: cardinality = None
                    for v in self.graph.objects(restriction, OWL.minCardinality):
                        try: min_card = int(str(v))
                        except: min_card = None
                    for v in self.graph.objects(restriction, OWL.maxCardinality):
                        try: max_card = int(str(v))
                        except: max_card = None
                    if prop:
                        self.property_restrictions.setdefault(prop, []).append({
                            'class': str(cls_uri),
                            'someValuesFrom': some_values,
                            'allValuesFrom': all_values,
                            'hasValue': range_target,
                            'cardinality': cardinality,
                            'minCardinality': min_card,
                            'maxCardinality': max_card
                        })
