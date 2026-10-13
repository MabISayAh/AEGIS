import streamlit as st
from landing import render_landing, render_loading
from dashboard import render_dashboard
from analytics import render_dispatch_analytics

if "page" not in st.session_state:
    st.session_state["page"] = st.query_params.get("page", "landing")

st.set_page_config(
    page_title="AEGIS",
    page_icon="aegis_logo.png",
    layout="centered" if st.session_state["page"] in ("landing", "loading") else "wide",
)

if st.session_state["page"] == "landing":
    render_landing()

elif st.session_state["page"] == "loading":
    render_loading()

elif st.session_state["page"] == "analytics":
    render_dispatch_analytics()

else:
    render_dashboard()