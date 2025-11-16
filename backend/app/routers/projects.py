"""Projects API router."""

from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from typing import List, Optional
from pathlib import Path
import shutil
import uuid
import logging

from ..schemas.project import ProjectCreate, ProjectResponse, ProjectList
from ..config import settings

router = APIRouter()
logger = logging.getLogger(__name__)

# Temporary in-memory storage (replace with database)
projects_db = {}


@router.post("/", response_model=ProjectResponse)
async def create_project(project: ProjectCreate):
    """Create a new project."""
    project_id = str(uuid.uuid4())

    project_data = {
        "id": project_id,
        "name": project.name,
        "description": project.description,
        "status": "created",
        "data_file": None,
        "ontology_file": None,
        "config": {},
    }

    projects_db[project_id] = project_data

    # Create project directory
    project_dir = Path(settings.UPLOAD_DIR) / project_id
    project_dir.mkdir(parents=True, exist_ok=True)

    return project_data


@router.get("/", response_model=List[ProjectResponse])
async def list_projects(skip: int = 0, limit: int = 100):
    """List all projects."""
    projects = list(projects_db.values())
    return projects[skip : skip + limit]


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(project_id: str):
    """Get a specific project."""
    if project_id not in projects_db:
        raise HTTPException(status_code=404, detail="Project not found")

    return projects_db[project_id]


@router.delete("/{project_id}")
async def delete_project(project_id: str):
    """Delete a project."""
    if project_id not in projects_db:
        raise HTTPException(status_code=404, detail="Project not found")

    # Delete project directory
    project_dir = Path(settings.UPLOAD_DIR) / project_id
    if project_dir.exists():
        shutil.rmtree(project_dir)

    del projects_db[project_id]

    return {"message": "Project deleted successfully"}


@router.post("/{project_id}/upload-data")
async def upload_data_file(
    project_id: str,
    file: UploadFile = File(...),
):
    """Upload data file (CSV, Excel, JSON, XML)."""
    if project_id not in projects_db:
        raise HTTPException(status_code=404, detail="Project not found")

    # Validate file type
    allowed_extensions = [".csv", ".xlsx", ".json", ".xml"]
    file_ext = Path(file.filename).suffix.lower()

    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed: {', '.join(allowed_extensions)}"
        )

    # Save file
    project_dir = Path(settings.UPLOAD_DIR) / project_id
    file_path = project_dir / f"data{file_ext}"

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Update project
    projects_db[project_id]["data_file"] = str(file_path)
    projects_db[project_id]["status"] = "data_uploaded"

    return {
        "message": "Data file uploaded successfully",
        "file_path": str(file_path),
        "file_size": file_path.stat().st_size,
    }


@router.post("/{project_id}/upload-ontology")
async def upload_ontology_file(
    project_id: str,
    file: UploadFile = File(...),
):
    """Upload ontology file (TTL, OWL, RDF/XML)."""
    if project_id not in projects_db:
        raise HTTPException(status_code=404, detail="Project not found")

    # Validate file type
    allowed_extensions = [".ttl", ".owl", ".rdf"]
    file_ext = Path(file.filename).suffix.lower()

    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed: {', '.join(allowed_extensions)}"
        )

    # Save file
    project_dir = Path(settings.UPLOAD_DIR) / project_id
    file_path = project_dir / f"ontology{file_ext}"

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Update project
    projects_db[project_id]["ontology_file"] = str(file_path)
    projects_db[project_id]["status"] = "ontology_uploaded"

    return {
        "message": "Ontology file uploaded successfully",
        "file_path": str(file_path),
        "file_size": file_path.stat().st_size,
    }


@router.get("/{project_id}/data-preview")
async def get_data_preview(project_id: str, limit: int = 10):
    """Get preview of data file (first N rows) with analysis."""
    if project_id not in projects_db:
        raise HTTPException(status_code=404, detail="Project not found")

    project = projects_db[project_id]

    if not project.get("data_file"):
        raise HTTPException(status_code=400, detail="No data file uploaded")

    try:
        from ..services.rdfmap_service import RDFMapService
        from pathlib import Path

        # Ensure data_file is a string path
        data_file = str(project["data_file"])

        service = RDFMapService(uploads_dir=settings.UPLOAD_DIR, data_dir=settings.DATA_DIR)
        analysis = service.analyze_data_file(data_file)

        # Get first few rows using parser
        from rdfmap.parsers.data_source import create_parser
        parser = create_parser(data_file)
        dataframes = list(parser.parse())

        if dataframes:
            df = dataframes[0]
            # Convert first N rows to dict
            preview_df = df.head(limit)
            rows = preview_df.to_dicts()
        else:
            rows = []

        return {
            **analysis,
            "rows": rows,
            "showing": len(rows),
        }
    except Exception as e:
        logger.error(f"Error in data preview: {e}", exc_info=True)
        # Return error in response instead of raising
        return {
            "error": str(e),
            "columns": [],
            "rows": [],
            "total_rows": 0,
            "showing": 0,
        }


@router.get("/{project_id}/ontology-analysis")
async def get_ontology_analysis(project_id: str):
    """Get analysis of the uploaded ontology."""
    if project_id not in projects_db:
        raise HTTPException(status_code=404, detail="Project not found")

    project = projects_db[project_id]

    if not project.get("ontology_file"):
        raise HTTPException(status_code=400, detail="No ontology file uploaded")

    try:
        from ..services.rdfmap_service import RDFMapService

        # Ensure ontology_file is a string path
        ontology_file = str(project["ontology_file"])

        service = RDFMapService(uploads_dir=settings.UPLOAD_DIR, data_dir=settings.DATA_DIR)
        analysis = service.analyze_ontology(ontology_file)

        return analysis
    except Exception as e:
        logger.error(f"Error analyzing ontology: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error analyzing ontology: {str(e)}")


