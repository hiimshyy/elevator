# Elevator Predictive Maintenance (elevator-pdm)

AI-powered predictive maintenance system for elevators using vibration, temperature/humidity, and load cell sensors.

## Architecture

This project follows **Clean Architecture** with four layers:

- **Domain** — Entities, value objects, interfaces (ports), domain events
- **Application** — Use cases, DTOs, feature engineering
- **Infrastructure** — Adapters: Modbus, SQLite/PostgreSQL, Redis, ONNX, Slack, SMTP
- **Presentation** — FastAPI REST/WebSocket API, Streamlit dashboard

## Quick Start

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
.venv\Scripts\activate     # Windows

# Install dependencies
pip install -e ".[dev]"

# Run API server
uvicorn elevator_pdm.presentation.api.main:app --reload --port 8000

# Run Streamlit dashboard
streamlit run src/elevator_pdm/presentation/dashboard/app.py

# Run tests
pytest
```

## Docker Deployment

```bash
docker-compose up -d
```

## Documentation

See [docs/implementation_plan.md](docs/implementation_plan.md) for the full Phase 1 plan.
