"""Fleet Overview Page (Task D11).

Lists all elevators with status badges (green/yellow/red),
health score gauges, and last reading timestamp.
Calls REST API to fetch data.
"""
import streamlit as st
import requests
import time
from datetime import datetime, timezone

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
        else:
            st.error(f"Failed to fetch elevators: {response.status_code}")
            return []
    except Exception as e:
        st.error(f"API connection error: {e}")
        return []


def get_status_color(status, health_score):
    """Return color based on status or health score."""
    if status == "CRITICAL":
        return "red"
    elif status == "WARNING":
        return "orange"
    elif status == "OVERLOAD":
        return "red"
    elif health_score is not None:
        if health_score >= 85:
            return "green"
        elif health_score >= 40:
            return "orange"
        else:
            return "red"
    return "gray"


def show_page():
    """Display Fleet Overview page."""
    st.title("🏢 Fleet Overview")

    # Auto-refresh every 10 seconds
    auto_refresh = st.checkbox("Auto-refresh (10s)", value=True)
    if auto_refresh:
        time.sleep(10)
        st.rerun()

    # Fetch elevators
    elevators = get_elevators()

    if not elevators:
        st.warning("No elevators found or API unavailable.")
        return

    st.write(f"**Total elevators:** {len(elevators)}")

    # Display each elevator
    cols = st.columns(3)

    for idx, elev in enumerate(elevators):
        col = cols[idx % 3]

        with col:
            # Determine status color
            color = get_status_color(elev.get("status"), elev.get("latest_health_score"))

            # Card container
            with st.container(border=True):
                # Elevator ID and status badge
                st.subheader(f"Elevator {elev['id']}")

                # Color-coded status badge
                status = elev.get("status", "UNKNOWN")
                badge_color = get_status_color(status, elev.get("latest_health_score"))
                st.markdown(
                    f"<span style='background-color: {badge_color}; color: white; "
                    f"padding: 4px 8px; border-radius: 4px;'>{status}</span>",
                    unsafe_allow_html=True,
                )

                # Health score gauge
                health_score = elev.get("latest_health_score")
                if health_score is not None:
                    st.metric("Health Score", f"{health_score:.1f}")
                    # Progress bar as gauge
                    st.progress(health_score / 100.0)
                else:
                    st.write("Health: N/A")

                # Max capacity
                st.write(f"**Capacity:** {elev.get('max_capacity_kg', 'N/A')} kg")

                # Created date
                created = elev.get("created_at", "")
                if created:
                    try:
                        dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                        st.write(f"**Created:** {dt.strftime('%Y-%m-%d')}")
                    except Exception:
                        pass

                # Link to live monitor
                if st.button(f"View Live", key=f"live_{elev['id']}"):
                    st.session_state.selected_elevator = elev["id"]
                    st.switch_page("live.py")

    # Summary statistics
    st.divider()
    st.subheader("Summary")

    col1, col2, col3, col4 = st.columns(4)

    healthy = sum(1 for e in elevators if e.get("latest_health_score", 0) >= 85)
    warning = sum(1 for e in elevators if e.get("latest_health_score", 0) >= 40 and e.get("latest_health_score", 0) < 85)
    critical = sum(1 for e in elevators if e.get("latest_health_score", 0) < 40)

    col1.metric("Healthy (≥85)", healthy)
    col2.metric("Warning (40-85)", warning)
    col3.metric("Critical (<40)", critical)
    col4.metric("Total", len(elevators))


if __name__ == "__main__":
    show_page()
