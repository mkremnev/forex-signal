"""API v1 routers."""

from fastapi import APIRouter

from forex_backend.api.v1 import auth, settings

# Create main v1 router
api_router = APIRouter(prefix="/v1")

# Include sub-routers
api_router.include_router(auth.router)
api_router.include_router(settings.router)

__all__ = ["api_router"]