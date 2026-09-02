import streamlit as st


def render_dashboard():
    # Inject Custom CSS
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Rethink+Sans:ital,wght@0,400..800;1,400..800&display=swap');

    /* Global Font & Background */
    html, body, [class*="css"], .stApp, p, div, span, label, h1, h2, h3, h4, h5, h6, li {
        font-family: 'Rethink Sans', sans-serif !important;
    }

    .stApp {
        background-color: #FAFAFA;
    }

    [data-testid="stHeader"] {
        display: none !important;
    }

    footer {
        display: none !important;
    }
    [data-testid="stFooter"] {
        display: none !important;
    }

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
        position: relative; /* anchor point for the absolutely-positioned back button below */
        padding-top: 1.25rem !important;
        padding-left: 1rem !important;
        padding-right: 1rem !important;
        padding-bottom: 0rem !important;
        max-width: 100%;
    }

    .st-key-back_btn {
        position: absolute !important;
        top: 1px !important;
        left: 20px !important;
        width: auto !important;
        z-index: 100000 !important;
    }
    /* The "* " here is needed for the same reason as the panel buttons below:
       Streamlit wraps the button label text in its own inner element that
       carries its own font-weight, which font-weight on <button> alone won't override */
    .st-key-back_btn button,
    .st-key-back_btn button * {
        background-color: transparent !important;
        border: none !important;
        box-shadow: none !important;
        color: #477B9E !important;
        font-weight: 800 !important;
        font-size: 16px !important;
        padding: 0 !important;
    }
    .st-key-back_btn button:hover,
    .st-key-back_btn button:hover * {
        color: #345E7A !important;
        background-color: transparent !important;
    }

    /* Panels & Cards */
    .title-box {
        background-color: #E4E5F1;
        color: #3E3F49;
        font-size: 24px;
        font-weight: 700;
        text-align: center;
        padding: 10px;
        border-radius: 6px;
        border: 1px solid #D1D5E0;
        margin-bottom: 15px;
        box-shadow: 0px 2px 2px rgba(0, 0, 0, 0.15);
    }

    .custom-panel {
        background-color: #E4E5F1;
        border: 1px solid #D1D5E0;
        border-radius: 6px;
        margin-bottom: 15px;
        overflow: hidden;
        box-shadow: 0px 2px 2px rgba(0, 0, 0, 0.15);
    }

    .panel-header {
        background-color: #E4E5F1;
        padding: 10px 15px;
        font-weight: 600;
        color: #3E3F49;
        font-size: 16px;
        border-bottom: 1px solid #FFFFFF;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }

    .help-icon {
        color: #3E3F49;
        font-size: 14px;
        border: 1px solid #3E3F49;
        border-radius: 50%;
        width: 18px;
        height: 18px;
        display: flex;
        align-items: center;
        justify-content: center;
        cursor: pointer;
    }

    .panel-body {
        padding: 15px;
        background-color: #E4E5F1;
    }

    .metric-label {
        font-size: 13px;
        color: #3E3F49;
        font-weight: 600;
        margin-bottom: 2px;
        margin-top: 10px;
    }
    .metric-label:first-child { margin-top: 0; }

    .metric-value {
        font-size: 14px;
        color: #477B9E;
        font-weight: 500;
        margin-left: 15px;
        margin-bottom: 5px;
    }

    /* Center Canvas */
    .canvas-placeholder {
        background-color: #F6F4F0;
        border: 1px solid #E0DED9;
        border-radius: 6px;
        height: 610px;
        width: 100%;
        margin-bottom: 15px;
        box-shadow: 0px 2px 2px rgba(0, 0, 0, 0.15);
    }

    /* Bottom Control Bar */
    .control-bar {
        background-color: #E4E5F1;
        border: 1px solid #D1D5E0;
        border-radius: 6px;
        padding: 10px 15px;
        display: flex;
        align-items: center;
        box-shadow: 0px 2px 2px rgba(0, 0, 0, 0.15);
    }
    .control-label {
        font-size: 16px;
        font-weight: 600;
        color: #3E3F49;
    }

    /* Right Column Specifics */
    .timer-box {
        background-color: #E4E5F1;
        border: 1px solid #D1D5E0;
        border-radius: 6px;
        text-align: center;
        font-size: 30px;
        font-weight: 600;
        color: #3E3F49;
        padding: 15px;
        margin-bottom: 15px;
        box-shadow: 0px 2px 2px rgba(0, 0, 0, 0.15);
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 10px;
    }
    .timer-icon {
        width: 26px;
        height: 26px;
        flex-shrink: 0;
    }

    /* Parameters panel body — targets the container via its key */
    .st-key-params_panel {
        background-color: #E4E5F1 !important;
        border: 1px solid #D1D5E0;
        border-top: 1px solid #FFFFFF;
        border-radius: 0 0 6px 6px;
        padding: 15px;
    }

    /* Groups the "Parameters" header + body into one visual card, sharing a single
       shadow — matching how .custom-panel works elsewhere. Without this wrapper,
       the header and body each cast their own shadow, and the header's shadow was
       bleeding down over the thin white divider line, washing it out. */
    .st-key-params_group {
        border-radius: 6px;
        overflow: hidden;
        margin-bottom: 15px;
        box-shadow: 0px 2px 2px rgba(0, 0, 0, 0.15);
    }

    /* Streamlit overrides for right column — the "* " selectors are needed because
       Streamlit wraps each label's text in its own inner <p>/<span>, which carries
       an explicit font-weight of its own. Setting font-weight only on the outer
       <label> doesn't override that inner element's own value. */
    div[data-testid="stSelectbox"] label,
    div[data-testid="stSlider"] label,
    div[data-testid="stSelectbox"] label *,
    div[data-testid="stSlider"] label * {
        font-size: 13px !important;
        color: #3E3F49 !important;
        font-weight: 700 !important;
    }
    div[data-testid="stSelectbox"] > div {
        min-height: 32px !important;
    }

    /* --- Recolor Streamlit's default red/orange accent to #477B9E ---
       Newer Streamlit themes read this CSS variable for sliders, focus rings,
       etc, so overriding it is the broadest fix. The explicit selectors below
       are a fallback in case a given element reads a hard-coded color instead. */
    :root {
        --primary-color: #477B9E;
    }

    /* Selectbox border, including on focus/open (this is usually where the
       red/orange outline shows up) */
    div[data-testid="stSelectbox"] > div > div {
        border-color: #D1D5E0 !important;
    }
    div[data-testid="stSelectbox"] > div > div:focus-within,
    div[data-baseweb="select"] > div:focus-within {
        border-color: #477B9E !important;
        box-shadow: 0 0 0 1px #477B9E !important;
    }

    /* Slider track (the thin bar) and its filled portion */
    div[data-testid="stSlider"] div[data-baseweb="slider"] > div {
        background-color: #D1D5E0 !important;
    }
    div[data-testid="stSlider"] div[data-baseweb="slider"] > div > div {
        background-color: #477B9E !important;
    }
    /* Slider thumb (the draggable circle) */
    div[data-testid="stSlider"] [role="slider"] {
        background-color: #477B9E !important;
        border-color: #477B9E !important;
    }
    /* Slider value label that floats above the thumb while dragging */
    div[data-testid="stSlider"] [data-testid="stThumbValue"] {
        color: #477B9E !important;
    }
    /* Slider tick labels (min/max numbers under the track) */
    div[data-testid="stSlider"] [data-testid="stTickBar"] {
        color: #3E3F49 !important;
    }
    /* Catch-all: Streamlit's default red accent (#FF4B4B) can show up via inline
       style OR a compiled class depending on version, which the selectors above
       may miss. This repaints ANY element inside the slider still carrying that
       exact red, wherever/however it's applied, without touching the grey track. */
    div[data-testid="stSlider"] [style*="255, 75, 75"],
    div[data-testid="stSlider"] [style*="ff4b4b" i] {
        background-color: #477B9E !important;
        border-color: #477B9E !important;
        color: #477B9E !important;
        fill: #477B9E !important;
    }

    /* Button customization — targeted via key, not :contains() (invalid CSS).
       Font-weight needs to target the inner label element too (Streamlit wraps
       button text in its own <p>/<div>), but box-shadow must stay on the OUTER
       button only — putting box-shadow on the inner text element as well cast a
       second shadow directly behind the text, causing that ghosting/double look. */
    .st-key-show_analytics_btn button {
        background-color: #477B9E !important;
        color: white !important;
        border: none !important;
        border-radius: 6px !important;
        box-shadow: 0px 2px 2px rgba(0, 0, 0, 0.15);
    }
    .st-key-show_analytics_btn button * {
        font-weight: 700 !important;
    }
    .st-key-run_btn button {
        background-color: #60CE56 !important;
        color: black !important;
        border: none !important;
        border-radius: 6px !important;
        box-shadow: 0px 2px 2px rgba(0, 0, 0, 0.15);
    }
    .st-key-run_btn button * {
        font-weight: 700 !important;
    }
    .st-key-reset_btn button {
        background-color: #FF6F6F !important;
        color: black !important;
        border: none !important;
        border-radius: 6px !important;
        box-shadow: 0px 2px 2px rgba(0, 0, 0, 0.15);
    }
    .st-key-reset_btn button * {
        font-weight: 700 !important;
    }

    .st-key-show_analytics_btn button:hover { background-color: #3b6685 !important; }
    .st-key-run_btn button:hover { background-color: #52a855 !important; }
    .st-key-reset_btn button:hover { background-color: #e55c5c !important; }

    </style>
    """, unsafe_allow_html=True)

    # --- TOP BAR ---
    st.markdown('<div class="top-window-bar"></div>', unsafe_allow_html=True)
    if st.button("← Back", key="back_btn"):
        st.session_state["page"] = "landing"
        st.rerun()

    # --- MAIN LAYOUT ---
    col_left, col_mid, col_right = st.columns([1.2, 3.2, 1.1], gap="small")

    # ==========================
    # LEFT COLUMN
    # ==========================
    with col_left:
        st.markdown('<div class="title-box">Baseco</div>', unsafe_allow_html=True)

        st.markdown("""
        <div class="custom-panel">
            <div class="panel-header">Performance <span class="help-icon">?</span></div>
            <div class="panel-body">
                <div class="metric-label">Primary Route Verified:</div>
                <div class="metric-value">15/15 Consecutive Agents</div>
                <div class="metric-label">Total Exploratory Agents:</div>
                <div class="metric-value">123 Agents</div>
                <div class="metric-label">Total Time:</div>
                <div class="metric-value">123123 seconds</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("""
        <div class="custom-panel">
            <div class="panel-header">Metrics <span class="help-icon">?</span></div>
            <div class="panel-body" style="padding-bottom: 5px;">
                <div class="metric-label">Primary Optimal Route Nodes:</div>
                <div class="metric-value">[A, D, E, F, G, H]</div>
                <div class="metric-label">Total Route Distance:</div>
                <div class="metric-value">1192 meters</div>
                <div class="metric-label">Estimated Time of Arrival (ETA):</div>
                <div class="metric-value">6 min and 40 sec</div>
                <div class="metric-label">Hazards Bypassed Count:</div>
                <div class="metric-value">5 hazards</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # These are placeholder values matching the Dispatch Analytics screen's
        # expected keys (see DEFAULT_RESULTS in analytics.py). When your backend
        # computes real results, replace this dict with real computed values
        # using these same keys — analytics.py doesn't need any changes.
        if st.button("Show Analytics", key="show_analytics_btn", use_container_width=True):
            st.session_state["sim_results"] = {
                "total_transit_time": "6 min and 39 sec",
                "bfp_benchmark_time": "9 min and 40 sec",
                "callout_text": "31% faster than benchmark, inside the golden hour window.",
                "this_sim_pct": 85,
                "bfp_benchmark_pct": 100,
                "path_distance_pct": 38,
                "path_complexity_pct": 52,
                "structural_risk_pct": 19,
                "nodes_visited": "14/14",
                "hazards_bypassed": "5",
                "route_hazard_score": "Low",
                "vehicle_entrapment_risk": "None",
            }
            st.session_state["page"] = "analytics"
            st.rerun()

    # ==========================
    # MIDDLE COLUMN
    # ==========================
    with col_mid:
        st.markdown('<div class="canvas-placeholder"></div>', unsafe_allow_html=True)

        ctrl_col1, ctrl_col2, ctrl_col3 = st.columns([1.5, 1, 1])
        with ctrl_col1:
            st.markdown(
                '<div style="background-color: #EAEBF3; border-radius: 6px; padding: 6px 15px; height: 100%; border: 1px solid #D1D5E0; display:flex; align-items:center; box-shadow: 0px 2px 2px rgba(0, 0, 0, 0.15);"><span class="control-label">Simulation Controls</span></div>',
                unsafe_allow_html=True)
        with ctrl_col2:
            st.button("Run", key="run_btn", use_container_width=True)
        with ctrl_col3:
            st.button("Reset", key="reset_btn", use_container_width=True)

    # ==========================
    # RIGHT COLUMN
    # ==========================
    with col_right:
        # Timer icon and value are kept as separate elements on purpose: when you
        # wire up the actual backend timer later, you only need to change the
        # "00:00.0" string below (e.g. render it from a variable) — the icon markup
        # never needs to be touched.
        st.markdown("""
        <div class="timer-box">
            <svg class="timer-icon" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <circle cx="12" cy="13" r="8" stroke="#477B9E" stroke-width="2"/>
                <path d="M12 9v4l3 2" stroke="#477B9E" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                <path d="M9 2h6" stroke="#477B9E" stroke-width="2" stroke-linecap="round"/>
                <path d="M12 2v3" stroke="#477B9E" stroke-width="2" stroke-linecap="round"/>
            </svg>
            <span id="timer-value">00:00.0</span>
        </div>
        """, unsafe_allow_html=True)

        # Wraps header + body together so they share ONE shadow (see .st-key-params_group)
        with st.container(key="params_group"):
            st.markdown("""
            <div class="panel-header" style="border: 1px solid #D1D5E0; border-radius: 6px 6px 0 0; border-bottom: none;">
                Parameters <span class="help-icon">?</span>
            </div>
            """, unsafe_allow_html=True)

            # Parameters panel body — real container, styled via .st-key-params_panel in the CSS above
            with st.container(key="params_panel"):
                options_0_to_1 = ["0.0", "0.1", "0.2", "0.3", "0.4", "0.5", "0.6", "0.7", "0.8", "0.9", "1.0"]

                st.selectbox("Distance (D)", options_0_to_1)
                st.selectbox("Path Complexity (C)", options_0_to_1)
                st.selectbox("Structural Risk (R)", options_0_to_1)

                p_col1, p_col2 = st.columns(2)
                with p_col1:
                    st.selectbox("Pmin", options_0_to_1)
                with p_col2:
                    st.selectbox("Pmax", options_0_to_1)

                st.slider("Scout Agents", min_value=50, max_value=500, value=50)
                st.slider("Carrier Agents", min_value=1, max_value=10, value=1)