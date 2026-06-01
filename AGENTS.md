# Repository Guidelines

## Project Structure & Module Organization
Core code lives in `src/elevator_pdm/` and follows Clean Architecture:
- `domain/`: entities, value objects, interfaces (ports), domain rules.
- `application/`: use cases and services (feature engineering, orchestration).
- `infrastructure/`: adapters for DB, Modbus, Redis, MQTT, ONNX, notifications.
- `presentation/`: FastAPI API (`api/`) and legacy Streamlit PoC (`dashboard/`).

Supporting folders:
- `tests/` (`unit/`, `integration/`, `e2e/`) for automated coverage.
- `config/` for runtime YAML settings.
- `models/` for ONNX artifacts.
- `docs/` for implementation and engineering plans.
- `scripts/` and `notebooks/` for operational tasks and model training.
- `frontend/` for React + TypeScript (Vite) UI.
- `deploy/` for container/runtime artifacts (for example, `Dockerfile.app`).

## Build, Test, and Development Commands
- `python -m venv .venv` then `.venv\Scripts\activate` (Windows): create/activate env.
- `pip install -e ".[dev]"`: install app + dev tools.
- `uvicorn elevator_pdm.presentation.api.main:app --reload --port 8000`: run API locally.
- `cd frontend && npm install && npm run dev`: run React frontend locally.
- `.venv\Scripts\python.exe scripts/process_alert_pipeline.py --once`: run alert pipeline once.
- `.venv\Scripts\python.exe scripts/process_alert_pipeline.py`: run alert pipeline worker loop.
- `docker-compose up -d --build`: run API + alert worker stack.
- `pytest`: run all tests.
- `pytest --cov=src/elevator_pdm --cov-report=term-missing`: run with coverage.
- `ruff check src tests` and `ruff format src tests`: lint/format Python.
- `mypy src`: strict static type checking.

## Coding Style & Naming Conventions
Target Python `3.11+`, 4-space indentation, max line length 100 (Ruff config).  
Use type hints throughout; `mypy` runs in strict mode.  
Prefer `snake_case` for modules/functions/variables, `PascalCase` for classes, `UPPER_SNAKE_CASE` for constants.  
Keep dependencies inward: domain must not import application/infrastructure/presentation.

## Testing Guidelines
Use `pytest` (+ `pytest-asyncio` for async paths).  
Place tests under matching layers, e.g. `tests/unit/application/test_run_inference.py`.  
Name files `test_*.py` and test functions `test_*`.  
For new features, add at least one unit test and, if API/DB behavior changes, one integration test.

## Commit & Pull Request Guidelines
Recent history follows Conventional Commit style prefixes: `feat:`, `fix:`, `update:`.  
Format commits as `<type>: <imperative summary>` (example: `feat: add MQTT publisher adapter`).

PRs should include:
- concise change summary and impacted layers/files,
- linked task/issue (if available),
- test evidence (`pytest`/coverage/lint output),
- API examples or frontend screenshots when UI/contract changes.

## Security & Configuration Tips
Do not commit secrets. Keep credentials in environment variables and `.env`-style local files.  
Treat `config/config.yaml` as non-secret defaults and override sensitive fields via env vars.
For containers, override DB location with `ELEVATOR_DATABASE__URL` (current compose uses `sqlite:////app/data/elevator.db`).
