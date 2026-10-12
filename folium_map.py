"""
Interactive (pan / zoom / drag) map views built with Folium (Leaflet.js)
on top of a real OpenStreetMap basemap -- the static views only
(pre-run preview, final route result, D/R/C heatmap). The live
Scout/Carrier animation still runs on matplotlib (plotting.py).

Your graph JSON stores node positions as UTM meters (EPSG:32651), which
is what the routing math needs. Folium needs latitude/longitude, so
positions are converted on the fly with the exact inverse of
simulation_backend.latlon_to_utm -- the graph file itself is untouched,
and nothing here influences routing, only how results are drawn.

Folium wants coordinates as [lat, lon]; pyproj (always_xy=True) returns
(lon, lat). That swap is the classic bug in this kind of code, so it is
done in exactly one place (utm_to_latlon / nodes_to_latlon) and covered
by tests.
"""

import json
import os

try:
    import folium
    from branca.colormap import LinearColormap
    FOLIUM_AVAILABLE = True
except ImportError:  # dashboard.py falls back to the matplotlib maps
    folium = None
    LinearColormap = None
    FOLIUM_AVAILABLE = False

# Shared with the matplotlib heatmap so titles/labels/fallback values can
# never drift apart between the two renderers.
from plotting import ATTRIBUTE_CONFIG, _edge_attribute_value

# Must match the default epsg in simulation_backend.latlon_to_utm().
UTM_EPSG = "EPSG:32651"
BASECO_CENTER = (14.5913, 120.9600)  # (lat, lon) -- same point pull_osm_graph.py centers on

# Basemap. CARTO's free tiles now require an API key (since late Aug
# 2026) -- without one they come back watermarked "API KEY REQUIRED".
# So: plain OpenStreetMap tiles by default (no key needed, fine for
# light/demo use under OSM's tile usage policy), and if a free CARTO key
# is provided via the CARTO_API_KEY environment variable, the cleaner,
# lighter CARTO style is used instead. Never hardcode the key in source.
CARTO_KEY_ENV = "CARTO_API_KEY"
CARTO_LIGHT_URL = "https://basemaps.cartocdn.com/rastertiles/light_all/{z}/{x}/{y}.png?key=%s"
CARTO_ATTR = (
    '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors, '
    '&copy; <a href="https://carto.com/attributions">CARTO</a>'
)


# --- "Blocks" basemap: plain grey background + building footprints ---
# No tile service at all, so no street names/labels and no API key. The
# footprints come from pull_osm_buildings.py (run once). If that file is
# missing or unreadable, the map falls back to the street-tile basemap
# below, so this can never leave the dashboard without a map.
USE_BUILDING_BLOCKS = True           # set False to always use street tiles
BUILDINGS_FILE = "baseco_buildings.geojson"
BACKGROUND_COLOR = "#E9EBEF"
BUILDING_FILL = "#CBCFD8"
BUILDING_OUTLINE = "#B3B8C4"
OSM_ATTRIBUTION_TEXT = (
    '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank">OpenStreetMap</a> contributors'
)


def _collapsible_attribution_html(inner_html):
    """A small '(i)' badge, bottom-right, that expands to the full
    attribution text on click -- built with <details>/<summary> so it
    needs no JS. Used in place of Leaflet's own attribution control
    (disabled via attributionControl=False in _new_map) so EVERY basemap
    variant (buildings-blocks, OSM tiles, CARTO tiles) gets the same
    compact treatment instead of the default always-expanded grey bar.

    Collapsing it is a styling choice; the attribution text itself is NOT
    optional -- OpenStreetMap's data license (ODbL) requires it whenever
    OSM data is displayed, so this always renders the required credit,
    just tucked behind one click instead of permanently taking up space."""
    return f"""
    <details style="position:fixed;bottom:4px;right:4px;z-index:9999;
                     font:11px sans-serif;" id="attrib-details">
        <summary style="list-style:none;cursor:pointer;width:18px;height:18px;
                         border-radius:50%;background:rgba(255,255,255,0.85);
                         color:#555;text-align:center;line-height:18px;
                         box-shadow:0 1px 3px rgba(0,0,0,0.3);
                         font-weight:700;">i</summary>
        <div style="margin-top:2px;background:rgba(255,255,255,0.9);
                     padding:3px 8px;border-radius:4px;color:#333;
                     box-shadow:0 1px 3px rgba(0,0,0,0.3);
                     white-space:nowrap;">
            {inner_html}
        </div>
    </details>
    <style>#attrib-details summary::-webkit-details-marker {{display:none;}}</style>
    """

_buildings_cache = {"path": None, "mtime": None, "data": None}


def _load_buildings():
    """GeoJSON dict of building outlines, or None if unavailable. Cached
    (re-read only if the file changes) because the map is rebuilt on every
    Streamlit rerun and the file can be ~1 MB."""
    if not USE_BUILDING_BLOCKS:
        return None
    try:
        mtime = os.path.getmtime(BUILDINGS_FILE)
        c = _buildings_cache
        if c["path"] == BUILDINGS_FILE and c["mtime"] == mtime:
            return c["data"]
        with open(BUILDINGS_FILE) as f:
            data = json.load(f)
        if not data.get("features"):
            return None
        c.update(path=BUILDINGS_FILE, mtime=mtime, data=data)
        return data
    except (OSError, ValueError, AttributeError):
        return None


def _building_style(_feature):
    return {
        "fillColor": BUILDING_FILL, "color": BUILDING_OUTLINE,
        "weight": 0.8, "fillOpacity": 1.0,
    }


def _basemap_kwargs():
    key = os.environ.get(CARTO_KEY_ENV, "").strip()
    if key:
        return {"tiles": CARTO_LIGHT_URL % key, "attr": CARTO_ATTR}
    return {"tiles": "OpenStreetMap"}

# Overlay styling for the base graph, 3 tiers like the matplotlib legend.
# Darker/thicker than the matplotlib versions: the old light greys were
# tuned for a cream background and would vanish on a map basemap.
TIER_STYLE = {
    "main": ("#3D4A63", 4.0, "Main road"),
    "residential": ("#6F7D99", 3.0, "Residential road"),
    "footpath": ("#8C97B2", 2.5, "Footpath / eskinita"),
}
_MAIN_TAGS = {"primary", "secondary", "tertiary", "trunk"}
_RESIDENTIAL_TAGS = {"residential", "living_street", "unclassified", "service"}

# Same hues as the live animation (plotting.update_carrier_frame) so a
# route keeps one color identity from animation to final map.
ROUTE_STYLES = [
    ("#60CE56", 7.0, None, "1st best route"),
    ("#3B82C4", 5.5, "10 8", "2nd best route"),
    ("#9B59B6", 4.5, "3 8", "3rd best route"),
]
HAZARD_COLOR = "#8B4513"
FIRE_COLOR = "#CC3333"
TARGET_COLOR = "#FF6F6F"
# Approximate Leaflet pin colors, only used for legend swatches.
PIN_RED = "#D63E2A"
PIN_BLUE = "#38AADD"

HEATMAP_COLORS = ["#1a9850", "#fee08b", "#d73027"]  # green -> yellow -> red
HEATMAP_TOOLTIP = {
    "distance": ("Distance", " m"),
    "risk": ("Risk", " / 10"),
    "complexity": ("Turn complexity", "\u00b0"),
}

_transformer = None


# --------------------------------------------------------------------------
# Coordinate conversion (UTM meters -> lat/lon)
# --------------------------------------------------------------------------

def _inverse_transformer():
    global _transformer
    if _transformer is None:
        from pyproj import Transformer
        _transformer = Transformer.from_crs(UTM_EPSG, "EPSG:4326", always_xy=True)
    return _transformer


def utm_to_latlon(x, y):
    """Returns (lat, lon). pyproj gives (lon, lat) with always_xy=True --
    swapped here, once, because Folium expects [lat, lon]."""
    lon, lat = _inverse_transformer().transform(x, y)
    return lat, lon


def nodes_to_latlon(nodes):
    """{node_id: (lat, lon)} for every node, converted in one batch call."""
    ids = list(nodes.keys())
    if not ids:
        return {}
    xs = [nodes[n]["utm_x"] for n in ids]
    ys = [nodes[n]["utm_y"] for n in ids]
    lons, lats = _inverse_transformer().transform(xs, ys)
    return {n: (lat, lon) for n, lat, lon in zip(ids, lats, lons)}


# --------------------------------------------------------------------------
# Shared building blocks
# --------------------------------------------------------------------------

INITIAL_ZOOM = 18  # a closer first view than fit_bounds was producing --
                    # see the note below on why fit_bounds was dropped

def _new_map(nodes_ll):
    if nodes_ll:
        lats = [p[0] for p in nodes_ll.values()]
        lons = [p[1] for p in nodes_ll.values()]
        center = [(min(lats) + max(lats)) / 2, (min(lons) + max(lons)) / 2]
    else:
        center = list(BASECO_CENTER)
    buildings = _load_buildings()
    # attributionControl=False in both branches below hides Leaflet's own
    # always-expanded attribution bar; _collapsible_attribution_html()
    # adds the required credit back in as a small click-to-expand badge
    # instead (see that function's docstring for why it's never fully
    # removed).
    if buildings is not None:
        # tiles=None: no tile layer, so no street names. Buildings are
        # added FIRST so every later layer (roads, routes, markers) draws
        # on top of them.
        m = folium.Map(location=center, zoom_start=INITIAL_ZOOM, control_scale=True,
                       tiles=None, max_zoom=20, attributionControl=False)
        m.get_root().header.add_child(folium.Element(
            f"<style>.leaflet-container{{background:{BACKGROUND_COLOR} !important;}}</style>"))
        m.get_root().html.add_child(folium.Element(_collapsible_attribution_html(OSM_ATTRIBUTION_TEXT)))
        folium.GeoJson(buildings, name="Buildings", style_function=_building_style).add_to(m)
    else:
        basemap_kwargs = _basemap_kwargs()
        # `attr` is kept IN basemap_kwargs (not popped) and passed to
        # folium.Map as usual -- Folium's TileLayer still needs it for a
        # custom tile URL (CARTO) even with attributionControl=False, to
        # satisfy its own "custom tiles must have an attribution" check.
        # It just won't be the thing actually displayed; the badge below is.
        tile_attr_text = basemap_kwargs.get("attr", OSM_ATTRIBUTION_TEXT)
        m = folium.Map(location=center, zoom_start=INITIAL_ZOOM, control_scale=True,
                       attributionControl=False, **basemap_kwargs)
        m.get_root().html.add_child(folium.Element(_collapsible_attribution_html(tile_attr_text)))
    # NOTE: no fit_bounds() here. fit_bounds was given the lat/lon extent
    # of EVERY node in the graph (the whole ~600-800m street network), so
    # it zoomed out however far was needed to fit that entire area on
    # screen -- silently overriding zoom_start every time, regardless of
    # what's actually on the map (a small preview, one route, etc). The
    # map now just opens centered on the graph's centroid at a fixed,
    # closer zoom level. The person can still scroll to zoom out if they
    # want the wider view back.
    return m


def _edge_tier(e):
    tag = e.get("highway_type")
    if isinstance(tag, list):
        tag = tag[0] if tag else None
    if tag in _MAIN_TAGS:
        return "main"
    if tag in _RESIDENTIAL_TAGS:
        return "residential"
    return "footpath"


def _segment(e, nodes_ll):
    u, v = e["from"], e["to"]
    if u in nodes_ll and v in nodes_ll:
        return [list(nodes_ll[u]), list(nodes_ll[v])]
    return None


def _unique_edges(edges):
    """The walk graph lists every street in both directions (and
    sometimes as parallel edges); they draw as the same straight line, so
    keep one per node pair to halve the layer count."""
    seen = set()
    for e in edges.values():
        key = frozenset((e["from"], e["to"]))
        if key in seen:
            continue
        seen.add(key)
        yield e


def _route_latlons(route, nodes_ll):
    return [list(nodes_ll[n]) for n in route if n in nodes_ll]


def _add_base_graph(m, nodes_ll, edges):
    groups = {"main": [], "residential": [], "footpath": []}
    for e in _unique_edges(edges):
        seg = _segment(e, nodes_ll)
        if seg:
            groups[_edge_tier(e)].append(seg)
    # Thinnest first so main roads draw on top. One multi-polyline per
    # tier (3 layers) instead of one layer per edge.
    for tier in ("footpath", "residential", "main"):
        segs = groups[tier]
        if segs:
            color, weight, label = TIER_STYLE[tier]
            folium.PolyLine(
                locations=segs, color=color, weight=weight, opacity=0.9, tooltip=label,
            ).add_to(m)


def _add_hazards(m, nodes_ll, hazard_edges):
    """Returns True if any hazard edge was drawn (for the legend)."""
    if not hazard_edges:
        return False
    segs, seen = [], set()
    for (u, v) in hazard_edges:
        key = frozenset((u, v))
        if key in seen or u not in nodes_ll or v not in nodes_ll:
            continue
        seen.add(key)
        segs.append([list(nodes_ll[u]), list(nodes_ll[v])])
    if not segs:
        return False
    folium.PolyLine(
        locations=segs, color=HAZARD_COLOR, weight=6, opacity=0.95,
        dash_array="6 6", tooltip="Debris / blocked (random hazard)",
    ).add_to(m)
    return True


def _add_fire(m, fire_xy, radius_m=None):
    lat, lon = utm_to_latlon(*fire_xy)
    if radius_m and radius_m > 0:
        folium.Circle(
            location=[lat, lon], radius=radius_m, color=FIRE_COLOR, weight=2,
            fill=True, fill_color=FIRE_COLOR, fill_opacity=0.22,
            tooltip=f"Fire spread (~{radius_m:.0f} m radius)",
        ).add_to(m)
    folium.Marker(
        location=[lat, lon], tooltip="Fire origin",
        icon=folium.Icon(color="red", icon="fire"),
    ).add_to(m)


def _add_start(m, start_xy):
    lat, lon = utm_to_latlon(*start_xy)
    folium.Marker(
        location=[lat, lon], tooltip="Start (Fire Station)",
        icon=folium.Icon(color="blue", icon="home"),
    ).add_to(m)


def _legend_html(rows):
    parts = []
    for kind, color, label in rows:
        if kind == "line":
            swatch = (f'<span style="display:inline-block;width:24px;border-top:4px solid {color};'
                      f'vertical-align:middle;margin-right:8px;"></span>')
        elif kind == "dashed":
            swatch = (f'<span style="display:inline-block;width:24px;border-top:4px dashed {color};'
                      f'vertical-align:middle;margin-right:8px;"></span>')
        else:  # "dot"
            swatch = (f'<span style="display:inline-block;width:12px;height:12px;border-radius:50%;'
                      f'background:{color};vertical-align:middle;margin:0 14px 0 6px;"></span>')
        parts.append(f"<div>{swatch}{label}</div>")
    return (
        '<div style="position:fixed;bottom:18px;left:12px;z-index:9999;'
        'background:rgba(255,255,255,0.93);padding:8px 12px;border-radius:8px;'
        'box-shadow:0 1px 5px rgba(0,0,0,0.3);font:12px/1.55 sans-serif;color:#333;">'
        + "".join(parts) + "</div>"
    )


def _add_legend(m, rows):
    m.get_root().html.add_child(folium.Element(_legend_html(rows)))


def _road_legend_rows():
    return [
        ("line", TIER_STYLE["main"][0], TIER_STYLE["main"][2]),
        ("line", TIER_STYLE["residential"][0], TIER_STYLE["residential"][2]),
        ("line", TIER_STYLE["footpath"][0], TIER_STYLE["footpath"][2]),
    ]


# --------------------------------------------------------------------------
# Public map builders
# --------------------------------------------------------------------------

def build_preview_map(nodes, edges, fire_xy=None, start_xy=None, hazard_edges=None):
    """Interactive equivalent of plotting.plot_preview()."""
    nodes_ll = nodes_to_latlon(nodes)
    m = _new_map(nodes_ll)
    _add_base_graph(m, nodes_ll, edges)

    legend = _road_legend_rows()
    if _add_hazards(m, nodes_ll, hazard_edges):
        legend.append(("dashed", HAZARD_COLOR, "Debris / blocked (random hazard)"))
    if fire_xy is not None:
        _add_fire(m, fire_xy)
        legend.append(("dot", PIN_RED, "Fire origin"))
    if start_xy is not None:
        _add_start(m, start_xy)
        legend.append(("dot", PIN_BLUE, "Start"))
    _add_legend(m, legend)
    return m


def build_route_map(results):
    """Interactive equivalent of plotting.plot_graph_with_route()."""
    nodes = results["nodes"]
    edges = results["edges"]
    top_routes = results.get("top_routes") or (
        [{"route": results["best_route"], "length_m": results["best_length_m"]}]
        if results.get("best_route") else []
    )

    nodes_ll = nodes_to_latlon(nodes)
    m = _new_map(nodes_ll)
    _add_base_graph(m, nodes_ll, edges)

    legend = _road_legend_rows()
    if _add_hazards(m, nodes_ll, results.get("random_hazard_edges")):
        legend.append(("dashed", HAZARD_COLOR, "Debris / blocked (random hazard)"))

    if results.get("enable_fire"):
        _add_fire(
            m, (results["fire_origin_x"], results["fire_origin_y"]),
            radius_m=results.get("final_fire_radius_m", 0),
        )
        legend.append(("dot", PIN_RED, "Fire origin / spread"))

    # Draw 3rd -> 1st so the best route ends up on top.
    for i in reversed(range(min(3, len(top_routes)))):
        info = top_routes[i]
        color, weight, dash, label = ROUTE_STYLES[i]
        pts = _route_latlons(info["route"], nodes_ll)
        if len(pts) < 2:
            continue
        if dash is None:
            # White casing under the solid best route -- navigation-app look.
            folium.PolyLine(locations=pts, color="#FFFFFF", weight=weight + 4, opacity=0.9).add_to(m)
        kwargs = {"dash_array": dash} if dash else {}
        folium.PolyLine(
            locations=pts, color=color, weight=weight, opacity=0.95,
            tooltip=f"{label} - {info['length_m']:.0f} m", **kwargs,
        ).add_to(m)
    for i in range(min(3, len(top_routes))):
        color, _w, dash, label = ROUTE_STYLES[i]
        legend.append(("dashed" if dash else "line", color, label))

    if top_routes:
        first_pts = _route_latlons(top_routes[0]["route"], nodes_ll)
        if first_pts:
            folium.Marker(
                location=first_pts[0], tooltip="Start (Fire Station)",
                icon=folium.Icon(color="blue", icon="home"),
            ).add_to(m)
            folium.CircleMarker(
                location=first_pts[-1], radius=9, color="#FFFFFF", weight=2,
                fill=True, fill_color=TARGET_COLOR, fill_opacity=1.0,
                tooltip="Target (fire)",
            ).add_to(m)
            legend.append(("dot", PIN_BLUE, "Start (Fire Station)"))
            legend.append(("dot", TARGET_COLOR, "Target (fire)"))

    _add_legend(m, legend)
    return m


def build_attribute_heatmap_map(nodes, edges, attribute, fire_xy=None, start_xy=None, hazard_edges=None):
    """Interactive equivalent of plotting.plot_attribute_heatmap(): every
    edge colored green -> red by its D, R, or C value. Same raw values,
    same value/max scale (vmin fixed at 0) as the matplotlib version, plus
    a hover tooltip with each edge's exact number."""
    cfg = ATTRIBUTE_CONFIG[attribute]
    nodes_ll = nodes_to_latlon(nodes)
    m = _new_map(nodes_ll)

    pairs = []
    for e in _unique_edges(edges):
        seg = _segment(e, nodes_ll)
        if seg:
            pairs.append((seg, _edge_attribute_value(e, attribute)))

    max_val = (max((v for _s, v in pairs), default=1.0)) or 1.0
    cmap = LinearColormap(colors=HEATMAP_COLORS, vmin=0.0, vmax=max_val, caption=cfg["colorbar_label"])
    name, unit = HEATMAP_TOOLTIP[attribute]
    for seg, value in pairs:
        folium.PolyLine(
            locations=seg, color=cmap(value), weight=5, opacity=0.95,
            tooltip=f"{name}: {value:.1f}{unit}",
        ).add_to(m)
    cmap.add_to(m)

    legend = []
    if _add_hazards(m, nodes_ll, hazard_edges):
        legend.append(("dashed", HAZARD_COLOR, "Debris / blocked (random hazard)"))
    if fire_xy is not None:
        _add_fire(m, fire_xy)
        legend.append(("dot", PIN_RED, "Fire origin"))
    if start_xy is not None:
        _add_start(m, start_xy)
        legend.append(("dot", PIN_BLUE, "Start"))
    if legend:
        _add_legend(m, legend)
    return m