# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build & Development Commands

```bash
# Activate virtual environment (Windows) before running any commands
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

# Run Streamlit dashboard
streamlit run src/elevator_pdm/presentation/dashboard/app.py
```

## Architecture

Clean Architecture with four layers. **Dependencies point inward only**: Infrastructure → Application → Domain. Outer layers import from inner layers; inner layers never import from outer layers.

```
src/elevator_pdm/
├── domain/           # Innermost: entities, value objects, interfaces (abstract), events
├── application/       # Use cases (orchestration), DTOs, services (feature engineer, health calc)
├── infrastructure/    # Adapters: sensors, persistence, ML, messaging, notifications, config
└── presentation/      # FastAPI routers, WebSocket, schemas, Streamlit dashboard
```

### Key Design Patterns

- **Repository**: `domain/interfaces/*_repository.py` defines abstract repos; `infrastructure/persistence/sqlite_*_repo.py` implements them. Swap SQLite ↔ PostgreSQL without touching use cases.
- **Gateway**: `domain/interfaces/sensor_gateway.py` abstracts sensor I/O. `infrastructure/sensors/mock_gateway.py` for tests, `modbus_gateway.py` for production.
- **Strategy**: `domain/interfaces/model_runtime.py` abstracts inference; `infrastructure/ml/onnx_runtime.py` implements it.
- **Dependency Injection**: `presentation/api/dependencies.py` uses FastAPI `Depends()` to wire concrete implementations to abstract interfaces.

### Configuration

- Settings: `src/elevator_pdm/infrastructure/config/settings.py` — Pydantic BaseSettings loading from `config/config.yaml` with env var overrides
- Env vars use prefix `ELEVATOR_` with `__` as nested delimiter (e.g., `ELEVATOR_SERIAL__PORT=/dev/ttyUSB1`)
- Logging config: `config/logging.yaml`

### Key Paths

| What | Where |
|---|---|
| Domain interfaces (ports) | `src/elevator_pdm/domain/interfaces/` |
| Use cases | `src/elevator_pdm/application/use_cases/` |
| Sensor/config adapters | `src/elevator_pdm/infrastructure/` |
| FastAPI routers | `src/elevator_pdm/presentation/api/routers/` |
| API schemas | `src/elevator_pdm/presentation/api/schemas/` |
| Tests | `tests/unit/`, `tests/integration/`, `tests/e2e/` |
| Engineering tasks | `docs/engineering_tasks.md` |
| Full implementation plan | `docs/implementation_plan.md` |

### Sensor Stack

Three RS-485 Modbus RTU sensors on shared bus: ES-VS-01 (vibration, slave 1), ES35-SW (temp/humidity, slave 2), RW-ST01D + HD-MV01A (load cell, slave 3). Poll interval: 5s vibration, 30s temp/humidity, 1s load.

### Database & Cloud Sync

SQLite on edge (5 tables: elevators, sensor_readings, inference_results, alerts, maintenance_schedule). Edge publishes unsynchronized data via **MQTT** to a Cloud Broker, and a Cloud Subscriber worker inserts it into PostgreSQL in the cloud. ORM: SQLAlchemy 2.0 with `infrastructure/persistence/models.py`.
