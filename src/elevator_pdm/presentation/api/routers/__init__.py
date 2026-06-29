"""Routers package — exports all API routers."""
from elevator_pdm.presentation.api.routers.alerts import router as alerts_router
from elevator_pdm.presentation.api.routers.controller import router as controller_router
from elevator_pdm.presentation.api.routers.elevators import router as elevators_router
from elevator_pdm.presentation.api.routers.health import router as health_router
from elevator_pdm.presentation.api.routers.maintenance import router as maintenance_router
from elevator_pdm.presentation.api.routers.models import router as models_router
from elevator_pdm.presentation.api.routers.predict import router as predict_router

__all__ = [
    "alerts_router",
    "controller_router",
    "elevators_router",
    "health_router",
    "maintenance_router",
    "models_router",
    "predict_router",
]
