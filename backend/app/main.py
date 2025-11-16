"""FastAPI main application."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

from .config import settings
from .routers import projects, mappings, conversion, websockets

# Import RDFMap version
try:
    from rdfmap import __version__ as rdfmap_version
except ImportError:
    rdfmap_version = "unknown"

app = FastAPI(
    title="RDFMap Web API",
    description="Web API for RDFMap - Semantic Model Data Mapper",
    version="0.1.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(projects.router, prefix="/api/projects", tags=["projects"])
app.include_router(mappings.router, prefix="/api/mappings", tags=["mappings"])
app.include_router(conversion.router, prefix="/api/conversion", tags=["conversion"])
app.include_router(websockets.router, prefix="/ws", tags=["websockets"])

# Serve uploaded files (in production, use S3 or CDN)
if os.path.exists("/app/uploads"):
    app.mount("/uploads", StaticFiles(directory="/app/uploads"), name="uploads")


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "RDFMap Web API",
        "version": "0.1.0",
        "rdfmap_core_version": rdfmap_version,
        "docs": "/api/docs",
    }


@app.get("/api/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "rdfmap_version": rdfmap_version,
    }


@app.on_event("startup")
async def startup_event():
    """Initialize on startup."""
    # Create directories
    os.makedirs("/app/uploads", exist_ok=True)
    os.makedirs("/app/data", exist_ok=True)

    # TODO: Initialize database
    # TODO: Load BERT model into memory (if using semantic matching)

    print(f"🚀 RDFMap Web API started (RDFMap Core v{rdfmap_version})")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    print("👋 RDFMap Web API shutting down")

