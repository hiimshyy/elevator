"""FastAPI application factory.

Creates the FastAPI app with lifespan (init DB, load models),
CORS middleware, and API key auth.
"""
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware

from elevator_pdm.infrastructure.persistence.database import init_db
from elevator_pdm.presentation.api.auth import verify_api_key
from elevator_pdm.presentation.api.dependencies import get_db_engine
from elevator_pdm.presentation.api.routers import (
    alerts_router,
    elevators_router,
    health_router,
    maintenance_router,
    models_router,
    predict_router,
)
from elevator_pdm.presentation.api.websocket.sensor_stream import router as sensor_stream_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan events.

    - Creates database tables on startup.
    - Loads ML models.
    """
    # Startup
    engine = get_db_engine()
    init_db(engine)
    yield
    # Shutdown (nothing to clean up for SQLite)


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Returns:
        Configured FastAPI application.
    """
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
    app.include_router(sensor_stream_router, tags=["websocket"])

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
