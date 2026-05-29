"""FastAPI application factory.

Creates the FastAPI app with lifespan (init DB, load models),
CORS middleware, and API key auth.
"""
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Depends, Response
from fastapi.middleware.cors import CORSMiddleware

from elevator_pdm.presentation.api.dependencies import (
    get_settings,
    get_db_engine,
)
from elevator_pdm.presentation.api.routers import (
    elevators_router,
    predict_router,
    alerts_router,
    maintenance_router,
    health_router,
    models_router,
)
from elevator_pdm.presentation.api.auth import verify_api_key


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan events.

    - Creates database tables on startup.
    - Loads ML models.
    """
    # Startup
    settings = get_settings()
    engine = get_db_engine()
    # Import models to register them with Base
    from elevator_pdm.infrastructure.persistence import models  # noqa: F401
    models.Base.metadata.create_all(bind=engine)
    yield
    # Shutdown (nothing to clean up for SQLite)


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Returns:
        Configured FastAPI application.
    """
    settings = get_settings()

    app = FastAPI(
        title="Elevator PDM API",
        description="Predictive Maintenance API for Elevator Monitoring",
        version="1.0.0",
        lifespan=lifespan,
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # TODO: configure from settings
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Global API key auth dependency
    # All routes except /api/health require API key
    api_key_dep = Depends(verify_api_key)

    # Register routers
    app.include_router(
        elevators_router,
        prefix="/api/elevators",
        tags=["elevators"],
        dependencies=[api_key_dep],
    )
    app.include_router(
        predict_router,
        prefix="/api",
        tags=["predict"],
        dependencies=[api_key_dep],
    )
    app.include_router(
        alerts_router,
        prefix="/api/alerts",
        tags=["alerts"],
        dependencies=[api_key_dep],
    )
    app.include_router(
        maintenance_router,
        prefix="/api/maintenance",
        tags=["maintenance"],
        dependencies=[api_key_dep],
    )
    app.include_router(
        health_router,
        prefix="/api/health",
        tags=["health"],
        # No auth for health check
    )
    app.include_router(
        models_router,
        prefix="/api/models",
        tags=["models"],
        dependencies=[api_key_dep],
    )

    @app.get("/")
    async def root():
        return {"message": "Elevator PDM API", "docs": "/docs"}

    @app.get("/favicon.ico", include_in_schema=False)
    async def favicon() -> Response:
        """Return an empty favicon to avoid 404 noise in browser logs."""
        return Response(content=b"", media_type="image/x-icon")

    return app


# Create the app instance for uvicorn
app = create_app()
