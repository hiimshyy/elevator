"""Routers package — exports all API routers."""
from elevator_pdm.presentation.api.routers.elevators import router as elevators_router
from elevator_pdm.presentation.api.routers.predict import router as predict_router
from elevator_pdm.presentation.api.routers.alerts import router as alerts_router
from elevator_pdm.presentation.api.routers.maintenance import router as maintenance_router
from elevator_pdm.presentation.api.routers.health import router as health_router
from elevator_pdm.presentation.api.routers.models import router as models_router

__all__ = [
    "elevators_router",
    "predict_router",
    "alerts_router",
    "maintenance_router",
    "health_router",
    "models_router",
]
