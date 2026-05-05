"""Streamlit Dashboard — Elevator Predictive Maintenance.

Entry point for the Streamlit dashboard with three pages:
1. Fleet Overview — list all elevators with status badges
2. Live Monitor — real-time charts for selected elevator
3. Alerts & Maintenance — view and manage alerts/maintenance
"""
import streamlit as st

# Page config
st.set_page_config(
    page_title="Elevator PDM Dashboard",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Sidebar navigation
st.sidebar.title("🏢 Elevator PDM")

page = st.sidebar.radio(
    "Navigate",
    ["Fleet Overview", "Live Monitor", "Alerts & Maintenance"],
)

# Load pages
if page == "Fleet Overview":
    from elevator_pdm.presentation.dashboard.pages.fleet import show_page
    show_page()
elif page == "Live Monitor":
    from elevator_pdm.presentation.dashboard.pages.live import show_page
    show_page()
elif page == "Alerts & Maintenance":
    from elevator_pdm.presentation.dashboard.pages.alerts import show_page
    show_page()
