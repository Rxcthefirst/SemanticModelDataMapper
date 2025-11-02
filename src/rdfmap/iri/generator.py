"""IRI generation and templating engine."""

import re
from string import Formatter
from typing import Any, Dict, Set
from urllib.parse import quote


class IRITemplate:
    """IRI template handler with variable substitution."""

    def __init__(self, template: str, base_iri: str = ""):
        """Initialize IRI template.
        
        Args:
            template: Template string with {variable} placeholders
            base_iri: Base IRI to substitute for {base_iri} variable
        """
        self.template = template
        self.base_iri = base_iri
        self._variables = self._extract_variables()

    def _extract_variables(self) -> Set[str]:
        """Extract variable names from template."""
        return {
            field_name
            for _, field_name, _, _ in Formatter().parse(self.template)
            if field_name
        }

    @property
    def variables(self) -> Set[str]:
        """Get set of variable names in template."""
        return self._variables.copy()

    def render(self, context: Dict[str, Any]) -> str:
        """Render IRI template with provided context.
        
        Args:
            context: Dictionary of variable values
            
        Returns:
            Rendered IRI string
            
        Raises:
            ValueError: If required variables are missing
        """
        # Add base_iri to context
        full_context = {"base_iri": self.base_iri, **context}
        
        # Check for missing variables
        missing = self._variables - set(full_context.keys())
        if missing:
            raise ValueError(f"Missing required variables for IRI template: {missing}")
        
        # Render template
        try:
            iri = self.template.format(**full_context)
        except KeyError as e:
            raise ValueError(f"Variable not found in context: {e}")
        
        # URL encode special characters in path components
        # but preserve the IRI structure (scheme, slashes, etc.)
        iri = self._encode_iri(iri)
        
        return iri

    def _encode_iri(self, iri: str) -> str:
        """Encode IRI components while preserving structure.
        
        Args:
            iri: Raw IRI string
            
        Returns:
            Encoded IRI
        """
        # Split into scheme and rest
        if "://" in iri:
            scheme, rest = iri.split("://", 1)
            
            # Split rest into authority and path
            if "/" in rest:
                authority, path = rest.split("/", 1)
                
                # Encode path components but not slashes
                path_parts = path.split("/")
                encoded_parts = [quote(part, safe="") for part in path_parts]
                encoded_path = "/".join(encoded_parts)
                
                return f"{scheme}://{authority}/{encoded_path}"
            else:
                # No path, just authority
                return f"{scheme}://{rest}"
        
        # No scheme, encode as-is (shouldn't happen for valid IRIs)
        return quote(iri, safe=":/#")


def validate_iri(iri: str) -> bool:
    """Validate that a string is a valid IRI.
    
    Args:
        iri: IRI string to validate
        
    Returns:
        True if valid IRI
    """
    # Basic IRI validation - must have scheme and something after it
    # Supports both hierarchical (http://, ftp://) and non-hierarchical (urn:, mailto:) schemes
    iri_pattern = re.compile(
        r"^[a-zA-Z][a-zA-Z0-9+.-]*:"  # Scheme
        r"(//)?"  # Optional authority separator for hierarchical IRIs
        r"[^\s]+"  # Path/fragment/scheme-specific part
    )
    return bool(iri_pattern.match(iri))


def curie_to_iri(curie: str, namespaces: Dict[str, str]) -> str:
    """Convert CURIE to full IRI.
    
    Args:
        curie: Compact URI (e.g., ex:MortgageLoan)
        namespaces: Namespace prefix to IRI mappings
        
    Returns:
        Full IRI
        
    Raises:
        ValueError: If prefix not found in namespaces
    """
    if ":" not in curie:
        raise ValueError(f"Invalid CURIE format (missing colon): {curie}")
    
    prefix, local_part = curie.split(":", 1)
    
    if prefix not in namespaces:
        raise ValueError(f"Unknown namespace prefix: {prefix}")
    
    return namespaces[prefix] + local_part


def iri_to_curie(iri: str, namespaces: Dict[str, str]) -> str:
    """Convert IRI to CURIE if possible.
    
    Args:
        iri: Full IRI
        namespaces: Namespace prefix to IRI mappings
        
    Returns:
        CURIE if namespace matches, otherwise original IRI
    """
    for prefix, namespace in namespaces.items():
        if iri.startswith(namespace):
            local_part = iri[len(namespace):]
            return f"{prefix}:{local_part}"
    
    return iri
