"""Live Monitor Page (Task D12).

Select elevator dropdown → live line charts for accel_rms,
velocity_rms, load_kg, temperature.
Polls API every 5s.
"""
import streamlit as st
import requests
import time
from collections import deque
from datetime import datetime

# API base URL
API_BASE = "http://localhost:8000/api"


def get_elevators():
    """Fetch all elevators from API."""
    try:
        response = requests.get(
            f"{API_BASE}/elevators",
            headers={"X-API-Key": "elevator-secret-key-123"},
            timeout=5,
        )
        if response.status_code == 200:
            return response.json()
        return []
    except Exception:
        return []


def get_readings(elevator_id, limit=60):
    """Fetch recent readings for an elevator."""
    try:
        response = requests.get(
            f"{API_BASE}/elevators/{elevator_id}/readings",
            headers={"X-API-Key": "elevator-secret-key-123"},
            params={"limit": limit},
            timeout=5,
        )
        if response.status_code == 200:
            return response.json()
        return []
    except Exception:
        return []


def show_page():
    """Display Live Monitor page."""
    st.title("📊 Live Monitor")

    # Select elevator
    elevators = get_elevators()

    if not elevators:
        st.warning("No elevators found or API unavailable.")
        return

    elevator_options = {e["id"]: e for e in elevators}

    selected = st.selectbox(
        "Select Elevator",
        options=list(elevator_options.keys()),
        index=0,
    )

    if not selected:
        st.info("Please select an elevator.")
        return

    # Initialize session state for rolling data
    if "live_data" not in st.session_state:
        st.session_state.live_data = {
            "timestamps": deque(maxlen=60),
            "accel_rms": deque(maxlen=60),
            "velocity_rms": deque(maxlen=60),
            "load_kg": deque(maxlen=60),
            "temp": deque(maxlen=60),
        }

    data = st.session_state.live_data

    # Placeholder for charts
    chart_accel = st.empty()
    chart_velocity = st.empty()
    chart_load = st.empty()
    chart_temp = st.empty()

    # Poll button
    if st.button("Start Live Monitor") or st.session_state.get("monitoring", False):
        st.session_state.monitoring = True

        # Fetch latest readings
        readings = get_readings(selected, limit=60)

        if readings:
            # Update data
            data["timestamps"].clear()
            data["accel_rms"].clear()
            data["velocity_rms"].clear()
            data["load_kg"].clear()
            data["temp"].clear()

            for r in readings:
                try:
                    ts = datetime.fromisoformat(r["timestamp"].replace("Z", "+00:00"))
                    data["timestamps"].append(ts)
                    data["accel_rms"].append(r.get("accel_rms_mg", 0))
                    data["velocity_rms"].append(r.get("velocity_rms_mms") or 0)
                    data["load_kg"].append(r.get("load_kg") or 0)
                    data["temp"].append(r.get("vib_temperature_c") or r.get("env_temperature_c") or 0)
                except Exception:
                    pass

            # Create charts
            if data["timestamps"]:
                import pandas as pd

                df = pd.DataFrame({
                    "Timestamp": list(data["timestamps"]),
                    "Accel RMS (mg)": list(data["accel_rms"]),
                    "Velocity RMS (mm/s)": list(data["velocity_rms"]),
                    "Load (kg)": list(data["load_kg"]),
                    "Temperature (°C)": list(data["temp"]),
                })
                df = df.set_index("Timestamp")

                # Accel RMS chart
                chart_accel.line_chart(
                    df[["Accel RMS (mg)"]],
                    use_container_width=True,
                )
                st.caption("Accel RMS — mg")

                # Velocity RMS chart
                chart_velocity.line_chart(
                    df[["Velocity RMS (mm/s)"]],
                    use_container_width=True,
                )
                st.caption("Velocity RMS — mm/s")

                # Load chart
                chart_load.line_chart(
                    df[["Load (kg)"]],
                    use_container_width=True,
                )
                st.caption("Load — kg")

                # Temperature chart
                chart_temp.line_chart(
                    df[["Temperature (°C)"]],
                    use_container_width=True,
                )
                st.caption("Temperature — °C")

        # Auto-refresh every 5 seconds
        time.sleep(5)
        st.rerun()

    # Show static view if not monitoring
    if not st.session_state.get("monitoring", False):
        st.info("Click 'Start Live Monitor' to begin live monitoring.")
        readings = get_readings(selected, limit=60)

        if readings:
            import pandas as pd

            df = pd.DataFrame([
                {
                    "Timestamp": r["timestamp"],
                    "Accel RMS (mg)": r.get("accel_rms_mg", 0),
                    "Velocity RMS (mm/s)": r.get("velocity_rms_mms") or 0,
                    "Load (kg)": r.get("load_kg") or 0,
                    "Temperature (°C)": r.get("vib_temperature_c") or r.get("env_temperature_c") or 0,
                }
                for r in readings
            ])

            if not df.empty:
                df["Timestamp"] = pd.to_datetime(df["Timestamp"])
                df = df.set_index("Timestamp")

                st.subheader("Accel RMS (mg)")
                st.line_chart(df[["Accel RMS (mg)"]], use_container_width=True)

                st.subheader("Velocity RMS (mm/s)")
                st.line_chart(df[["Velocity RMS (mm/s)"]], use_container_width=True)

                st.subheader("Load (kg)")
                st.line_chart(df[["Load (kg)"]], use_container_width=True)

                st.subheader("Temperature (°C)")
                st.line_chart(df[["Temperature (°C)"]], use_container_width=True)


if __name__ == "__main__":
    show_page()
