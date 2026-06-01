"""Live Monitor page for the Streamlit dashboard."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd
import requests
import streamlit as st

API_BASE = "http://localhost:8000/api"
API_HEADERS = {"X-API-Key": "elevator-secret-key-123"}
POLL_INTERVAL_SECONDS = 5


def _request_json(path: str, params: dict[str, Any] | None = None) -> tuple[Any, str | None]:
    """Fetch JSON from the API and return either payload or an error message."""
    try:
        response = requests.get(
            f"{API_BASE}{path}",
            headers=API_HEADERS,
            params=params,
            timeout=5,
        )
    except requests.RequestException as exc:
        return None, f"Request failed: {exc}"

    if response.status_code != 200:
        return None, f"API returned HTTP {response.status_code} for {path}"

    try:
        return response.json(), None
    except ValueError:
        return None, f"API returned invalid JSON for {path}"


def get_elevators() -> tuple[list[dict[str, Any]], str | None]:
    """Fetch all elevators from the API."""
    payload, error = _request_json("/elevators")
    if error:
        return [], error
    return payload or [], None


def get_readings(elevator_id: str, limit: int = 60) -> tuple[list[dict[str, Any]], str | None]:
    """Fetch recent readings for an elevator."""
    payload, error = _request_json(
        f"/elevators/{elevator_id}/readings",
        params={"limit": limit},
    )
    if error:
        return [], error
    return payload or [], None


def build_chart_dataframe(readings: list[dict[str, Any]]) -> pd.DataFrame:
    """Convert API readings into a chart-ready dataframe."""
    rows: list[dict[str, Any]] = []

    for reading in readings:
        timestamp = reading.get("timestamp")
        if not timestamp:
            continue

        rows.append(
            {
                "Timestamp": pd.to_datetime(timestamp, utc=True),
                "Accel RMS (mg)": reading.get("accel_rms_mg", 0) or 0,
                "Velocity RMS (mm/s)": reading.get("velocity_rms_mms", 0) or 0,
                "Load (kg)": reading.get("load_kg", 0) or 0,
                "Temperature (C)": (
                    reading.get("vib_temperature_c")
                    or reading.get("env_temperature_c")
                    or 0
                ),
            }
        )

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    df = df.sort_values("Timestamp").set_index("Timestamp")
    return df


def get_empty_state_message(elevator_id: str, monitoring: bool) -> str:
    """Return the empty-state message for the current monitor mode."""
    if monitoring:
        return (
            f"Live monitor is active for {elevator_id}, "
            "but the API returned no sensor readings yet. "
            "Start the sensor polling pipeline or ingest sample data first."
        )

    return (
        f"No sensor readings are available for {elevator_id} yet. "
        "Click 'Start Live Monitor' after the polling pipeline is producing data."
    )


def render_charts(df: pd.DataFrame) -> None:
    """Render summary metrics and charts for the selected elevator."""
    latest = df.iloc[-1]
    metric_cols = st.columns(4)
    metric_cols[0].metric("Accel RMS", f"{latest['Accel RMS (mg)']:.2f} mg")
    metric_cols[1].metric("Velocity RMS", f"{latest['Velocity RMS (mm/s)']:.2f} mm/s")
    metric_cols[2].metric("Load", f"{latest['Load (kg)']:.2f} kg")
    metric_cols[3].metric("Temperature", f"{latest['Temperature (C)']:.2f} C")

    chart_cols = st.columns(2)
    with chart_cols[0]:
        st.subheader("Acceleration")
        st.line_chart(df[["Accel RMS (mg)"]], width="stretch")
        st.subheader("Load")
        st.line_chart(df[["Load (kg)"]], width="stretch")

    with chart_cols[1]:
        st.subheader("Velocity")
        st.line_chart(df[["Velocity RMS (mm/s)"]], width="stretch")
        st.subheader("Temperature")
        st.line_chart(df[["Temperature (C)"]], width="stretch")


def render_snapshot(elevator_id: str, monitoring: bool) -> None:
    """Render one snapshot of live data for the selected elevator."""
    readings, error = get_readings(elevator_id, limit=60)
    st.caption(
        f"Last fetch attempt: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} "
        f"(refresh interval: {POLL_INTERVAL_SECONDS}s)"
    )

    if error:
        st.error(f"Unable to load readings for {elevator_id}. {error}")
        return

    if not readings:
        st.warning(get_empty_state_message(elevator_id, monitoring))
        return

    df = build_chart_dataframe(readings)
    if df.empty:
        st.warning(f"Readings were returned for {elevator_id}, but they could not be charted.")
        return

    st.caption(f"Showing {len(df)} most recent samples for {elevator_id}.")
    render_charts(df)


def show_page() -> None:
    """Display the Live Monitor page."""
    st.title("Live Monitor")

    if "monitoring" not in st.session_state:
        st.session_state.monitoring = False

    elevators, error = get_elevators()
    if error:
        st.error(f"Unable to load elevators. {error}")
        return

    if not elevators:
        st.warning("No elevators found in the API.")
        return

    elevator_ids = [elevator["id"] for elevator in elevators]
    if st.session_state.get("live_selected_elevator") not in elevator_ids:
        st.session_state.live_selected_elevator = elevator_ids[0]

    selected = st.selectbox(
        "Select Elevator",
        options=elevator_ids,
        key="live_selected_elevator",
    )

    control_cols = st.columns([1, 1, 3])
    if control_cols[0].button("Start Live Monitor", width="stretch"):
        st.session_state.monitoring = True

    if control_cols[1].button("Stop Live Monitor", width="stretch"):
        st.session_state.monitoring = False

    if st.session_state.monitoring:
        st.success(
            f"Live monitor is running for {selected}. "
            f"The charts refresh every {POLL_INTERVAL_SECONDS} seconds."
        )

        @st.fragment(run_every=f"{POLL_INTERVAL_SECONDS}s")
        def live_monitor_fragment() -> None:
            render_snapshot(selected, monitoring=True)

        live_monitor_fragment()
        return

    st.info("Live monitor is idle.")
    render_snapshot(selected, monitoring=False)


if __name__ == "__main__":
    show_page()
