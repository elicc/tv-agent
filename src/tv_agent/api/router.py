"""Versioned API router composition."""

from fastapi import APIRouter

from tv_agent.api.routes.health import router as health_router

api_router = APIRouter()
api_router.include_router(health_router, tags=["health"])
