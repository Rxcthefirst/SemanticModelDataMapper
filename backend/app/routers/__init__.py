"""Placeholder routers (to be implemented)."""

from fastapi import APIRouter

# Mappings router
mappings_router = APIRouter()

@mappings_router.get("/{project_id}/mappings")
async def get_mappings(project_id: str):
    """Get project mappings."""
    return {"message": "Not implemented yet"}

# Conversion router
conversion_router = APIRouter()

@conversion_router.post("/{project_id}/convert")
async def convert_to_rdf(project_id: str):
    """Convert project data to RDF."""
    return {"message": "Not implemented yet"}

# WebSocket router
websockets_router = APIRouter()

@websockets_router.websocket("/{project_id}")
async def websocket_endpoint(project_id: str):
    """WebSocket for real-time updates."""
    pass

