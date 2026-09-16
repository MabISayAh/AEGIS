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

# Purely cosmetic nudge applied when DRAWING the Start marker
START_MARKER_OFFSET_M = (0.0, -6.0)  # (dx, dy)


def _offset_point(x, y, offset=START_MARKER_OFFSET_M):
    dx, dy = offset
    return x + dx, y + dy


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
            ax.plot(x, y, color=color, linewidth=width, zorder=1, clip_on=False)


def _draw_random_hazards(ax, handles, nodes, hazard_edges):
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
        ax.plot(x, y, color="#8B4513", linewidth=3, linestyle=(0, (2, 2)), zorder=2, clip_on=False)
    if drawn_pairs:
        handles.append(Line2D([0], [0], color="#8B4513", linewidth=3, linestyle=(0, (2, 2)), label="Debris / blocked (random hazard)"))


def _style_axes(fig, ax):
    ax.set_facecolor("#F6F4F0")
    fig.patch.set_facecolor("#F6F4F0")
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.margins(0.12)
    ax.set_aspect("equal")


def _place_legend(fig, ax, handles, fontsize=8):
    ax.legend(
        handles=handles, loc="upper left", bbox_to_anchor=(1.02, 1.0),
        frameon=False, fontsize=fontsize, borderaxespad=0.0,
    )
    fig.subplots_adjust(left=0.02, right=0.76, top=0.93, bottom=0.05)


def plot_preview(nodes, edges, fire_xy=None, start_xy=None, hazard_edges=None):
    fig, ax = plt.subplots(figsize=(9.6, 6.4))
    _draw_base_graph(ax, nodes, edges)

    handles = list(ROAD_LEGEND)
    _draw_random_hazards(ax, handles, nodes, hazard_edges)

    if fire_xy is not None:
        ax.scatter([fire_xy[0]], [fire_xy[1]], color="#CC3333", marker="*", s=220, zorder=3, clip_on=False)
        handles.append(Line2D([0], [0], marker="*", color="w", markerfacecolor="#CC3333", markersize=14, label="Fire origin"))
    if start_xy is not None:
        sx, sy = _offset_point(*start_xy)
        ax.scatter([sx], [sy], color="#477B9E", marker="o", s=110, zorder=3, clip_on=False)
        handles.append(Line2D([0], [0], marker="o", color="w", markerfacecolor="#477B9E", markersize=10, label="Start"))

    _style_axes(fig, ax)
    _place_legend(fig, ax, handles, fontsize=8)
    return fig


def plot_scout_progress(nodes, edges, scout_number, num_scouts, scout_route,
                         verified_routes, best_route, start_node=None,
                         target_node=None, scout_status=None):
    fig, ax = plt.subplots(figsize=(9.6, 6.4))
    _draw_base_graph(ax, nodes, edges)

    handles = list(ROAD_LEGEND)

    verified_styles = [
        ("#60CE56", 2.8, "solid", "Verified route 1"),
        ("#3B82C4", 2.4, (0, (6, 3)), "Verified route 2"),
        ("#9B59B6", 2.0, (0, (2, 2)), "Verified route 3"),
    ]
    for i, route in enumerate((verified_routes or [])[:3]):
        color, width, style, label = verified_styles[i]
        rx = [nodes[n]["utm_x"] for n in route if n in nodes]
        ry = [nodes[n]["utm_y"] for n in route if n in nodes]
        ax.plot(rx, ry, color=color, linewidth=width, linestyle=style, zorder=3 + i, clip_on=False)
        handles.append(Line2D([0], [0], color=color, linewidth=width, linestyle=style, label=label))

    if scout_route:
        rx = [nodes[n]["utm_x"] for n in scout_route if n in nodes]
        ry = [nodes[n]["utm_y"] for n in scout_route if n in nodes]
        ax.plot(rx, ry, color="#FFA94D", linewidth=3.0, zorder=6, clip_on=False)
        handles.append(Line2D([0], [0], color="#FFA94D", linewidth=3.0, label=f"Scout {scout_number} (this pass)"))

    if start_node and start_node in nodes:
        sx, sy = _offset_point(nodes[start_node]["utm_x"], nodes[start_node]["utm_y"])
        ax.scatter([sx], [sy], color="#477B9E", s=100, zorder=7, clip_on=False)
        handles.append(Line2D([0], [0], marker="o", color="w", markerfacecolor="#477B9E", markersize=10, label="Start (Fire Station)"))
    if target_node and target_node in nodes:
        ax.scatter([nodes[target_node]["utm_x"]], [nodes[target_node]["utm_y"]],
                   color="#FF6F6F", s=100, zorder=7, clip_on=False)
        handles.append(Line2D([0], [0], marker="o", color="w", markerfacecolor="#FF6F6F", markersize=10, label="Target (fire)"))

    status = {
        "reached": "reached target",
        "no_path": "no hazard-free path exists right now",
        "step_budget": "still searching -- ran out of step budget",
    }.get(scout_status, "reached target" if scout_route else "blocked / backtracked")
    ax.set_title(
        f"Scout {scout_number}/{num_scouts} -- {status}",
        fontsize=10, color="#555",
    )
    _style_axes(fig, ax)
    _place_legend(fig, ax, handles, fontsize=7.5)
    return fig


def create_scout_canvas(nodes, edges, hazard_edges=None):
    fig, ax = plt.subplots(figsize=(9.6, 6.4))
    _draw_base_graph(ax, nodes, edges)
    base_handles = list(ROAD_LEGEND)
    _draw_random_hazards(ax, base_handles, nodes, hazard_edges)
    _style_axes(fig, ax)
    return fig, ax, base_handles


def _draw_live_fire(ax, new_artists, handles, fire_origin_xy, fire_radius_m,
                     moderate_buffer_m=12, low_buffer_m=25):
    """
    Draws the fire's CURRENT extent as three concentric rings.
    Buffers are intentionally tight so the growth is clearly visible
    as the simulation progresses.
    """
    if fire_origin_xy is None or fire_radius_m is None or fire_radius_m < 0:
        return
    fx, fy = fire_origin_xy

    tiers = [
        (fire_radius_m + low_buffer_m, "#FFD54F", 0.18, "Fire hazard -- LOW"),
        (fire_radius_m + moderate_buffer_m, "#FF8A65", 0.30, "Fire hazard -- MODERATE"),
        (fire_radius_m, "#FF6F6F", 0.55, "Fire hazard -- IMPASSABLE"),
    ]
    for i, (r, color, alpha, label) in enumerate(tiers):
        if r <= 0:
            continue
        circle = Circle(
            (fx, fy), r,
            facecolor=color, edgecolor=color,
            alpha=alpha, zorder=2 + i * 0.1, clip_on=False, linewidth=0,
        )
        ax.add_patch(circle)
        new_artists.append(circle)
        handles.append(Line2D([0], [0], marker="o", color="w", markerfacecolor=color,
                               markersize=10, alpha=min(alpha + 0.35, 1.0), label=label))

    star = ax.scatter([fx], [fy], color="#CC3333", marker="*", s=180, zorder=3, clip_on=False)
    new_artists.append(star)
    handles.append(Line2D([0], [0], marker="*", color="w", markerfacecolor="#CC3333", markersize=14, label="Fire origin"))


def update_scout_frame(fig, ax, base_handles, nodes, scout_number, num_scouts,
                        scout_route, verified_routes, best_route,
                        start_node=None, target_node=None, scout_status=None,
                        dynamic_artists=None, fire_origin_xy=None, fire_radius_m=None):
    # Remove previous dynamic artists
    if dynamic_artists:
        for artist in dynamic_artists:
            try:
                artist.remove()
            except Exception:
                pass

    new_artists = []
    handles = list(base_handles)

    # Live fire (grows every frame)
    _draw_live_fire(ax, new_artists, handles, fire_origin_xy, fire_radius_m)

    # Verified routes
    verified_styles = [
        ("#60CE56", 2.8, "solid", "Verified route 1"),
        ("#3B82C4", 2.4, (0, (6, 3)), "Verified route 2"),
        ("#9B59B6", 2.0, (0, (2, 2)), "Verified route 3"),
    ]
    for i, route in enumerate((verified_routes or [])[:3]):
        color, width, style, label = verified_styles[i]
        rx = [nodes[n]["utm_x"] for n in route if n in nodes]
        ry = [nodes[n]["utm_y"] for n in route if n in nodes]
        line, = ax.plot(rx, ry, color=color, linewidth=width, linestyle=style, zorder=3 + i, clip_on=False)
        new_artists.append(line)
        handles.append(Line2D([0], [0], color=color, linewidth=width, linestyle=style, label=label))

    # Current scout path
    if scout_route:
        rx = [nodes[n]["utm_x"] for n in scout_route if n in nodes]
        ry = [nodes[n]["utm_y"] for n in scout_route if n in nodes]
        line, = ax.plot(rx, ry, color="#FFA94D", linewidth=3.0, zorder=6, clip_on=False)
        new_artists.append(line)
        handles.append(Line2D([0], [0], color="#FFA94D", linewidth=3.0, label=f"Scout {scout_number} (this pass)"))

    # Start / Target markers
    if start_node and start_node in nodes:
        sx, sy = _offset_point(nodes[start_node]["utm_x"], nodes[start_node]["utm_y"])
        scatter = ax.scatter([sx], [sy], color="#477B9E", s=100, zorder=7, clip_on=False)
        new_artists.append(scatter)
        handles.append(Line2D([0], [0], marker="o", color="w", markerfacecolor="#477B9E", markersize=10, label="Start (Fire Station)"))
    if target_node and target_node in nodes:
        scatter = ax.scatter([nodes[target_node]["utm_x"]], [nodes[target_node]["utm_y"]],
                             color="#FF6F6F", s=100, zorder=7, clip_on=False)
        new_artists.append(scatter)
        handles.append(Line2D([0], [0], marker="o", color="w", markerfacecolor="#FF6F6F", markersize=10, label="Target (fire)"))

    status = {
        "reached": "reached target",
        "no_path": "no hazard-free path exists right now",
        "step_budget": "still searching -- ran out of step budget",
    }.get(scout_status, "reached target" if scout_route else "blocked / backtracked")

    ax.set_title(
        f"Scout {scout_number}/{num_scouts} -- {status}",
        fontsize=10, color="#555",
    )
    _place_legend(fig, ax, handles, fontsize=7.5)
    return new_artists


def create_carrier_canvas(nodes, edges, hazard_edges=None):
    fig, ax = plt.subplots(figsize=(9.6, 6.4))
    _draw_base_graph(ax, nodes, edges)
    base_handles = list(ROAD_LEGEND)
    _draw_random_hazards(ax, base_handles, nodes, hazard_edges)
    _style_axes(fig, ax)
    return fig, ax, base_handles


def update_carrier_frame(fig, ax, base_handles, nodes, top_routes,
                          carrier_id, carrier_number, num_carriers, rank, route,
                          current_node, status, carriers_completed,
                          start_node=None, target_node=None,
                          dynamic_artists=None, fire_origin_xy=None, fire_radius_m=None):
    if dynamic_artists:
        for artist in dynamic_artists:
            try:
                artist.remove()
            except Exception:
                pass

    new_artists = []
    handles = list(base_handles)

    # Live fire
    _draw_live_fire(ax, new_artists, handles, fire_origin_xy, fire_radius_m)

    # Ranked routes
    route_styles = [
        ("#60CE56", 3.0, "solid", "Rank 1 route"),
        ("#3B82C4", 2.6, (0, (6, 3)), "Rank 2 route"),
        ("#9B59B6", 2.2, (0, (2, 2)), "Rank 3 route"),
    ]
    for i, r in enumerate((top_routes or [])[:3]):
        color, width, style, label = route_styles[i]
        path = r["route"]
        rx = [nodes[n]["utm_x"] for n in path if n in nodes]
        ry = [nodes[n]["utm_y"] for n in path if n in nodes]
        line, = ax.plot(rx, ry, color=color, linewidth=width, linestyle=style, zorder=3 + i, clip_on=False)
        new_artists.append(line)
        handles.append(Line2D([0], [0], color=color, linewidth=width, linestyle=style, label=label))

    # Current carrier position
    if current_node and current_node in nodes:
        scatter = ax.scatter(
            [nodes[current_node]["utm_x"]], [nodes[current_node]["utm_y"]],
            color="#1E40AF", marker="s", s=90, zorder=8, clip_on=False
        )
        new_artists.append(scatter)
        handles.append(Line2D([0], [0], marker="s", color="w", markerfacecolor="#1E40AF",
                               markersize=9, label=f"{carrier_id} (rank {rank})"))

    # Start / Target
    if start_node and start_node in nodes:
        sx, sy = _offset_point(nodes[start_node]["utm_x"], nodes[start_node]["utm_y"])
        scatter = ax.scatter([sx], [sy], color="#477B9E", s=100, zorder=7, clip_on=False)
        new_artists.append(scatter)
        handles.append(Line2D([0], [0], marker="o", color="w", markerfacecolor="#477B9E", markersize=10, label="Start (Fire Station)"))
    if target_node and target_node in nodes:
        scatter = ax.scatter([nodes[target_node]["utm_x"]], [nodes[target_node]["utm_y"]],
                             color="#FF6F6F", s=100, zorder=7, clip_on=False)
        new_artists.append(scatter)
        handles.append(Line2D([0], [0], marker="o", color="w", markerfacecolor="#FF6F6F", markersize=10, label="Target (fire)"))

    ax.set_title(
        f"Carrier {carrier_number}/{num_carriers} ({carrier_id}, rank {rank}) -- {status}  "
        f"({carriers_completed}/{num_carriers} arrived)",
        fontsize=10, color="#555",
    )
    _place_legend(fig, ax, handles, fontsize=7.5)
    return new_artists


def plot_graph_with_route(results):
    nodes = results["nodes"]
    edges = results["edges"]
    top_routes = results.get("top_routes") or (
        [{"route": results["best_route"], "length_m": results["best_length_m"]}]
        if results.get("best_route") else []
    )

    fig, ax = plt.subplots(figsize=(9.6, 6.4))
    _draw_base_graph(ax, nodes, edges)

    handles = list(ROAD_LEGEND)

    # Random hazard edges (debris / collapsed structures)
    _draw_random_hazards(ax, handles, nodes, results.get("random_hazard_edges"))

    # Live fire at the end of the run
    if results.get("enable_fire") and results.get("final_fire_radius_m", 0) > 0:
        _draw_live_fire(
            ax, [], handles,
            fire_origin_xy=(results["fire_origin_x"], results["fire_origin_y"]),
            fire_radius_m=results["final_fire_radius_m"],
        )

    # Ranked routes
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
        ax.plot(rx, ry, color=color, linewidth=width, linestyle=style, zorder=4 + i, clip_on=False)
        handles.append(Line2D([0], [0], color=color, linewidth=width, linestyle=style, label=label))

    # Start & Target markers
    if top_routes:
        first_route = top_routes[0]["route"]
        rx = [nodes[n]["utm_x"] for n in first_route if n in nodes]
        ry = [nodes[n]["utm_y"] for n in first_route if n in nodes]
        sx, sy = _offset_point(rx[0], ry[0])
        ax.scatter([sx], [sy], color="#477B9E", s=100, zorder=6, clip_on=False)
        ax.scatter([rx[-1]], [ry[-1]], color="#FF6F6F", s=100, zorder=6, clip_on=False)
        handles.append(Line2D([0], [0], marker="o", color="w", markerfacecolor="#477B9E", markersize=10, label="Start (Fire Station)"))
        handles.append(Line2D([0], [0], marker="o", color="w", markerfacecolor="#FF6F6F", markersize=10, label="Target (fire)"))

    _style_axes(fig, ax)
    _place_legend(fig, ax, handles, fontsize=7.5)
    return fig