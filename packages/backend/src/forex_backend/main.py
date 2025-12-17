"""FastAPI application entry point."""

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from forex_backend.api.v1 import api_router

app = FastAPI(
    title="Forex Signal Agent API",
    description="Backend API for managing forex signals and user dashboard",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API v1 router
app.include_router(api_router, prefix="/api")


@app.get("/")
async def root():
    """Health check endpoint."""
    return {"status": "ok", "service": "forex-backend"}


@app.get("/health")
async def health():
    """API health check."""
    return {"status": "healthy"}


def main():
    """Run the application."""
    uvicorn.run(
        "forex_backend.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )


if __name__ == "__main__":
    main()