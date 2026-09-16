import json
import random
import time

import matplotlib.pyplot as plt
import streamlit as st

from simulation_backend import (
    run_full_simulation, FIRETRUCK_SPEED_KMH, FIRETRUCK_SPEED_MPS, FIRE_STATION_LAT, FIRE_STATION_LON, latlon_to_utm,
    load_graph, build_adjacency, build_edge_lookup, get_largest_component_nodes,
    nearest_node, compute_baseline_corridor_edges, pick_random_hazard_edges,
    DEFAULT_SCOUTING_PHASE_DURATION_S,
)
from plotting import (
    plot_graph_with_route, plot_preview, plot_scout_progress,
    create_scout_canvas, update_scout_frame,
    create_carrier_canvas, update_carrier_frame,
)

GRAPH_FILE = "baseco_osm_graph_scored.json"
STATION_X, STATION_Y = latlon_to_utm(FIRE_STATION_LAT, FIRE_STATION_LON)


@st.cache_data
def get_graph_bounds(path):
    with open(path) as f:
        data = json.load(f)
    xs = [n["utm_x"] for n in data["nodes"].values()]
    ys = [n["utm_y"] for n in data["nodes"].values()]
    return min(xs), max(xs), min(ys), max(ys)


@st.cache_data
def load_graph_for_preview(path):
    with open(path) as f:
        data = json.load(f)
    return data["nodes"], data["edges"]


@st.cache_data
def load_graph_structures(path):
    """Adjacency/edge-lookup/largest-component data, precomputed once and
    cached -- the same shape of data run_full_simulation builds internally,
    reused here so the preview can mirror its hazard-picking logic exactly."""
    nodes, edges = load_graph(path)
    adj = build_adjacency(edges)
    lookup = build_edge_lookup(edges)
    largest_nodes, num_components = get_largest_component_nodes(adj)
    return nodes, lookup, largest_nodes


def compute_preview_hazards(fire_x, fire_y, num_random_hazards, seed):
    """Mirrors the hazard-picking steps at the top of
    simulation_backend.run_full_simulation() -- same corridor computation,
    same pick_random_hazard_edges() call, same seed -- so whatever the
    preview shows is exactly what Run will actually use, as long as the fire
    position, hazard count, and seed haven't changed since."""
    if num_random_hazards <= 0:
        return set()
    nodes, lookup, largest_nodes = load_graph_structures(GRAPH_FILE)
    target_node = nearest_node(nodes, fire_x, fire_y, largest_nodes)
    start_node = nearest_node(nodes, STATION_X, STATION_Y, largest_nodes)
    corridor_edges = compute_baseline_corridor_edges(nodes, lookup, start_node, target_node, hop_radius=1)
    return pick_random_hazard_edges(
        lookup, num_random_hazards, corridor_edges=corridor_edges,
        exclude_nodes={start_node, target_node}, seed=seed,
    )


def format_timer(seconds):
    minutes = int(seconds // 60)
    secs = seconds % 60
    return f"{minutes:02d}:{secs:04.1f}"


def render_timer(slot, seconds=None):
    display = format_timer(seconds) if seconds is not None else "00:00.0"
    slot.markdown(f"""
    <div class="timer-box">
        <svg class="timer-icon" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <circle cx="12" cy="13" r="8" stroke="#477B9E" stroke-width="2"/>
            <path d="M12 9v4l3 2" stroke="#477B9E" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            <path d="M9 2h6" stroke="#477B9E" stroke-width="2" stroke-linecap="round"/>
            <path d="M12 2v3" stroke="#477B9E" stroke-width="2" stroke-linecap="round"/>
        </svg>
        <span id="timer-value">{display}</span>
    </div>
    """, unsafe_allow_html=True)


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

    /* Keep the whole dashboard within one viewport -- long parameter/metric
       lists scroll WITHIN their own panel instead of pushing the page height
       past the screen and forcing an outer scrollbar. */
    html, body { overflow: hidden !important; }
    .stApp { height: 100vh; overflow: hidden; }
    .block-container { max-height: 100vh; overflow: hidden; }
    .st-key-params_group, .st-key-params_panel {
        max-height: calc(100vh - 140px);
        overflow-y: auto;
    }

    /* st.caption() renders at a low default opacity/gray that blends into
       the panel's light background -- boost it for the "Start point is
       fixed..." note at the bottom of Parameters. */
    .st-key-params_panel [data-testid="stCaptionContainer"],
    .st-key-params_panel small {
        color: #3E3F49 !important;
        opacity: 1 !important;
        font-weight: 500 !important;
        font-size: 12px !important;
    }

    /* Left column (title, Run/Reset, Performance/Metrics panels, Analytics
       button) can grow tall once a simulation has run, so let it scroll
       independently instead of overflowing past the viewport. This targets
       the column div itself -- rather than a single st.container key -- since
       the left column's content is written across two separate "with
       col_left:" blocks (buttons before the map, results after), and both
       still land in the same underlying column element. */
    div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"]:nth-child(1) {
        max-height: calc(100vh - 60px);
        overflow-y: auto;
        padding-right: 6px;
    }

    /* --- Canvas height clamp ---
       The plotted matplotlib figure has no intrinsic height limit of its own.
       Without this, a tall figure could push other content below the
       viewport, where it gets clipped by the `overflow: hidden` rules above
       instead of scrolling into view. Clamping this wrapper to (roughly) the
       full available height -- matching the right column's own clamp --
       and scaling the image to fit inside it lets the map take up nearly the
       whole screen while still guaranteeing nothing gets cut off. */
    .st-key-canvas_wrapper {
        position: relative;
        height: calc(100vh - 90px);
        max-height: calc(100vh - 90px);
        overflow: hidden;
        border-radius: 6px;
        margin-bottom: 15px;
    }
    .st-key-canvas_wrapper [data-testid="stVerticalBlockBorderWrapper"],
    .st-key-canvas_wrapper > div {
        height: 100%;
    }
    .st-key-canvas_wrapper img {
        height: 100%;
        width: 100% !important;
        object-fit: contain;
        object-position: center;
    }
    /* Custom "Scouts exploring the network..." overlay, replacing
       st.spinner(). st.spinner's internal markup is nested in a way that,
       in this Streamlit version, was collapsing to a near-zero-width box
       inside the flex canvas_wrapper -- wrapping the text one letter per
       line. Building the overlay ourselves with plain HTML/CSS sidesteps
       that entirely, and lets us park it at the bottom of the map instead
       of dead-center covering the action. */
    .running-overlay {
        position: absolute;
        bottom: 16px;
        left: 50%;
        transform: translateX(-50%);
        z-index: 10;
        background-color: rgba(250, 250, 250, 0.92);
        padding: 8px 18px;
        border-radius: 20px;
        box-shadow: 0px 2px 6px rgba(0, 0, 0, 0.25);
        font-weight: 600;
        font-size: 14px;
        color: #3E3F49;
        white-space: nowrap;
        display: flex;
        align-items: center;
        gap: 8px;
    }
    .running-overlay .running-dot {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        background-color: #477B9E;
        flex-shrink: 0;
        animation: running-pulse 1s ease-in-out infinite;
    }
    @keyframes running-pulse {
        0%, 100% { opacity: 0.25; }
        50% { opacity: 1; }
    }

    /* Simulation Controls block, now stacked in the (narrower) left column
       instead of a horizontal row above the canvas. */
    .st-key-sim_controls_group {
        margin-bottom: 0;
    }
    .st-key-sim_controls_group .control-label-box {
        background-color: #EAEBF3;
        border-radius: 6px;
        padding: 6px 15px;
        border: 1px solid #D1D5E0;
        display: flex;
        align-items: center;
        box-shadow: 0px 2px 2px rgba(0, 0, 0, 0.15);
        margin-bottom: 15px;
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
    /* Shuffle-hazards button, now matching show_analytics_btn's solid style
       exactly -- same background, same hover darken -- instead of the
       outline treatment it had before. */
    .st-key-shuffle_hazards_btn button {
        background-color: #477B9E !important;
        color: white !important;
        border: none !important;
        border-radius: 6px !important;
        box-shadow: 0px 2px 2px rgba(0, 0, 0, 0.15);
    }
    .st-key-shuffle_hazards_btn button * {
        font-weight: 700 !important;
        font-size: 13px !important;
    }

    .st-key-show_analytics_btn button:hover { background-color: #3b6685 !important; }
    .st-key-run_btn button:hover { background-color: #52a855 !important; }
    .st-key-reset_btn button:hover { background-color: #e55c5c !important; }
    .st-key-shuffle_hazards_btn button:hover { background-color: #3b6685 !important; }

    </style>
    """, unsafe_allow_html=True)

    # --- TOP BAR ---
    st.markdown('<div class="top-window-bar"></div>', unsafe_allow_html=True)
    if st.button("← Back", key="back_btn"):
        st.session_state["page"] = "landing"
        st.rerun()

    # --- MAIN LAYOUT ---
    col_left, col_mid, col_right = st.columns([1.2, 3.6, 1.0], gap="small")

    # NOTE ON ORDER: these blocks are written
    #   col_right -> col_left (part 1) -> col_mid -> col_left (part 2)
    # in the CODE, even though they render LEFT -> MIDDLE -> RIGHT on screen.
    # Streamlit places each block's output into its column regardless of code
    # order, and a column's "with" block can be re-entered multiple times --
    # content just stacks in the order it was written. What matters is data
    # dependencies: col_right's parameter widgets are captured before col_mid
    # needs them; col_left's Run/Reset buttons are captured before col_mid's
    # simulation logic needs to know their state; and col_mid's simulation
    # results exist in session_state before col_left's part 2 displays them.

    # ==========================
    # RIGHT COLUMN (parameters -- captured first so Run can use them)
    # ==========================
    with col_right:
        timer_slot = st.empty()
        render_timer(timer_slot)

        with st.container(key="params_group"):
            st.markdown("""
            <div class="panel-header" style="border: 1px solid #D1D5E0; border-radius: 6px 6px 0 0; border-bottom: none;">
                Parameters
            </div>
            """, unsafe_allow_html=True)

            with st.container(key="params_panel"):
                options_0_to_1 = ["0.0", "0.1", "0.2", "0.3", "0.4", "0.5", "0.6", "0.7", "0.8", "0.9", "1.0"]

                # Every widget below now has an EXPLICIT key. Without one,
                # Streamlit auto-generates a key based on position/args, which
                # is NOT reliably preserved across our custom session_state
                # page-router (Dashboard -> Analytics -> Dashboard) -- since
                # these widgets simply don't execute at all while the
                # Analytics page is showing, an unkeyed widget can silently
                # snap back to its hardcoded default on return, which then
                # made result_matches_sliders go False and the canvas fall
                # back to an empty preview instead of the real results.
                dist_w = float(st.selectbox("Distance [D]", options_0_to_1, index=4, key="dist_w_select"))
                complexity_w = float(st.selectbox("Path Complexity [C]", options_0_to_1, index=3, key="complexity_w_select"))
                # Escaping the (R) so Streamlit doesn't render it as a trademark symbol
                risk_w = float(st.selectbox("Structural Risk [R]", options_0_to_1, index=3, key="risk_w_select"))

                p_col1, p_col2 = st.columns(2)
                with p_col1:
                    pmin_w = float(st.selectbox("Pmin", options_0_to_1, index=1, key="pmin_w_select"))
                with p_col2:
                    pmax_w = float(st.selectbox("Pmax", options_0_to_1, index=9, key="pmax_w_select"))

                # Scout max unchanged, min raised to 100
                scout_agents = st.slider("Scout Agents", min_value=100, max_value=500, value=100, key="scout_agents_slider")
                # Carrier max constrained to 10
                carrier_agents = st.slider("Carrier Agents", min_value=1, max_value=10, value=1, key="carrier_agents_slider")

                st.markdown('<div class="metric-label" style="margin-top:8px;">Fire Simulation</div>', unsafe_allow_html=True)
                enable_fire = st.checkbox("Enable fire hazard", value=True, key="enable_fire_checkbox")
                fire_x_pct = st.slider("Fire Origin X (%)", 0, 100, 50, disabled=not enable_fire, key="fire_x_pct_slider")
                fire_y_pct = st.slider("Fire Origin Y (%)", 0, 100, 50, disabled=not enable_fire, key="fire_y_pct_slider")
                spread_rate_m_per_min = st.slider(
                    "Fire Spread Rate (m/min)", 0.1, 2.5, 1.0, step=0.1, disabled=not enable_fire, key="spread_rate_slider"
                )

                st.markdown('<div class="metric-label" style="margin-top:8px;">Random Hazards</div>', unsafe_allow_html=True)
                enable_random_hazards = st.checkbox("Enable random hazards (debris / collapsed structures)", value=False, key="enable_random_hazards_checkbox")
                num_random_hazards = st.slider(
                    "Number of random hazards", 0, 15, 5, disabled=not enable_random_hazards, key="num_random_hazards_slider"
                )
                # Stable across reruns (so the preview doesn't flicker every
                # time a slider moves) until the user explicitly shuffles, or
                # until this is the very first render of the session.
                if "hazard_seed" not in st.session_state:
                    st.session_state["hazard_seed"] = random.randint(0, 2**31 - 1)
                if st.button("Shuffle hazard positions", key="shuffle_hazards_btn", disabled=not enable_random_hazards, width='stretch'):
                    st.session_state["hazard_seed"] = random.randint(0, 2**31 - 1)

                st.caption(f"Start point is fixed at the Baseco Fire Station. Firetruck speed fixed at {FIRETRUCK_SPEED_KMH} km/h.")

    # ==========================
    # LEFT COLUMN, PART 1 (title + Run/Reset controls -- rendered before
    # col_mid, since col_mid's simulation logic needs to know whether Run
    # was clicked this render. Streamlit lets a column's "with" block be
    # re-entered later for part 2, and content stacks in the order written.)
    # ==========================
    with col_left:
        st.markdown('<div class="title-box">Baseco</div>', unsafe_allow_html=True)

        with st.container(key="sim_controls_group"):
            st.markdown(
                '<div class="control-label-box"><span class="control-label">Simulation Controls</span></div>',
                unsafe_allow_html=True)
            run_clicked = st.button("Run", key="run_btn", width='stretch')
            reset_clicked = st.button("Reset", key="reset_btn", width='stretch')

        if reset_clicked:
            st.session_state.pop("aco_results", None)

    # ==========================
    # MIDDLE COLUMN (canvas, full-height -- uses params captured above and
    # the run/reset state captured in the left column just above)
    # ==========================
    with col_mid:
        # Wrapped in a height-clamped container (see .st-key-canvas_wrapper CSS
        # above) so the map can fill nearly the whole screen while still
        # guaranteeing nothing gets cut off by the page's overflow:hidden.
        # Kept as a variable (rather than only using "with ... :" once) so the
        # spinner below can be appended into the *same* wrapper later --
        # that's what lets the CSS position it as a centered overlay on top
        # of the map instead of as a block element that gets pushed down.
        canvas_wrapper = st.container(key="canvas_wrapper")
        with canvas_wrapper:
            canvas_slot = st.empty()  # reserved now, filled in further down
            loading_slot = st.empty()  # the "Scouts exploring..." overlay lives here

        # Computed every render (not just on Run click) so the preview can
        # track the sliders live, before you commit to running the sim.
        min_x, max_x, min_y, max_y = get_graph_bounds(GRAPH_FILE)
        fire_x = min_x + (fire_x_pct / 100) * (max_x - min_x)
        fire_y = min_y + (fire_y_pct / 100) * (max_y - min_y)

        if run_clicked:
            weight_sum = dist_w + complexity_w + risk_w
            if weight_sum == 0:
                st.error("Distance, Complexity, and Risk weights can't all be 0.")
            else:
                # normalize weights to sum to 1, since desirability() expects that
                w1, w2, w3 = dist_w / weight_sum, risk_w / weight_sum, complexity_w / weight_sum
                nodes_for_anim, edges_for_anim = load_graph_for_preview(GRAPH_FILE)

                # start/target aren't known until run_full_simulation picks
                # them (fixed fire-station start, nearest-node-to-fire
                # target) -- stash them the first time the callback fires
                # so every subsequent frame can still draw the markers.
                #
                # The base graph (every road edge) is drawn ONCE here via
                # create_scout_canvas, and every frame afterward reuses the
                # same fig/ax via update_scout_frame -- which only touches
                # the handful of artists that actually change (routes,
                # markers, title, legend). That's what makes it cheap
                # enough to render every single Scout, not just some.
                # The exact random-hazard edges THIS run will use -- same
                # deterministic hazard-picking logic and seed
                # run_full_simulation uses internally (see
                # compute_preview_hazards's own docstring). Computed once,
                # up front, and drawn into both animation canvases' static
                # base layer below, so hazards are visible DURING the live
                # Scout/Carrier animation, not just in the pre-Run preview
                # and the post-Run results map.
                live_hazard_edges = compute_preview_hazards(
                    fire_x, fire_y,
                    num_random_hazards if enable_random_hazards else 0,
                    st.session_state["hazard_seed"],
                )

                anim_fig, anim_ax, anim_base_handles = create_scout_canvas(
                    nodes_for_anim, edges_for_anim, hazard_edges=live_hazard_edges,
                )
                anim_state = {"start_node": None, "target_node": None, "dynamic_artists": None}

                # Live stopwatch: starts now (Scout phase kickoff) and keeps
                # climbing every frame -- Scout AND Carrier -- until the
                # FIRST Carrier to reach the target fires its "reached"
                # callback, at which point it freezes for good. Later
                # Carriers still arriving (or failing) after that don't
                # move it anymore.
                # SIMULATED elapsed time, not real wall-clock time. Scouts add a
                # small fixed amount per agent (so displaying up to 500 Scouts
                # stays fast/meaningful regardless of real render time), and
                # Carriers add real travel time computed from actual distance
                # covered at the fixed firetruck speed -- the same formula the
                # ETA metric uses -- so a Carrier that completes its route shows
                # a timer value that matches that route's ETA exactly.
                timer_state = {"simulated_elapsed_s": 0.0, "frozen_at": None}
                SCOUT_TIMER_INCREMENT_S = 0.002  # 2ms of simulated time per Scout

                def tick_timer(delta_s):
                    if timer_state["frozen_at"] is not None:
                        return
                    timer_state["simulated_elapsed_s"] += delta_s
                    render_timer(timer_slot, timer_state["simulated_elapsed_s"])

                def on_scout(scout_number, num_scouts, scout_route, scout_status,
                             scout_traversed_edges, verified_routes, best_route,
                             elapsed_s=0.0):
                    if scout_route and anim_state["start_node"] is None:
                        anim_state["start_node"] = scout_route[0]
                        anim_state["target_node"] = scout_route[-1]
                    loading_slot.markdown(
                        f'<div class="running-overlay"><span class="running-dot"></span>'
                        f'Scout {scout_number}/{num_scouts} exploring the network...</div>',
                        unsafe_allow_html=True,
                    )
                    # Live fire radius at this exact point in the Scout
                    # phase -- same closed-form the backend's FireModel
                    # uses (radius = spread_rate_mps * elapsed_s), computed
                    # here instead of threading a FireModel instance
                    # through the callback. Only meaningful if fire is on.
                    live_fire_radius_m = (
                        (spread_rate_m_per_min / 60) * elapsed_s if enable_fire else None
                    )
                    anim_state["dynamic_artists"] = update_scout_frame(
                        anim_fig, anim_ax, anim_base_handles, nodes_for_anim,
                        scout_number, num_scouts,
                        scout_route, verified_routes, best_route,
                        start_node=anim_state["start_node"],
                        target_node=anim_state["target_node"],
                        scout_status=scout_status,
                        dynamic_artists=anim_state["dynamic_artists"],
                        fire_origin_xy=(fire_x, fire_y) if enable_fire else None,
                        fire_radius_m=live_fire_radius_m,
                    )
                    with canvas_slot.container():
                        st.pyplot(anim_fig, width='stretch')
                    tick_timer(SCOUT_TIMER_INCREMENT_S)
                    time.sleep(0.005)  # small pause per Scout so the animation is actually visible

                # Carrier phase reuses the Scout phase's start/target (both
                # fixed -- Fire Station and nearest-node-to-fire) but gets
                # its OWN canvas/fig, so the Scout swarm's final frame stays
                # on screen as the last thing painted before Carriers take
                # over, instead of the two phases fighting over one canvas.
                carrier_fig, carrier_ax, carrier_base_handles = create_carrier_canvas(
                    nodes_for_anim, edges_for_anim, hazard_edges=live_hazard_edges,
                )
                carrier_anim_state = {"dynamic_artists": None}

                # Edge-distance lookup, reused to compute each Carrier's real
                # cumulative distance traveled along ITS committed route --
                # same lookup shape run_full_simulation builds internally.
                _, carrier_edge_lookup, _ = load_graph_structures(GRAPH_FILE)

                def on_carrier(carrier_id, carrier_number, num_carriers, rank, route,
                                current_node, step, total_steps, status,
                                carriers_completed, top_routes, elapsed_s=0.0):
                    loading_slot.markdown(
                        f'<div class="running-overlay"><span class="running-dot"></span>'
                        f'Carrier {carrier_number}/{num_carriers} ({carrier_id}, rank {rank}) '
                        f'en route... ({carriers_completed}/{num_carriers} arrived)</div>',
                        unsafe_allow_html=True,
                    )
                    # Same live fire radius computation as the Scout phase --
                    # the fire keeps spreading while Carriers travel, so this
                    # keeps growing across the whole Carrier phase too,
                    # instead of freezing at whatever it was when scouting ended.
                    live_fire_radius_m = (
                        (spread_rate_m_per_min / 60) * elapsed_s if enable_fire else None
                    )
                    carrier_anim_state["dynamic_artists"] = update_carrier_frame(
                        carrier_fig, carrier_ax, carrier_base_handles, nodes_for_anim,
                        top_routes, carrier_id, carrier_number, num_carriers, rank, route,
                        current_node, status, carriers_completed,
                        start_node=anim_state["start_node"], target_node=anim_state["target_node"],
                        dynamic_artists=carrier_anim_state["dynamic_artists"],
                        fire_origin_xy=(fire_x, fire_y) if enable_fire else None,
                        fire_radius_m=live_fire_radius_m,
                    )
                    with canvas_slot.container():
                        st.pyplot(carrier_fig, width='stretch')

                    # Real simulated travel time: distance actually covered so
                    # far along THIS Carrier's committed route, at the fixed
                    # firetruck speed -- the exact same distance/speed formula
                    # the ETA metric uses. When a Carrier following the best
                    # (rank-1) route reaches the target, this value equals that
                    # route's eta_seconds exactly, since both reduce to
                    # best_length / FIRETRUCK_SPEED_MPS for the same route.
                    if timer_state["frozen_at"] is None and current_node in route:
                        idx = route.index(current_node)
                        traveled_m = sum(
                            carrier_edge_lookup[(route[i], route[i + 1])]["distance_m"]
                            for i in range(idx)
                        )
                        simulated_elapsed_s = traveled_m / FIRETRUCK_SPEED_MPS
                        if status == "reached":
                            # Freeze the instant the FIRST Carrier reports
                            # "reached" -- every callback after this one is ignored.
                            timer_state["frozen_at"] = simulated_elapsed_s
                            render_timer(timer_slot, simulated_elapsed_s)
                        else:
                            timer_state["simulated_elapsed_s"] = simulated_elapsed_s
                            render_timer(timer_slot, simulated_elapsed_s)
                    time.sleep(0.03)  # small pause per Carrier step so the movement reads as motion

                # Custom overlay instead of st.spinner() -- see the
                # .running-overlay CSS above for why. Lives in loading_slot,
                # which sits inside canvas_wrapper (so it's positioned
                # relative to the map, pinned near its bottom edge) and gets
                # cleared once the run finishes.
                loading_slot.markdown(
                    '<div class="running-overlay"><span class="running-dot"></span>Scouts exploring the network...</div>',
                    unsafe_allow_html=True,
                )
                st.session_state["aco_results"] = run_full_simulation(
                    graph_file=GRAPH_FILE,
                    w1=w1, w2=w2, w3=w3,
                    rho_min=pmin_w, rho_max=pmax_w,
                    num_scouts=scout_agents,
                    num_carriers=carrier_agents,
                    fire_origin_x=fire_x, fire_origin_y=fire_y,
                    spread_rate_mps=spread_rate_m_per_min / 60,
                    enable_fire=enable_fire,
                    num_random_hazards=num_random_hazards if enable_random_hazards else 0,
                    random_hazard_seed=st.session_state["hazard_seed"],
                    progress_callback=on_scout,
                    carrier_progress_callback=on_carrier,
                )
                plt.close(anim_fig)      # only close once the whole run is done -- we reused this fig every frame
                plt.close(carrier_fig)   # same for the Carrier phase's own reused fig
                loading_slot.empty()

                # Persist the measured stopwatch time -- frozen at the first
                # Carrier's arrival if one made it, otherwise wherever the
                # clock landed when the run ended (e.g. every Carrier got
                # blocked) -- so it survives Streamlit reruns triggered by
                # slider moves instead of reverting to the distance/speed
                # ETA estimate below.
                st.session_state["aco_results"]["measured_response_time_s"] = (
                    timer_state["frozen_at"] if timer_state["frozen_at"] is not None
                    else timer_state["simulated_elapsed_s"]
                )
                # Stash the normalized weights actually used for THIS run --
                # Analytics reads these to show what fraction of the Scout
                # Ants' routing decision each factor represented (the user's
                # slider inputs), as opposed to measuring how the resulting
                # route objectively turned out.
                st.session_state["aco_results"]["dist_weight"] = w1
                st.session_state["aco_results"]["risk_weight"] = w2
                st.session_state["aco_results"]["complexity_weight"] = w3

        results = st.session_state.get("aco_results")
        # A result is "current" only if the sliders still match the position
        # it was actually computed at -- moving a slider after Running should
        # fall back to the live preview instead of showing a now-stale plot.
        result_matches_sliders = (
            results is not None
            and abs(results["fire_origin_x"] - fire_x) < 1
            and abs(results["fire_origin_y"] - fire_y) < 1
        )

        # Shows the actual measured time from Run click to the first Carrier
        # reaching the target (frozen live during the animation above).
        # Falls back to the distance/speed ETA estimate only for older
        # results computed before this field existed.
        if result_matches_sliders and results.get("measured_response_time_s") is not None:
            render_timer(timer_slot, results["measured_response_time_s"])
        elif result_matches_sliders and results["success"]:
            render_timer(timer_slot, results["eta_seconds"])
        else:
            render_timer(timer_slot)

        with canvas_slot.container():
            if result_matches_sliders and results["success"]:
                fig = plot_graph_with_route(results)
                st.pyplot(fig, width='stretch'); plt.close(fig)
            else:
                nodes, edges = load_graph_for_preview(GRAPH_FILE)
                preview_hazard_edges = compute_preview_hazards(
                    fire_x, fire_y,
                    num_random_hazards if enable_random_hazards else 0,
                    st.session_state["hazard_seed"],
                )
                fig = plot_preview(nodes, edges, (fire_x, fire_y), (STATION_X, STATION_Y), hazard_edges=preview_hazard_edges)
                st.pyplot(fig, width='stretch'); plt.close(fig)
                if results is not None and not result_matches_sliders:
                    st.caption("Sliders have moved since the last run -- click Run to simulate at this new position.")
                elif results is not None and not results["success"]:
                    st.warning("No route found last run -- try raising Scout Agents, or click Run again.")


    # ==========================
    # LEFT COLUMN, PART 2 (results -- reads what col_mid just computed)
    # ==========================
    with col_left:
        results = st.session_state.get("aco_results")

        if results and results["success"]:
            top_routes_html = ""
            route_labels = ["1st (best)", "2nd", "3rd"]
            for i, r in enumerate(results.get("top_routes", [])[:3]):
                top_routes_html += (
                    f'<div class="metric-label">{route_labels[i]} route:</div>'
                    f'<div class="metric-value">{len(r["route"])} nodes, {r["length_m"]:.1f} m</div>'
                )

            perf_html = f"""
            <div class="custom-panel">
                <div class="panel-header">Performance</div>
                <div class="panel-body">
                    <div class="metric-label">Scouts That Reached Target:</div>
                    <div class="metric-value">{results['scouts_reached_target']}/{results['scouts_run']} scouts{' (of ' + str(results['num_scouts']) + ' set)' if results['scouts_run'] < results['num_scouts'] else ''}</div>
                    <div class="metric-label">Carriers That Reached Target:</div>
                    <div class="metric-value">{results['carrier_successes']}/{results['num_carriers']} Carriers</div>
                    <div class="metric-label">Fire Radius (end of run):</div>
                    <div class="metric-value">{results['final_fire_radius_m']:.0f} m</div>
                </div>
            </div>
            """
            metrics_html = f"""
            <div class="custom-panel">
                <div class="panel-header">Metrics</div>
                <div class="panel-body" style="padding-bottom: 5px;">
                    {top_routes_html}
                    <div class="metric-label">Start / Target:</div>
                    <div class="metric-value">Fire Station &rarr; {results['target_node']}</div>
                    <div class="metric-label">First-Engine ETA:</div>
                    <div class="metric-value">{format_timer(results['eta_seconds'])} @ {results['firetruck_speed_kmh']} km/h</div>
                </div>
            </div>
            """
        else:
            perf_html = """
            <div class="custom-panel">
                <div class="panel-header">Performance</div>
                <div class="panel-body">
                    <div class="metric-label">Status:</div>
                    <div class="metric-value">Click Run to simulate</div>
                </div>
            </div>
            """
            metrics_html = """
            <div class="custom-panel">
                <div class="panel-header">Metrics</div>
                <div class="panel-body" style="padding-bottom: 5px;">
                    <div class="metric-label">Status:</div>
                    <div class="metric-value">No simulation run yet</div>
                </div>
            </div>
            """

        st.markdown(perf_html, unsafe_allow_html=True)
        st.markdown(metrics_html, unsafe_allow_html=True)

        show_analytics_clicked = st.button("Show Analytics", key="show_analytics_btn", width='stretch')
        if show_analytics_clicked:
            if not (result_matches_sliders and results and results["success"]):
                st.warning("Run a successful simulation first before viewing analytics.")
            else:
                # Analytics computation (BFP benchmark comparison, hazard
                # scoring, entrapment classification) now lives in
                # analytics.py itself -- it reads st.session_state["aco_results"]
                # (already set above) directly, so dashboard.py's only job
                # here is to navigate.
                st.session_state["page"] = "analytics"
                st.rerun()