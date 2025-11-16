"""Conversion router - handles RDF conversion."""
from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from pathlib import Path
import logging

from ..services.rdfmap_service import RDFMapService
from ..config import settings
from ..worker import convert_to_rdf_task

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/{project_id}")
async def convert_to_rdf(
    project_id: str,
    output_format: str = Query("turtle", description="RDF format: turtle, json-ld, xml, nt"),
    validate: bool = Query(True, description="Validate output against ontology"),
    use_background: bool = Query(False, description="Run conversion as background job"),
):
    """
    Convert project data to RDF using the generated mappings.

    Supports synchronous (immediate) or asynchronous (background) conversion.
    """
    try:
        logger.info(f"Converting project {project_id} to RDF (format: {output_format})")

        # Check if mapping file exists
        mapping_file = Path(settings.DATA_DIR) / project_id / "mapping_config.yaml"
        if not mapping_file.exists():
            raise HTTPException(
                status_code=400,
                detail="No mapping configuration found. Generate mappings first."
            )

        if use_background:
            # Queue background task
            task = convert_to_rdf_task.delay(
                project_id=str(project_id),
                mapping_file_path=str(mapping_file),
                output_format=output_format,
                validate=validate,
            )
            return {
                "status": "queued",
                "project_id": project_id,
                "task_id": task.id,
                "message": "Conversion queued as background job",
            }
        else:
            # Run synchronously
            service = RDFMapService(
                uploads_dir=settings.UPLOAD_DIR,
                data_dir=settings.DATA_DIR,
            )

            result = service.convert_to_rdf(
                project_id=project_id,
                mapping_file_path=str(mapping_file),
                output_format=output_format,
                validate=validate,
            )

            return {
                "status": "success",
                "project_id": project_id,
                **result,
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error converting to RDF: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/job/{task_id}")
async def get_job_status(task_id: str):
    """
    Get the status and (if available) the result of a background conversion job.
    """
    try:
        from celery.result import AsyncResult
        res = AsyncResult(task_id)
        status = res.status
        response = {"task_id": task_id, "status": status}
        if res.successful():
            response["result"] = res.result
        elif res.failed():
            response["error"] = str(res.result)
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{project_id}/download")
async def download_rdf(project_id: str):
    """Download the generated RDF file (turtle by default)."""
    project_dir = Path(settings.DATA_DIR) / project_id
    # Try known extensions in preference order
    for ext in ["ttl", "jsonld", "rdf", "nt", "n3"]:
        candidate = project_dir / f"output.{ext}"
        if candidate.exists():
            from fastapi.responses import FileResponse
            media_types = {
                "ttl": "text/turtle",
                "jsonld": "application/ld+json",
                "rdf": "application/rdf+xml",
                "nt": "application/n-triples",
                "n3": "text/n3",
            }
            return FileResponse(str(candidate), media_type=media_types.get(ext, "text/plain"), filename=f"rdfmap-output.{ext}")
    raise HTTPException(status_code=404, detail="RDF output file not found. Run conversion first.")
