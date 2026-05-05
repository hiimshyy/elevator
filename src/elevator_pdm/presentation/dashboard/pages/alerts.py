"""Alerts & Maintenance Page (Task D13).

View and manage alerts and maintenance records.
Calls REST API to fetch and update data.
"""
import streamlit as st
import requests
from datetime import datetime

# API base URL
API_BASE = "http://localhost:8000/api"


def get_alerts(elevator_id=None, severity=None, acknowledged=None):
    """Fetch alerts from API."""
    try:
        params = {}
        if elevator_id:
            params["elevator_id"] = elevator_id
        if severity:
            params["severity"] = severity
        if acknowledged is not None:
            params["acknowledged"] = "true" if acknowledged else "false"

        response = requests.get(
            f"{API_BASE}/alerts",
            headers={"X-API-Key": "elevator-secret-key-123"},
            params=params,
            timeout=5,
        )
        if response.status_code == 200:
            return response.json()
        return []
    except Exception:
        return []


def get_maintenance(elevator_id=None, status=None):
    """Fetch maintenance records from API."""
    try:
        params = {}
        if elevator_id:
            params["elevator_id"] = elevator_id
        if status:
            params["status"] = status

        response = requests.get(
            f"{API_BASE}/maintenance",
            headers={"X-API-Key": "elevator-secret-key-123"},
            params=params,
            timeout=5,
        )
        if response.status_code == 200:
            return response.json()
        return []
    except Exception:
        return []


def acknowledge_alert(alert_id, technician):
    """Acknowledge an alert via API."""
    try:
        response = requests.patch(
            f"{API_BASE}/alerts/{alert_id}/acknowledge",
            headers={"X-API-Key": "elevator-secret-key-123"},
            json={"technician": technician},
            timeout=5,
        )
        return response.status_code == 200
    except Exception:
        return False


def show_page():
    """Display Alerts & Maintenance page."""
    st.title("📢 Alerts & Maintenance")

    # Tabs
    tab1, tab2, tab3 = st.tabs(["📢 Alerts", "🔧 Maintenance", "➕ Create Maintenance"])

    # Alerts tab
    with tab1:
        st.subheader("Alerts")

        # Filters
        col1, col2, col3 = st.columns(3)

        with col1:
            severity_filter = st.selectbox(
                "Filter by Severity",
                options=["All", "WARNING", "CRITICAL", "OVERLOAD"],
                index=0,
            )

        with col2:
            ack_filter = st.selectbox(
                "Filter by Status",
                options=["All", "Acknowledged", "Not Acknowledged"],
                index=0,
            )

        with col3:
            elevator_filter = st.text_input("Elevator ID (optional)")

        # Fetch alerts
        severity = severity_filter if severity_filter != "All" else None
        acknowledged = None
        if ack_filter == "Acknowledged":
            acknowledged = True
        elif ack_filter == "Not Acknowledged":
            acknowledged = False

        alerts = get_alerts(
            elevator_id=elevator_filter if elevator_filter else None,
            severity=severity,
            acknowledged=acknowledged,
        )

        if not alerts:
            st.info("No alerts found.")
        else:
            st.write(f"**Total alerts:** {len(alerts)}")

            for alert in alerts:
                with st.container(border=True):
                    col1, col2, col3 = st.columns([2, 2, 1])

                    with col1:
                        st.write(f"**Elevator:** {alert['id']}")
                        st.write(f"**Severity:** {alert['severity']}")
                        st.write(f"**Message:** {alert['message']}")

                    with col2:
                        st.write(f"**Time:** {alert['timestamp']}")
                        ack_status = "✅ Yes" if alert['acknowledged'] else "❌ No"
                        st.write(f"**Acknowledged:** {ack_status}")

                    with col3:
                        if not alert["acknowledged"]:
                            technician = st.text_input(
                                "Technician",
                                key=f"tech_{alert['id']}",
                            )
                            if st.button("Acknowledge", key=f"ack_{alert['id']}"):
                                if acknowledge_alert(alert["id"], technician):
                                    st.success("Alert acknowledged!")
                                    st.rerun()
                                else:
                                    st.error("Failed to acknowledge alert.")

    # Maintenance tab
    with tab2:
        st.subheader("Maintenance Records")

        # Filters
        col1, col2 = st.columns(2)

        with col1:
            status_filter = st.selectbox(
                "Filter by Status",
                options=["All", "pending", "scheduled", "completed"],
                index=0,
            )

        with col2:
            elevator_filter = st.text_input("Elevator ID (optional)", key="maint_elevator")

        # Fetch maintenance records
        maintenance = get_maintenance(
            elevator_id=elevator_filter if elevator_filter else None,
            status=status_filter if status_filter != "All" else None,
        )

        if not maintenance:
            st.info("No maintenance records found.")
        else:
            st.write(f"**Total records:** {len(maintenance)}")

            for record in maintenance:
                with st.container(border=True):
                    col1, col2 = st.columns([2, 1])

                    with col1:
                        st.write(f"**Elevator:** {record['elevator_id']}")
                        st.write(f"**Urgency:** {record['urgency']}")
                        st.write(f"**Reason:** {record['reason']}")
                        st.write(f"**Recommended Date:** {record['recommended_date']}")
                        st.write(f"**Status:** {record['status']}")

                        if record.get("estimated_rul_hours"):
                            st.write(f"**RUL:** {record['estimated_rul_hours']:.1f} hours")

                    with col2:
                        st.write(f"**Created:** {record['created_at']}")
                        if record.get("completed_at"):
                            st.write(f"**Completed:** {record['completed_at']}")
                        if record.get("technician"):
                            st.write(f"**Technician:** {record['technician']}")

    # Create Maintenance tab
    with tab3:
        st.subheader("Create Manual Maintenance Entry")

        with st.form("create_maintenance_form"):
            elevator_id = st.text_input("Elevator ID*", value="elev-001")
            recommended_date = st.date_input("Recommended Date*")
            urgency = st.selectbox("Urgency*", options=["routine", "soon", "urgent", "immediate"])
            reason = st.text_area("Reason*", value="Manual maintenance request")

            submitted = st.form_submit_button("Create Maintenance Entry")

            if submitted:
                if not elevator_id or not reason:
                    st.error("Please fill in all required fields.")
                else:
                    try:
                        response = requests.post(
                            f"{API_BASE}/maintenance",
                            headers={"X-API-Key": "elevator-secret-key-123"},
                            json={
                                "elevator_id": elevator_id,
                                "recommended_date": recommended_date.isoformat(),
                                "urgency": urgency,
                                "reason": reason,
                            },
                            timeout=5,
                        )

                        if response.status_code == 201:
                            st.success("Maintenance entry created!")
                        else:
                            st.error(f"Failed to create: {response.status_code}")
                    except Exception as e:
                        st.error(f"Error: {e}")


if __name__ == "__main__":
    show_page()
