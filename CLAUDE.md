# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with this repository.

## Build And Development Commands

```bash
# Activate virtual environment (Windows)
.venv\Scripts\activate

# Install project in editable mode with dev dependencies
pip install -e ".[dev]"

# Run all tests
pytest

# Run a single test file
pytest tests/unit/infrastructure/test_settings.py

# Run a single test by name
pytest -k "test_loads_from_config_yaml"

# Run tests with coverage
pytest --cov=src/elevator_pdm --cov-report=term-missing

# Lint
ruff check src/ tests/

# Format
ruff format src/ tests/

# Type check
mypy src/

# Run API server
uvicorn elevator_pdm.presentation.api.main:app --reload --port 8000

# Run React frontend
cd frontend
npm install
npm run dev

# Run alert pipeline once
cd ..
.venv\Scripts\python.exe scripts/process_alert_pipeline.py --once

# Run alert pipeline worker loop
.venv\Scripts\python.exe scripts/process_alert_pipeline.py

# Run API + alert worker with Docker Compose
docker-compose up -d --build
docker-compose logs -f alert-worker
```

## Architecture

Clean Architecture with four layers. Dependencies point inward only:
Infrastructure -> Application -> Domain.
Outer layers can import inner layers; inner layers must never import outer layers.

```text
src/elevator_pdm/
|- domain/           # entities, value objects, interfaces (ports), events
|- application/      # use cases, DTOs, services
|- infrastructure/   # adapters: sensors, persistence, ML, messaging, notifications, config
`- presentation/     # FastAPI routers, WebSocket, schemas, legacy Streamlit PoC
```

### Key Design Patterns

- Repository: `domain/interfaces/*_repository.py` defines abstract repos; `infrastructure/persistence/sqlite_*_repo.py` implements them.
- Gateway: `domain/interfaces/sensor_gateway.py` abstracts sensor I/O. `mock_gateway.py` for tests, `modbus_gateway.py` for production.
- Strategy: `domain/interfaces/model_runtime.py` abstracts inference; `infrastructure/ml/onnx_runtime.py` implements it.
- Dependency Injection: `presentation/api/dependencies.py` wires concrete implementations with FastAPI `Depends()`.

## Frontend And Runtime Status

- Primary UI: React app in `frontend/` (Vite + TypeScript).
- Legacy UI: Streamlit under `src/elevator_pdm/presentation/dashboard/` is a PoC fallback.
- Current compose stack starts:
- `api` (FastAPI on `http://localhost:8000`)
- `alert-worker` (continuous reading -> inference -> alert pipeline)
- Frontend is currently run separately via `npm run dev` (default `http://localhost:5173`).

## Configuration

- Settings: `src/elevator_pdm/infrastructure/config/settings.py`
- Loads from `config/config.yaml` with env var overrides.
- Env prefix: `ELEVATOR_`
- Nested delimiter: `__`
- Example: `ELEVATOR_SERIAL__PORT=/dev/ttyUSB1`
- Worker settings:
- `ELEVATOR_WORKERS__ALERT_PIPELINE_INTERVAL_S`
- `ELEVATOR_WORKERS__ALERT_PIPELINE_LIMIT`
- In Docker Compose, DB URL is overridden to:
- `ELEVATOR_DATABASE__URL=sqlite:////app/data/elevator.db`

## Key Paths

| What | Where |
|---|---|
| Domain interfaces (ports) | `src/elevator_pdm/domain/interfaces/` |
| Use cases | `src/elevator_pdm/application/use_cases/` |
| Worker loop service | `src/elevator_pdm/application/services/alert_pipeline_worker.py` |
| Sensor/config adapters | `src/elevator_pdm/infrastructure/` |
| FastAPI routers | `src/elevator_pdm/presentation/api/routers/` |
| API schemas | `src/elevator_pdm/presentation/api/schemas/` |
| React frontend | `frontend/` |
| Alert pipeline script | `scripts/process_alert_pipeline.py` |
| Compose stack | `docker-compose.yml` |
| App Dockerfile | `deploy/Dockerfile.app` |
| Tests | `tests/unit/`, `tests/integration/`, `tests/e2e/` |
| Engineering tasks | `docs/engineering_tasks.md` |
| Full implementation plan | `docs/implementation_plan.md` |

## Sensor Stack

Three RS-485 Modbus RTU sensors on a shared bus:
- ES-VS-01 (vibration, slave 1)
- ES35-SW (temp/humidity, slave 2)
- RW-ST01D + HD-MV01A (load, slave 3)

Recommended polling:
- vibration: 5s
- temp/humidity: 30s
- load: 1s

## Database And Cloud Sync

- Edge DB: SQLite (`elevators`, `sensor_readings`, `inference_results`, `alerts`, `maintenance_schedule`)
- ORM: SQLAlchemy 2.0 (`infrastructure/persistence/models.py`)
- Edge to cloud path uses MQTT publisher/subscriber pattern for sync into PostgreSQL.
