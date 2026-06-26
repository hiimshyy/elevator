"""Smoke test: controller-telemetry domain modules stay isolated.

Validates that the new controller-telemetry domain modules transitively import
none of the forbidden outward layers or Modbus libraries. Each module is
imported in a clean subprocess so that imports leaked by other tests in the
suite cannot mask a real isolation violation.

Validates: Requirements 1.10, 3.10
"""

import subprocess
import sys
import textwrap

import pytest

# New controller-telemetry domain modules created in tasks 1.1-1.5.
DOMAIN_MODULES: tuple[str, ...] = (
    "elevator_pdm.domain.value_objects.register_map",
    "elevator_pdm.domain.entities.controller_snapshot",
    "elevator_pdm.domain.interfaces.controller_gateway",
    "elevator_pdm.domain.interfaces.controller_snapshot_repository",
    "elevator_pdm.domain.interfaces.mqtt_publisher",
)

# Top-level package names the domain layer must never pull in (R1.10).
FORBIDDEN_PREFIXES: tuple[str, ...] = (
    "pymodbus",
    "minimalmodbus",
    "elevator_pdm.application",
    "elevator_pdm.infrastructure",
    "elevator_pdm.presentation",
)


def _forbidden_imports(module_name: str) -> list[str]:
    """Import ``module_name`` in a clean subprocess and return forbidden imports.

    Returns the sorted list of ``sys.modules`` entries that match a forbidden
    prefix after importing the target module. An empty list means the module is
    isolated.
    """
    script = textwrap.dedent(
        f"""
        import importlib
        import sys

        forbidden = {FORBIDDEN_PREFIXES!r}
        importlib.import_module({module_name!r})

        hits = sorted(
            name
            for name in sys.modules
            if any(name == p or name.startswith(p + ".") for p in forbidden)
        )
        print("\\n".join(hits))
        """
    )
    completed = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        check=True,
    )
    return [line for line in completed.stdout.splitlines() if line]


@pytest.mark.parametrize("module_name", DOMAIN_MODULES)
def test_domain_module_imports_no_forbidden_packages(module_name: str) -> None:
    """Each domain module imports no Modbus libs or outward layers (R1.10)."""
    hits = _forbidden_imports(module_name)
    assert hits == [], f"{module_name} transitively imports forbidden modules: {hits}"


def test_controller_snapshot_defined_without_sensor_reading() -> None:
    """ControllerSnapshot is a standalone domain entity (R3.10).

    The snapshot entity must be importable on its own without dragging in the
    pre-existing SensorReading entity, proving it was added without modifying
    that entity.
    """
    script = textwrap.dedent(
        """
        import importlib
        import sys

        importlib.import_module(
            "elevator_pdm.domain.entities.controller_snapshot"
        )
        print("sensor_reading_loaded:" + str(
            "elevator_pdm.domain.entities.sensor_reading" in sys.modules
        ))
        """
    )
    completed = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "sensor_reading_loaded:False" in completed.stdout
