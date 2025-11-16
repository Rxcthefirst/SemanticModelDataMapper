"""Celery worker configuration."""

import logging
from celery import Celery

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import settings
try:
    from .config import settings
    broker_url = settings.CELERY_BROKER_URL
    backend_url = settings.CELERY_RESULT_BACKEND
    logger.info(f"Loaded settings: broker={broker_url}, backend={backend_url}")
except Exception as e:
    logger.error(f"Error loading settings: {e}")
    # Fallback to environment variables
    import os
    broker_url = os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0")
    backend_url = os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6379/0")
    logger.info(f"Using fallback: broker={broker_url}, backend={backend_url}")

# Create Celery app
celery_app = Celery(
    "rdfmap",
    broker=broker_url,
    backend=backend_url,
)

# Configure Celery
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
)

logger.info("Celery app configured successfully")

# Auto-discover tasks (optional)
# celery_app.autodiscover_tasks(['app.tasks'])


@celery_app.task
def test_task():
    """Test task to verify Celery is working."""
    logger.info("Test task executed successfully!")
    return "Celery is working!"


@celery_app.task
def convert_to_rdf_task(project_id: str, mapping_file_path: str | None = None, output_format: str = "turtle", validate: bool = True):
    """
    Background task for RDF conversion using RDFMapService.

    Args:
        project_id: Project ID
        mapping_file_path: Path to the mapping file (optional)
        output_format: Desired output format (default: "turtle")
        validate: Whether to validate the mapping (default: True)

    Returns:
        dict: Result with status and additional information
    """
    logger.info(f"Starting RDF conversion for project {project_id}")

    try:
        from .services.rdfmap_service import RDFMapService
        service = RDFMapService()
        result = service.convert_to_rdf(
            project_id=project_id,
            mapping_file_path=mapping_file_path,
            output_format=output_format,
            validate=validate,
        )
        logger.info(f"RDF conversion completed for project {project_id}")
        return {"status": "success", **result}
    except Exception as e:
        logger.error(f"convert_to_rdf_task failed: {e}")
        return {"status": "error", "error": str(e)}
