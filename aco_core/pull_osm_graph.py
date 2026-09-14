"""
Pulls the real OpenStreetMap path network for a Baseco-area point directly
into a routable graph

SETUP:
    pip install osmnx --break-system-packages
"""

import osmnx as ox
import networkx as nx
import json
import math

# --- Center point + radius around Baseco study area ---
CENTER_POINT = (14.5913, 120.9600)   # (lat, lon)
RADIUS_METERS = 400

# network_type='walk' pulls footways/alleys/paths
G = ox.graph_from_point(
    CENTER_POINT,
    dist=RADIUS_METERS,
    network_type="walk",
    simplify=True,
)

print(f"Pulled {G.number_of_nodes()} nodes and {G.number_of_edges()} edges from OSM")

# Project to a metric CRS (UTM 51N) so edge lengths are in real meters
G_proj = ox.project_graph(G, to_crs="EPSG:32651")

edges_out = {}
for u, v, key, data in G_proj.edges(keys=True, data=True):
    edge_key = f"{u}-{v}-{key}"

    # Turn complexity: if this edge has interior geometry (a curved path
    # between two nodes), sum up the cumulative
    # turning angle along it. Straight edges get 0.
    turn_deg = 0.0
    geom = data.get("geometry")
    if geom is not None:
        coords = list(geom.coords)
        for i in range(1, len(coords) - 1):
            x0, y0 = coords[i - 1]
            x1, y1 = coords[i]
            x2, y2 = coords[i + 1]
            a1 = math.atan2(y1 - y0, x1 - x0)
            a2 = math.atan2(y2 - y1, x2 - x1)
            diff = math.degrees(abs(a2 - a1))
            turn_deg += 360 - diff if diff > 180 else diff

    edges_out[edge_key] = {
        "from": str(u),
        "to": str(v),
        "distance_m": round(data.get("length", 0), 2),
        "turn_complexity_deg": round(turn_deg, 2),
        "highway_type": data.get("highway", "unknown"),  # e.g. footway, path, alley
        "risk_score": None,
    }

nodes_out = {
    str(n): {"utm_x": round(d["x"], 2), "utm_y": round(d["y"], 2)}
    for n, d in G_proj.nodes(data=True)
}

output = {"nodes": nodes_out, "edges": edges_out}
with open("baseco_osm_graph.json", "w") as f:
    json.dump(output, f, indent=2)

print(f"Saved graph to baseco_osm_graph.json")
print(f"NOTE: risk_score is null for every edge -- you'll still need to")
print(f"      assign that manually based on visual inspection, same as before.")

# Saves a PNG of the pulled network
try:
    ox.plot_graph(G, show=False, save=True, filepath="baseco_osm_preview.png")
    print("Saved a preview image to baseco_osm_preview.png -- check that it")
    print("actually shows dense alley-level detail, not just main roads.")
except ImportError:
    print("Skipped preview image (matplotlib not installed) -- but your")
    print("graph data was already saved successfully to baseco_osm_graph.json.")
    print("Run: pip install matplotlib --break-system-packages, then re-run")
    print("this script if you still want the preview image.")