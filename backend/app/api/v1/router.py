"""API v1 router configuration."""
from fastapi import APIRouter

from app.api.v1.endpoints import tasks, conversations, snapshots, audit, health, websocket

api_router = APIRouter()

api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(tasks.router, prefix="/tasks", tags=["tasks"])
api_router.include_router(conversations.router, prefix="/conversations", tags=["conversations"])
api_router.include_router(snapshots.router, prefix="/snapshots", tags=["snapshots"])
api_router.include_router(audit.router, prefix="/audit-logs", tags=["audit"])
api_router.include_router(websocket.router, prefix="/ws", tags=["websocket"])