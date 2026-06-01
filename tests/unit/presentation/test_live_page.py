"""Tests for the Live Monitor dashboard page."""

from elevator_pdm.presentation.dashboard.pages import live


def test_build_chart_dataframe_sorts_rows_and_uses_temperature_fallback() -> None:
    readings = [
        {
            "timestamp": "2026-06-01T10:00:05Z",
            "accel_rms_mg": 15.0,
            "velocity_rms_mms": 3.2,
            "load_kg": 420.0,
            "env_temperature_c": 29.5,
        },
        {
            "timestamp": "2026-06-01T10:00:00Z",
            "accel_rms_mg": 10.0,
            "velocity_rms_mms": 2.8,
            "load_kg": 400.0,
            "vib_temperature_c": 33.0,
        },
    ]

    df = live.build_chart_dataframe(readings)

    assert list(df["Accel RMS (mg)"]) == [10.0, 15.0]
    assert list(df["Temperature (C)"]) == [33.0, 29.5]


def test_get_empty_state_message_changes_with_monitor_state() -> None:
    idle_message = live.get_empty_state_message("elev-001", monitoring=False)
    active_message = live.get_empty_state_message("elev-001", monitoring=True)

    assert "No sensor readings are available" in idle_message
    assert "Click 'Start Live Monitor'" in idle_message
    assert "Live monitor is active" in active_message
    assert "ingest sample data first" in active_message
