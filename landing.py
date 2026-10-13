import time
import base64
from pathlib import Path

import streamlit as st

# How long the loading screen stays up after the work is done, so the
# (hidden) map has time to load in the browser -- component bundle and map
# tiles get fetched and cached, which is what makes the dashboard's map
# appear instantly instead of popping in a moment after the page.
# Set to 0 to skip the extra wait.
MAP_WARM_SECONDS = 1.5
HIDDEN_MAP_HEIGHT_PX = 640   # keep equal to the dashboard's MAP_HEIGHT_PX


def get_base64_image(image_path):
    img_bytes = Path(image_path).read_bytes()
    return base64.b64encode(img_bytes).decode()


def _render_brand():
    """Shared look for the landing and loading screens: CSS, top bar,
    logo and the AEGIS title."""
    img_base64 = get_base64_image("aegis_logo.png")

    st.markdown(f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Rethink+Sans:ital,wght@0,400..800;1,400..800&family=Russo+One&display=swap');

        html, body, .stApp,
        [data-testid="stAppViewContainer"],
        [data-testid="stMain"],
        section.main {{
            overflow: hidden !important;
        }}

        .stApp {{
            background: linear-gradient(180deg, #121212 0%, #000000 100%);
            background-attachment: fixed;
        }}

        header {{ visibility: hidden !important; }}

        .top-window-bar {{
            position: fixed;
            top: 0; left: 0; width: 100%; height: 35px;
            background-color: #121212;
            border-bottom: 1px solid #121212;
            z-index: 999;
            display: flex;
            align-items: center;
            padding-left: 15px;
            box-shadow: 0px 2px 2px rgba(0, 0, 0, 0.15);
        }}

        .block-container {{
            padding-top: 4rem;
            overflow: hidden !important;
        }}

        div.stButton {{
            display: flex;
            justify-content: center;
            width: 100%;
        }}

        .aegis-logo-container {{
            display: flex;
            justify-content: center;
            margin-bottom: 10px;
        }}

        .aegis-logo-container img {{
            width: 100%;
            max-width: 375px;
            margin-top: 30px;
            height: auto;
            pointer-events: none;
            user-select: none;
        }}

        .aegis-title {{
            font-family: 'Russo One', sans-serif;
            font-size: 100px;
            color: #477B9E;
            margin-top: -20px;
            margin-bottom: 20px;
            letter-spacing: 2px;
            text-align: center;
        }}

        .aegis-subtitle {{
            font-family: 'Rethink Sans', sans-serif;
            font-size: 18px;
            font-weight: 600;
            color: #FFFFFF;
            margin-top: 30px;
            margin-bottom: 40px;
            text-align: center;
        }}

        div.stButton > button:first-child {{
            background-color: #275075;
            color: #FFFFFF;
            border-radius: 12px;
            padding: 10px 35px;
            width: 400px;
            height: 65px;
            font-size: 18px;
            font-weight: bold;
            font-family: 'Rethink Sans', sans-serif;
            border: none;
            box-shadow: 0px 4px 6px rgba(0, 0, 0, 0.1);
        }}

        div.stButton > button:first-child p,
        div.stButton > button:first-child div {{
            font-family: 'Rethink Sans', sans-serif !important;
            font-weight: bold !important;
            font-size: 18px !important;
        }}

        div.stButton > button:first-child:hover {{
            background-color: #193145;
        }}

        /* ---- Loading screen ---- */
        .aegis-loading {{
            width: 400px;
            max-width: 100%;
            margin: 30px auto 0 auto;
            text-align: center;
            font-family: 'Rethink Sans', sans-serif;
            animation: aegis-fade-in 0.4s ease both;
        }}
        .aegis-loading-label {{
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 10px;
            font-size: 16px;
            font-weight: 600;
            color: #FFFFFF;
        }}
        .aegis-spinner {{
            width: 18px;
            height: 18px;
            flex-shrink: 0;
            border: 3px solid rgba(71, 123, 158, 0.25);
            border-top-color: #477B9E;
            border-radius: 50%;
            animation: aegis-spin 0.8s linear infinite;
        }}
        .aegis-loading-bar {{
            height: 6px;
            margin-top: 14px;
            border-radius: 3px;
            background: rgba(71, 123, 158, 0.18);
            overflow: hidden;
        }}
        .aegis-loading-bar > div {{
            height: 100%;
            background: #477B9E;
            border-radius: 3px;
            transition: width 0.25s ease;
        }}
        @keyframes aegis-spin {{ to {{ transform: rotate(360deg); }} }}
        @keyframes aegis-fade-in {{ from {{ opacity: 0; }} to {{ opacity: 1; }} }}

        /* Off-screen (but full-size, so Leaflet really loads) container for
           the pre-warm map on the loading screen. */
        .st-key-warm_map_box {{
            position: fixed;
            left: -5000px;
            top: 0;
            width: 1000px;
            height: {HIDDEN_MAP_HEIGHT_PX}px;
            opacity: 0;
            pointer-events: none;
        }}
        </style>

        <div class="top-window-bar"></div>

        <div class="aegis-logo-container">
            <img src="data:image/png;base64,{img_base64}">
        </div>
    """, unsafe_allow_html=True)


def render_landing():
    _render_brand()
    st.markdown('<div class="aegis-subtitle">System ready for deployment!</div>', unsafe_allow_html=True)

    _, col_btn, _ = st.columns([1, 2, 1])
    with col_btn:
        if st.button("START"):
            # Go through the loading screen first so the dashboard opens
            # with its data cached and its map already loaded.
            st.session_state["page"] = "loading"
            st.rerun()


def _loading_html(label, pct):
    return (
        '<div class="aegis-loading">'
        f'<div class="aegis-loading-label"><span class="aegis-spinner"></span>{label}</div>'
        f'<div class="aegis-loading-bar"><div style="width:{pct:.0f}%"></div></div>'
        '</div>'
    )


def render_loading():
    """Loading screen between the landing page and the dashboard. Does the
    dashboard's first-render work up front (graph, start node, building
    outlines, a first map build) and loads a hidden copy of the map in the
    browser, then hands over to the dashboard."""
    _render_brand()
    status = st.empty()
    status.markdown(_loading_html("Starting up...", 0), unsafe_allow_html=True)

    # Imported here (not at the top) so the landing page itself stays light.
    # Every step is best-effort: if one fails, the dashboard just does that
    # work itself on first render, so a warm-up problem never blocks entry.
    try:
        import dashboard as dash
    except Exception:
        dash = None

    state = {}

    def load_network():
        state["nodes"], state["edges"] = dash.load_graph_for_preview(dash.GRAPH_FILE)
        dash.load_graph_structures(dash.GRAPH_FILE)

    def locate_station():
        dash.get_graph_bounds(dash.GRAPH_FILE)
        state["start_xy"] = dash.get_start_node_xy(dash.GRAPH_FILE)

    def build_map():
        dash.folium_map._load_buildings()
        state["map"] = dash.folium_map.build_preview_map(
            state["nodes"], state["edges"], None, state["start_xy"], hazard_edges=None,
        )

    map_ok = bool(dash and dash.INTERACTIVE_MAP_AVAILABLE and dash.st_folium is not None)
    steps = [("Loading road network", load_network),
             ("Locating fire station", locate_station)]
    if map_ok:
        steps.append(("Preparing map", build_map))

    total = len(steps) + 1   # +1 for the final map-loading phase
    for i, (label, fn) in enumerate(steps):
        status.markdown(_loading_html(label + "...", 100 * i / total), unsafe_allow_html=True)
        if dash is not None:
            try:
                fn()
            except Exception:
                pass

    # Load a hidden copy of the map in the browser and give it a moment, so
    # the component bundle and map tiles are already fetched and cached
    # when the dashboard draws its own map.
    if map_ok and state.get("map") is not None and MAP_WARM_SECONDS > 0:
        with st.container(key="warm_map_box"):
            try:
                dash.st_folium(state["map"], height=HIDDEN_MAP_HEIGHT_PX, width=1000,
                               returned_objects=[], key="warm_map")
            except Exception:
                pass
        base = 100 * len(steps) / total
        ticks = 10
        for t in range(1, ticks + 1):
            time.sleep(MAP_WARM_SECONDS / ticks)
            status.markdown(
                _loading_html("Rendering map..." if t < ticks else "Ready",
                              base + (100 - base) * t / ticks),
                unsafe_allow_html=True,
            )
    else:
        status.markdown(_loading_html("Ready", 100), unsafe_allow_html=True)

    st.session_state["page"] = "dashboard"
    st.rerun()