"""
Renders the Baseco graph, in-progress scout exploration, and the final
best route as matplotlib figures for embedding in Streamlit via st.pyplot.
"""

import matplotlib.pyplot as plt
from matplotlib.patches import Circle
from matplotlib.lines import Line2D

# Road-type visual styling -- grouped into 3 tiers so the legend stays
# readable instead of listing every individual OSM tag.
ROAD_STYLE = {
    "primary": ("#5C6B85", 2.6),
    "secondary": ("#5C6B85", 2.4),
    "tertiary": ("#5C6B85", 2.2),
    "trunk": ("#5C6B85", 2.6),
    "residential": ("#A6AFC4", 1.6),
    "living_street": ("#A6AFC4", 1.6),
    "unclassified": ("#A6AFC4", 1.6),
    "service": ("#C3C9D6", 1.3),
}
DEFAULT_STYLE = ("#D8DBE5", 1.0)  # footway/path/steps/alley/track -- eskinita tier

ROAD_LEGEND = [
    Line2D([0], [0], color="#5C6B85", linewidth=2.6, label="Main road"),
    Line2D([0], [0], color="#A6AFC4", linewidth=1.6, label="Residential road"),
    Line2D([0], [0], color="#D8DBE5", linewidth=1.0, label="Footpath / eskinita"),
]


def _draw_base_graph(ax, nodes, edges):
    for e in edges.values():
        u, v = e["from"], e["to"]
        if u in nodes and v in nodes:
            tag = e.get("highway_type")
            if isinstance(tag, list):
                tag = tag[0] if tag else None
            color, width = ROAD_STYLE.get(tag, DEFAULT_STYLE)
            x = [nodes[u]["utm_x"], nodes[v]["utm_x"]]
            y = [nodes[u]["utm_y"], nodes[v]["utm_y"]]
            ax.plot(x, y, color=color, linewidth=width, zorder=1)


def _draw_random_hazards(ax, handles, nodes, hazard_edges):
    """Draws permanent debris/collapsed-structure hazard edges (distinct from
    the fire, which is time-spreading) and appends a legend entry if any were
    actually drawn. Shared by plot_preview (before Run) and
    plot_graph_with_route (after Run) so both use identical styling --
    that's what makes the preview a trustworthy stand-in for the real thing."""
    if not hazard_edges:
        return
    drawn_pairs = set()
    for (u, v) in hazard_edges:
        pair_key = frozenset((u, v))
        if pair_key in drawn_pairs or u not in nodes or v not in nodes:
            continue
        drawn_pairs.add(pair_key)
        x = [nodes[u]["utm_x"], nodes[v]["utm_x"]]
        y = [nodes[u]["utm_y"], nodes[v]["utm_y"]]
        ax.plot(x, y, color="#8B4513", linewidth=3, linestyle=(0, (2, 2)), zorder=2)
    if drawn_pairs:
        handles.append(Line2D([0], [0], color="#8B4513", linewidth=3, linestyle=(0, (2, 2)), label="Debris / blocked (random hazard)"))


def _style_axes(fig, ax):
    ax.set_facecolor("#F6F4F0")
    fig.patch.set_facecolor("#F6F4F0")
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.set_aspect("equal")
    fig.tight_layout()


def plot_preview(nodes, edges, fire_xy=None, start_xy=None, hazard_edges=None):
    """Live preview shown while adjusting sliders, before Run is clicked.
    `hazard_edges` (optional) draws the same random-hazard edges that will
    actually be used if Run is clicked right now -- see
    dashboard.py's compute_preview_hazards(), which mirrors
    simulation_backend.run_full_simulation()'s own hazard-picking logic with
    the same seed, so this is a true preview and not just a decoy."""
    fig, ax = plt.subplots(figsize=(7.6, 6.4))
    _draw_base_graph(ax, nodes, edges)

    handles = list(ROAD_LEGEND)
    _draw_random_hazards(ax, handles, nodes, hazard_edges)

    if fire_xy is not None:
        ax.scatter([fire_xy[0]], [fire_xy[1]], color="#CC3333", marker="*", s=220, zorder=3)
        handles.append(Line2D([0], [0], marker="*", color="w", markerfacecolor="#CC3333", markersize=14, label="Fire origin"))
    if start_xy is not None:
        ax.scatter([start_xy[0]], [start_xy[1]], color="#477B9E", marker="o", s=110, zorder=3)
        handles.append(Line2D([0], [0], marker="o", color="w", markerfacecolor="#477B9E", markersize=10, label="Start"))

    ax.legend(handles=handles, loc="upper right", frameon=False, fontsize=8)
    _style_axes(fig, ax)
    return fig


def plot_iteration_progress(nodes, edges, iteration, num_iterations, scout_routes, best_route):
    """One animation frame during the run: this iteration's successful
    scout trails (faint orange), plus the best route found so far (green)."""
    fig, ax = plt.subplots(figsize=(7.6, 6.4))
    _draw_base_graph(ax, nodes, edges)

    for route in scout_routes:
        rx = [nodes[n]["utm_x"] for n in route if n in nodes]
        ry = [nodes[n]["utm_y"] for n in route if n in nodes]
        ax.plot(rx, ry, color="#FFA94D", linewidth=1.3, alpha=0.55, zorder=2)

    if best_route:
        rx = [nodes[n]["utm_x"] for n in best_route if n in nodes]
        ry = [nodes[n]["utm_y"] for n in best_route if n in nodes]
        ax.plot(rx, ry, color="#60CE56", linewidth=2.5, zorder=3, label="Best so far")

    ax.set_title(
        f"Scouting... iteration {iteration}/{num_iterations}  "
        f"({len(scout_routes)} scout route(s) this pass)",
        fontsize=10, color="#555",
    )
    handles = list(ROAD_LEGEND) + [
        Line2D([0], [0], color="#FFA94D", linewidth=1.3, alpha=0.7, label="Scout trail (this pass)"),
        Line2D([0], [0], color="#60CE56", linewidth=2.5, label="Best route so far"),
    ]
    ax.legend(handles=handles, loc="upper right", frameon=False, fontsize=8)
    _style_axes(fig, ax)
    return fig


def plot_graph_with_route(results):
    nodes = results["nodes"]
    edges = results["edges"]
    top_routes = results.get("top_routes") or ([{"route": results["best_route"], "length_m": results["best_length_m"]}] if results["best_route"] else [])

    fig, ax = plt.subplots(figsize=(7.6, 6.4))
    _draw_base_graph(ax, nodes, edges)

    handles = list(ROAD_LEGEND)

    # Random hazard edges (debris/collapsed structures) -- shown distinctly
    # from the fire, since they're permanent, not time-spreading.
    _draw_random_hazards(ax, handles, nodes, results.get("random_hazard_edges"))

    if results.get("enable_fire") and results.get("final_fire_radius_m", 0) > 0:
        fire_circle = Circle(
            (results["fire_origin_x"], results["fire_origin_y"]),
            results["final_fire_radius_m"],
            facecolor="#FF6F6F", edgecolor="#CC3333",
            alpha=0.25, zorder=2,
        )
        ax.add_patch(fire_circle)
        ax.scatter([results["fire_origin_x"]], [results["fire_origin_y"]], color="#CC3333", marker="*", s=180, zorder=3)
        handles.append(Line2D([0], [0], marker="*", color="w", markerfacecolor="#CC3333", markersize=14, label="Fire origin"))
        handles.append(Line2D([0], [0], marker="o", color="w", markerfacecolor="#FF6F6F", markersize=10, alpha=0.5, label="Fire extent (end of run)"))

    route_styles = [
        ("#60CE56", 3.2, "solid", "1st best route"),
        ("#3B82C4", 2.4, (0, (6, 3)), "2nd best route"),
        ("#9B59B6", 2.0, (0, (2, 2)), "3rd best route"),
    ]
    for i, route_info in enumerate(top_routes[:3]):
        route = route_info["route"]
        color, width, style, label = route_styles[i]
        rx = [nodes[n]["utm_x"] for n in route if n in nodes]
        ry = [nodes[n]["utm_y"] for n in route if n in nodes]
        ax.plot(rx, ry, color=color, linewidth=width, linestyle=style, zorder=4 + i)
        handles.append(Line2D([0], [0], color=color, linewidth=width, linestyle=style, label=label))

    if top_routes:
        first_route = top_routes[0]["route"]
        rx = [nodes[n]["utm_x"] for n in first_route if n in nodes]
        ry = [nodes[n]["utm_y"] for n in first_route if n in nodes]
        ax.scatter([rx[0]], [ry[0]], color="#477B9E", s=100, zorder=6)
        ax.scatter([rx[-1]], [ry[-1]], color="#FF6F6F", s=100, zorder=6)
        handles.append(Line2D([0], [0], marker="o", color="w", markerfacecolor="#477B9E", markersize=10, label="Start (Fire Station)"))
        handles.append(Line2D([0], [0], marker="o", color="w", markerfacecolor="#FF6F6F", markersize=10, label="Target (fire)"))

    ax.legend(handles=handles, loc="upper right", frameon=False, fontsize=7.5)
    _style_axes(fig, ax)
    return fig