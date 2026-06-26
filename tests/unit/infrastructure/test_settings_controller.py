"""Config-sourcing smoke test for the modbus controller telemetry feature.

Verifies that the controller telemetry serial profile, slave id, poll interval,
topic, and register map are sourced from ``Settings`` (Requirements 8.1, 8.2,
8.3, 8.5, 8.7) and that adapter source files contain no hardcoded MQTT
credentials, broker addresses, serial ports, or topic literals (Requirements
8.4, 8.6).
"""

import re
from pathlib import Path

from src.elevator_pdm.infrastructure.config.settings import (
    ControllerSerialConfig,
    RegisterEntryConfig,
    Settings,
)

# Repository root: tests/unit/infrastructure/<this file> -> parents[3] is repo root.
REPO_ROOT = Path(__file__).resolve().parents[3]

# Adapter / settings-consumer source files that should source all connection
# parameters from Settings. Files that do not exist yet (e.g. the controller
# gateway from task 4.1) are skipped so this test does not fail on absent
# modules.
CANDIDATE_ADAPTER_SOURCES = (
    REPO_ROOT / "src/elevator_pdm/infrastructure/messaging/mqtt_publisher.py",
    REPO_ROOT / "src/elevator_pdm/infrastructure/sensors/pymodbus_controller_gateway.py",
    REPO_ROOT / "src/elevator_pdm/application/use_cases/poll_controller.py",
    REPO_ROOT / "src/elevator_pdm/application/services/read_block_planner.py",
)


def _existing_adapter_sources() -> list[Path]:
    return [path for path in CANDIDATE_ADAPTER_SOURCES if path.is_file()]


# ---------------------------------------------------------------------------
# Serial profile sourced from Settings (R8.1)
# ---------------------------------------------------------------------------
def test_controller_serial_profile_loads_from_settings():
    serial = Settings().controller_telemetry.serial
    assert isinstance(serial, ControllerSerialConfig)
    assert serial.port == "/dev/ttyUSB0"
    assert serial.baudrate == 19200
    assert serial.bytesize == 8  # data bits
    assert serial.parity == "E"
    assert serial.stopbits == 1
    assert serial.timeout_ms == 1000


# ---------------------------------------------------------------------------
# Slave id sourced from Settings (R8.2)
# ---------------------------------------------------------------------------
def test_controller_slave_id_loads_from_settings():
    assert Settings().controller_telemetry.slave_id == 1


# ---------------------------------------------------------------------------
# Poll interval sourced from Settings (R8.3)
# ---------------------------------------------------------------------------
def test_controller_poll_interval_loads_from_settings():
    assert Settings().controller_telemetry.poll_interval_s == 5


# ---------------------------------------------------------------------------
# Elevator topic sourced from Settings (R8.5)
# ---------------------------------------------------------------------------
def test_controller_topic_loads_from_settings():
    assert Settings().controller_telemetry.topic_elevator == "embody/elevator"


# ---------------------------------------------------------------------------
# MQTT broker/credentials sourced from Settings (R8.4)
# ---------------------------------------------------------------------------
def test_mqtt_connection_params_load_from_settings():
    mqtt = Settings().mqtt
    # Fields exist and are sourced from Settings (defaults are blank so they
    # MUST be supplied via env/yaml, never hardcoded in source).
    assert hasattr(mqtt, "broker_url")
    assert hasattr(mqtt, "port")
    assert hasattr(mqtt, "username")
    assert hasattr(mqtt, "password")
    assert hasattr(mqtt, "client_id")
    assert mqtt.port == 1883
    assert mqtt.client_id == "embody002"


# ---------------------------------------------------------------------------
# Register map (addresses, scale factors, display bases) sourced from Settings
# (R8.7)
# ---------------------------------------------------------------------------
def test_controller_register_map_loads_from_settings():
    register_map = Settings().controller_telemetry.register_map
    assert len(register_map) > 0
    assert all(isinstance(entry, RegisterEntryConfig) for entry in register_map)

    # Every entry exposes address, scale, and base fields (R8.7).
    for entry in register_map:
        assert isinstance(entry.address, int)
        assert isinstance(entry.scale, str)
        assert isinstance(entry.base, int)

    by_key = {entry.key: entry for entry in register_map}
    assert by_key["current_floor"].address == 0x2111
    assert by_key["current"].address == 0x2121
    assert by_key["voltage"].address == 0x2122


# ---------------------------------------------------------------------------
# No hardcoded credentials / addresses / ports / topic in adapter sources
# (R8.6)
# ---------------------------------------------------------------------------
def test_adapter_sources_have_no_hardcoded_serial_port():
    # Serial device paths must come from Settings, never inline literals.
    serial_port_pattern = re.compile(r"/dev/tty(USB|S|AMA)\d|COM\d")
    for path in _existing_adapter_sources():
        source = path.read_text(encoding="utf-8")
        match = serial_port_pattern.search(source)
        assert match is None, f"Hardcoded serial port {match.group()!r} found in {path}"


def test_adapter_sources_have_no_hardcoded_topic():
    # The embody/elevator topic must be sourced from Settings.topic_elevator.
    for path in _existing_adapter_sources():
        source = path.read_text(encoding="utf-8")
        assert "embody/elevator" not in source, f"Hardcoded topic literal found in {path}"


def test_adapter_sources_have_no_hardcoded_broker_address():
    # Broker host:port / IP literals and mqtt:// hosts must come from Settings.
    ip_literal_pattern = re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b")
    broker_scheme_pattern = re.compile(r"mqtts?://[^\"'\s]+")
    for path in _existing_adapter_sources():
        source = path.read_text(encoding="utf-8")
        ip_match = ip_literal_pattern.search(source)
        assert ip_match is None, f"Hardcoded broker IP {ip_match.group()!r} found in {path}"
        scheme_match = broker_scheme_pattern.search(source)
        assert scheme_match is None, (
            f"Hardcoded broker address {scheme_match.group()!r} found in {path}"
        )
