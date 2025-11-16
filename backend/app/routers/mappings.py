"""Mappings router - handles mapping generation and management."""
from fastapi import APIRouter, HTTPException, Query, Response
from typing import Optional
import logging

from ..services.rdfmap_service import RDFMapService
from ..config import settings

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/{project_id}/generate")
async def generate_mappings(
    project_id: str,
    target_class: Optional[str] = Query(None, description="Target ontology class URI"),
    base_iri: str = Query("http://example.org/", description="Base IRI for resources"),
    use_semantic: bool = Query(True, description="Use semantic matching"),
    min_confidence: float = Query(0.5, description="Minimum confidence threshold"),
):
    """
    Generate automatic mappings between data and ontology.

    This endpoint analyzes the uploaded data and ontology files,
    then uses AI-powered matching to suggest column-to-property mappings.
    """
    try:
        logger.info(f"Generating mappings for project {project_id}")

        # Get project files from projects router storage
        # For now, we'll construct paths - in production, query from database
        from pathlib import Path
        project_dir = Path(settings.UPLOAD_DIR) / project_id

        # Find data and ontology files
        data_files = list(project_dir.glob("data.*"))
        ontology_files = list(project_dir.glob("ontology.*"))

        if not data_files:
            raise HTTPException(status_code=400, detail="No data file found for project")
        if not ontology_files:
            raise HTTPException(status_code=400, detail="No ontology file found for project")

        data_file = str(data_files[0])
        ontology_file = str(ontology_files[0])

        # Generate mappings
        service = RDFMapService(
            uploads_dir=settings.UPLOAD_DIR,
            data_dir=settings.DATA_DIR,
        )

        result = service.generate_mappings(
            project_id=project_id,
            ontology_file_path=ontology_file,
            data_file_path=data_file,
            target_class=target_class,
            base_iri=base_iri,
            use_semantic=use_semantic,
            min_confidence=min_confidence,
        )

        sheet_columns = 0
        if isinstance(result.get("mapping_config"), dict):
            sheets = result["mapping_config"].get("sheets", [])
            if sheets:
                sheet_columns = len(sheets[0].get("columns", {}))
        return {
            "status": "success",
            "project_id": project_id,
            "mapping_file": result["mapping_file"],
            "alignment_report": result["alignment_report"],
            "mapping_summary": result.get("mapping_summary"),
            "formatted_yaml": result.get("formatted_yaml"),
            "mapping_preview": {
                "base_iri": result["mapping_config"].get("defaults", {}).get("base_iri"),
                "target_class": result["mapping_config"].get("sheets", [{}])[0].get("row_resource", {}).get("class"),
                "column_count": sheet_columns,
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating mappings: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{project_id}")
async def get_mappings(project_id: str, raw: bool = False):
    """
    Get the current mapping configuration for a project.
    """
    try:
        from pathlib import Path
        import yaml
        mapping_file = Path(settings.DATA_DIR) / project_id / "mapping_config.yaml"
        if not mapping_file.exists():
            raise HTTPException(status_code=404, detail="No mappings found for project")
        if raw:
            return Response(content=mapping_file.read_text(), media_type="text/yaml")
        with open(mapping_file, 'r') as f:
            mapping_config = yaml.safe_load(f)
        return {
            "status": "success",
            "project_id": project_id,
            "mapping_config": mapping_config,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving mappings: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
