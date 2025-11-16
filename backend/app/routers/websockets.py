"""WebSocket router - placeholder."""
from fastapi import APIRouter, WebSocket

router = APIRouter()

@router.websocket("/{project_id}")
async def websocket_endpoint(websocket: WebSocket, project_id: str):
    await websocket.accept()
    await websocket.send_json({"message": "Connected"})
    await websocket.close()

