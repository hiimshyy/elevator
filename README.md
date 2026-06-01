# Elevator Predictive Maintenance (elevator-pdm)

AI-powered predictive maintenance system for elevators using vibration, temperature/humidity, and load cell sensors.

## Architecture

This project follows **Clean Architecture** with four layers:

- **Domain** — Entities, value objects, interfaces (ports), domain events
- **Application** — Use cases, DTOs, feature engineering
- **Infrastructure** — Adapters: Modbus, SQLite/PostgreSQL, Redis, MQTT, ONNX, Slack, SMTP
- **Presentation** — FastAPI REST/WebSocket API, React frontend

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

# Run alert pipeline once
.venv\Scripts\python.exe scripts/process_alert_pipeline.py --once

# Run alert pipeline continuously
.venv\Scripts\python.exe scripts/process_alert_pipeline.py

# Planned frontend workspace
cd frontend
npm install
npm run dev

# Run tests
pytest
```

> [!NOTE]
> The repository still contains a legacy Streamlit dashboard under
> `src/elevator_pdm/presentation/dashboard/`, but the target UI going forward is a
> separate React app in `frontend/`.

## Docker Deployment

```bash
docker-compose up -d
```

Services started by the edge stack:
- `api`: FastAPI app on port `8000`
- `alert-worker`: continuous reading -> inference -> alert pipeline
- `frontend`: React app (Vite) on port `5173`

After `docker-compose up -d`, open:
- Frontend: `http://localhost:5173`
- API docs: `http://localhost:8000/docs`

To inspect the worker once the stack is running:

```bash
docker-compose logs -f alert-worker
```

## Documentation

See [docs/implementation_plan.md](docs/implementation_plan.md) for the full Phase 1 plan.
