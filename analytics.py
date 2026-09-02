import streamlit as st

# Placeholder simulation results. Once the backend is wired up, populate
# st.session_state['sim_results'] with real values using these exact keys —
# nothing else in this file needs to change.
DEFAULT_RESULTS = {
    "total_transit_time": "6 min and 39 sec",
    "bfp_benchmark_time": "9 min and 40 sec",
    "callout_text": "31% faster than benchmark, inside the golden hour window.",

    # Progress bar fill percentages (0-100) for the transit-time comparison
    "this_sim_pct": 85,
    "bfp_benchmark_pct": 100,

    # Progress bar fill percentages (0-100) for the route-risk panel
    "path_distance_pct": 38,
    "path_complexity_pct": 52,
    "structural_risk_pct": 19,

    # Right-hand stat list
    "nodes_visited": "14/14",
    "hazards_bypassed": "5",
    "route_hazard_score": "Low",
    "vehicle_entrapment_risk": "None",
}


def _progress_bar(fill_pct, fill_color, track_color="#FFFFFF", height="10px"):
    """Returns the HTML for a single progress bar track + fill, as one line.
    IMPORTANT: this must stay a single line with no leading whitespace/newlines —
    a leading blank line followed by indented HTML gets misread by Markdown as
    an indented code block, causing the raw HTML to render as visible text
    instead of being parsed (this bit us once already)."""
    return f'<div style="background-color:{track_color}; border-radius:6px; height:{height}; overflow:hidden;"><div style="width:{fill_pct}%; height:100%; background-color:{fill_color}; border-radius:6px;"></div></div>'


def render_dispatch_analytics():
    # Inject Custom CSS
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Rethink+Sans:ital,wght@0,400..800;1,400..800&display=swap');

    html, body, [class*="css"], .stApp, p, div, span, label, h1, h2, h3, h4, h5, h6, li {
        font-family: 'Rethink Sans', sans-serif !important;
    }

    .stApp {
        background-color: #FAFAFA;
    }

    [data-testid="stHeader"] { display: none !important; }
    footer { display: none !important; }
    [data-testid="stFooter"] { display: none !important; }

    .top-window-bar {
        position: fixed;
        top: 0; left: 0; width: 100%; height: 35px;
        background-color: #E4E5F1;
        border-bottom: 1px solid #cbd5e1;
        z-index: 99999;
        display: flex;
        align-items: center;
        padding-left: 15px;
        box-shadow: 0px 2px 2px rgba(0, 0, 0, 0.15);
    }

    .block-container {
        position: relative; /* anchor point for the absolutely-positioned Close button */
        padding-top: 1.25rem !important;
        padding-left: 1rem !important;
        padding-right: 1rem !important;
        padding-bottom: 0.25rem !important;
        max-width: 100%;
    }

    /* Close button — same positioning trick as the Dashboard's back button */
    .st-key-close_analytics_btn {
        position: absolute !important;
        top: 1px !important;
        left: 20px !important;
        width: auto !important;
        z-index: 100000 !important;
    }
    .st-key-close_analytics_btn button,
    .st-key-close_analytics_btn button * {
        background-color: transparent !important;
        border: none !important;
        box-shadow: none !important;
        color: #3E3F49 !important;
        font-weight: 800 !important;
        font-size: 16px !important;
        padding: 0 !important;
    }
    .st-key-close_analytics_btn button:hover,
    .st-key-close_analytics_btn button:hover * {
        color: #000000 !important;
        background-color: transparent !important;
    }

    /* Page title */
    .analytics-title {
        font-size: 48px;
        font-weight: 800;
        color: #477B9E;
        text-align: center;
        letter-spacing: 1px;
        margin: 5px 0 15px 0;
    }

    /* Generic card: header + body, single shadow, white divider line between
       them — same pattern as .custom-panel on the Dashboard */
    .analytics-panel {
        background-color: #E4E5F1;
        border: 1px solid #D1D5E0;
        border-radius: 8px;
        overflow: hidden;
        box-shadow: 0px 2px 2px rgba(0, 0, 0, 0.15);
        margin-bottom: 15px;
        flex: 1; /* fills the height of .analytics-col below when the row's two columns differ in content height */
    }
    .analytics-panel-header {
        padding: 10px 18px;
        font-size: 15px;
        font-weight: 600;
        color: #3E3F49;
        border-bottom: 1px solid #FFFFFF;
    }
    .analytics-panel-body {
        padding: 18px;
    }
    .analytics-panel-value {
        font-size: 34px;
        font-weight: 700;
        color: #477B9E;
    }

    /* Green callout banner */
    .analytics-callout {
        background-color: #60CE56;
        border-radius: 8px;
        padding: 12px 20px;
        display: flex;
        align-items: center;
        gap: 12px;
        margin-bottom: 15px;
        box-shadow: 0px 2px 2px rgba(0, 0, 0, 0.15);
    }
    .analytics-callout-icon {
        width: 22px;
        height: 22px;
        flex-shrink: 0;
    }
    .analytics-callout-text {
        font-size: 15px;
        font-weight: 600;
        color: #1E1E1E;
    }

    /* Progress-bar row: label + value on top, bar underneath */
    .analytics-bar-row {
        margin-bottom: 18px;
    }
    .analytics-bar-row:last-child {
        margin-bottom: 0;
    }
    .analytics-bar-row-top {
        display: flex;
        justify-content: space-between;
        align-items: baseline;
        margin-bottom: 6px;
    }
    .analytics-bar-label {
        font-size: 15px;
        font-weight: 600;
        color: #3E3F49;
    }
    .analytics-bar-value {
        font-size: 15px;
        font-weight: 700;
        color: #477B9E;
    }

    /* Right-hand stat list rows, divided by white lines */
    .analytics-stat-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 12px 18px;
        border-bottom: 1px solid #FFFFFF;
    }
    .analytics-stat-row:last-child {
        border-bottom: none;
    }
    .analytics-stat-label {
        font-size: 15px;
        font-weight: 600;
        color: #3E3F49;
    }
    .analytics-stat-value {
        font-size: 15px;
        font-weight: 700;
        color: #477B9E;
    }

    /* Two-column row helper */
    .analytics-row {
        display: flex;
        gap: 15px;
    }
    .analytics-col {
        flex: 1;
        min-width: 0;
        display: flex;
        flex-direction: column;
    }
    /* Removes the trailing margin-bottom on the last row's panels, since that
       leftover 15px was just enough to push total page height past the
       viewport and trigger a scrollbar even though everything visually fits */
    .analytics-row-last .analytics-panel {
        margin-bottom: 0;
    }
    </style>
    """, unsafe_allow_html=True)

    # --- TOP BAR + CLOSE BUTTON ---
    st.markdown('<div class="top-window-bar"></div>', unsafe_allow_html=True)
    if st.button("✕ Close", key="close_analytics_btn"):
        st.session_state["page"] = "dashboard"
        st.rerun()

    # --- DATA ---
    # Pulls whatever the Dashboard stored when "Show Analytics" was pressed.
    # Falls back to placeholder values if this screen is opened directly.
    results = st.session_state.get("sim_results", DEFAULT_RESULTS)

    # --- TITLE ---
    st.markdown('<div class="analytics-title">DISPATCH ANALYTICS</div>', unsafe_allow_html=True)

    # --- ROW 1: Total Transit Time / BFP Benchmark ---
    st.markdown(f"""
    <div class="analytics-row">
        <div class="analytics-col">
            <div class="analytics-panel">
                <div class="analytics-panel-header">Total Transit Time</div>
                <div class="analytics-panel-body">
                    <div class="analytics-panel-value">{results['total_transit_time']}</div>
                </div>
            </div>
        </div>
        <div class="analytics-col">
            <div class="analytics-panel">
                <div class="analytics-panel-header">BFP Benchmark</div>
                <div class="analytics-panel-body">
                    <div class="analytics-panel-value">{results['bfp_benchmark_time']}</div>
                </div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # --- GREEN CALLOUT BANNER ---
    st.markdown(f"""
    <div class="analytics-callout">
        <svg class="analytics-callout-icon" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <circle cx="12" cy="13" r="9" fill="#1E1E1E"/>
            <path d="M12 8v5l3.5 2" stroke="#60CE56" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
        <span class="analytics-callout-text">{results['callout_text']}</span>
    </div>
    """, unsafe_allow_html=True)

    # --- ROW 2: This Simulation vs BFP Benchmark progress bars ---
    st.markdown(f"""
    <div class="analytics-panel">
        <div class="analytics-panel-body">
            <div class="analytics-bar-row">
                <div class="analytics-bar-row-top">
                    <span class="analytics-bar-label">This simulation</span>
                    <span class="analytics-bar-value">{results['total_transit_time']}</span>
                </div>
                {_progress_bar(results['this_sim_pct'], "#477B9E", height="12px")}
            </div>
            <div class="analytics-bar-row">
                <div class="analytics-bar-row-top">
                    <span class="analytics-bar-label">BFP Benchmark</span>
                    <span class="analytics-bar-value">{results['bfp_benchmark_time']}</span>
                </div>
                {_progress_bar(results['bfp_benchmark_pct'], "#B4B4B4", height="12px")}
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # --- ROW 3: Route risk bars / stat list ---
    st.markdown(f"""
    <div class="analytics-row analytics-row-last">
        <div class="analytics-col">
            <div class="analytics-panel">
                <div class="analytics-panel-body">
                    <div class="analytics-bar-row">
                        <div class="analytics-bar-row-top">
                            <span class="analytics-bar-label">Path Distance</span>
                            <span class="analytics-bar-value">{results['path_distance_pct']}%</span>
                        </div>
                        {_progress_bar(results['path_distance_pct'], "#FF6F6F", height="8px")}
                    </div>
                    <div class="analytics-bar-row">
                        <div class="analytics-bar-row-top">
                            <span class="analytics-bar-label">Path Complexity</span>
                            <span class="analytics-bar-value">{results['path_complexity_pct']}%</span>
                        </div>
                        {_progress_bar(results['path_complexity_pct'], "#FFE17D", height="8px")}
                    </div>
                    <div class="analytics-bar-row">
                        <div class="analytics-bar-row-top">
                            <span class="analytics-bar-label">Structural Risk</span>
                            <span class="analytics-bar-value">{results['structural_risk_pct']}%</span>
                        </div>
                        {_progress_bar(results['structural_risk_pct'], "#477B9E", height="8px")}
                    </div>
                </div>
            </div>
        </div>
        <div class="analytics-col">
            <div class="analytics-panel">
                <div class="analytics-stat-row">
                    <span class="analytics-stat-label">Nodes Visited</span>
                    <span class="analytics-stat-value">{results['nodes_visited']}</span>
                </div>
                <div class="analytics-stat-row">
                    <span class="analytics-stat-label">Hazards Bypassed</span>
                    <span class="analytics-stat-value">{results['hazards_bypassed']}</span>
                </div>
                <div class="analytics-stat-row">
                    <span class="analytics-stat-label">Route Hazard Score</span>
                    <span class="analytics-stat-value">{results['route_hazard_score']}</span>
                </div>
                <div class="analytics-stat-row">
                    <span class="analytics-stat-label">Vehicle Entrapment Risk</span>
                    <span class="analytics-stat-value">{results['vehicle_entrapment_risk']}</span>
                </div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)