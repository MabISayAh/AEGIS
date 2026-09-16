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

# Purely cosmetic nudge applied when DRAWING the Start marker -- the
# underlying start node's utm_x/utm_y (used for actual routing) is left
# untouched. This only exists because the Start node in the current graph
# sits a little above where its roads visually intersect; if the graph is
# ever re-pulled and the offset stops looking right, just tune these two
# numbers (in meters, same units as utm_x/utm_y) or set both to 0.
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
            # clip_on=False: a road drawn right at the edge of the data
            # range would otherwise have its rendered stroke width sliced
            # in half by the axes boundary -- margins() only pads the data
            # coordinates, not the physical linewidth on top of them.
            ax.plot(x, y, color=color, linewidth=width, zorder=1, clip_on=False)


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
    # Padding around the plotted network -- without this, edges that sit
    # at the extreme top/right/etc. of the graph get drawn flush against
    # the axes border, which reads as "cropped" even though nothing is
    # actually cut off. Bumped up from 0.08 -- edges/markers right at the
    # data boundary still need visible breathing room around them.
    ax.margins(0.12)
    ax.set_aspect("equal")


def _place_legend(fig, ax, handles, fontsize=8):
    """Places the legend OUTSIDE the map (in a reserved right-hand strip)
    instead of floating on top of it via loc="upper right". Reserving the
    space with a FIXED subplots_adjust (not tight_layout, which
    recalculates the layout based on the actual title/legend text on each
    call) matters for two reasons:
      1. Streamlit's st.pyplot() doesn't apply bbox_inches="tight" at save
         time, so a legend placed outside the axes without reserved room
         would just get clipped at the figure's edge.
      2. tight_layout's auto-fit varies slightly frame to frame depending
         on title length (plot_scout_progress) or whether a title exists
         at all (plot_preview / plot_graph_with_route don't set one), so
         the map's box would subtly shift/resize between frames. Fixed
         fractions instead pin the map to the exact same pixel box on
         every frame, titled or not."""
    ax.legend(
        handles=handles, loc="upper left", bbox_to_anchor=(1.02, 1.0),
        frameon=False, fontsize=fontsize, borderaxespad=0.0,
    )
    fig.subplots_adjust(left=0.02, right=0.76, top=0.93, bottom=0.05)


def plot_preview(nodes, edges, fire_xy=None, start_xy=None, hazard_edges=None):
    """Live preview shown while adjusting sliders, before Run is clicked.
    `hazard_edges` (optional) draws the same random-hazard edges that will
    actually be used if Run is clicked right now -- see
    dashboard.py's compute_preview_hazards(), which mirrors
    simulation_backend.run_full_simulation()'s own hazard-picking logic with
    the same seed, so this is a true preview and not just a decoy."""
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
    """One animation frame during the run: THIS Scout's own path (orange,
    bold -- the visual focus of the frame), plus any routes already
    VERIFIED via the Tc confidence threshold (green/blue/purple, same
    palette as the final results map) drawn underneath so you can watch
    them accumulate as the swarm converges.

    There's no "iteration" here -- the ms Scout population is walked one
    agent at a time, so this is Scout `scout_number` of `num_scouts`, not
    a wave."""
    fig, ax = plt.subplots(figsize=(9.6, 6.4))
    _draw_base_graph(ax, nodes, edges)

    handles = list(ROAD_LEGEND)

    # Routes already verified (Tc consecutive identical paths) before this
    # Scout ran -- same 3-color scheme as the final results map, so a
    # route's color stays consistent from "verified" through to "ranked."
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

    # This Scout's own path, drawn last (on top) so it's what draws the eye.
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
        f"Scout {scout_number}/{num_scouts} -- {status}  "
        f"({len(verified_routes or [])}/3 paths verified)",
        fontsize=10, color="#555",
    )
    _style_axes(fig, ax)
    _place_legend(fig, ax, handles, fontsize=7.5)
    return fig


def create_scout_canvas(nodes, edges, hazard_edges=None):
    """Draws the static base graph (every road edge) ONCE and returns the
    reusable fig/ax plus the static road-type legend handles. This is the
    expensive part of plot_scout_progress -- pulling it out of the
    per-frame path is what makes update_scout_frame() cheap enough to call
    on every single Scout without skipping frames.

    `hazard_edges` (the permanent debris/collapsed-structure edges, same
    ones plot_preview and plot_graph_with_route draw) is drawn here too,
    once, as part of the static layer -- these don't change frame to
    frame, so there's no reason to pay the cost of redrawing them on every
    Scout the way the dynamic artists (routes, markers) are.
    """
    fig, ax = plt.subplots(figsize=(9.6, 6.4))
    _draw_base_graph(ax, nodes, edges)
    base_handles = list(ROAD_LEGEND)
    _draw_random_hazards(ax, base_handles, nodes, hazard_edges)
    _style_axes(fig, ax)
    return fig, ax, base_handles


def _draw_live_fire(ax, new_artists, handles, fire_origin_xy, fire_radius_m):
    """Draws the fire's CURRENT extent (not the final one) as a dynamic
    artist -- appended to new_artists so update_scout_frame/
    update_carrier_frame's existing remove-and-redraw cycle clears and
    regrows it every frame, same as routes/markers. Mirrors the styling
    of the final-result fire circle in plot_graph_with_route so the fire
    looks the same whether you're watching it live or looking at the
    result afterward. No-ops if fire_origin_xy/fire_radius_m aren't
    provided, so callers that don't have fire enabled don't need to
    special-case anything."""
    if fire_origin_xy is None or not fire_radius_m or fire_radius_m <= 0:
        return
    fx, fy = fire_origin_xy
    fire_circle = Circle(
        (fx, fy), fire_radius_m,
        facecolor="#FF6F6F", edgecolor="#CC3333",
        alpha=0.25, zorder=2, clip_on=False,
    )
    ax.add_patch(fire_circle)
    new_artists.append(fire_circle)
    star = ax.scatter([fx], [fy], color="#CC3333", marker="*", s=180, zorder=3, clip_on=False)
    new_artists.append(star)
    handles.append(Line2D([0], [0], marker="*", color="w", markerfacecolor="#CC3333", markersize=14, label="Fire origin"))
    handles.append(Line2D([0], [0], marker="o", color="w", markerfacecolor="#FF6F6F", markersize=10, alpha=0.5, label="Fire extent (current)"))


def update_scout_frame(fig, ax, base_handles, nodes, scout_number, num_scouts,
                        scout_route, verified_routes, best_route,
                        start_node=None, target_node=None, scout_status=None,
                        dynamic_artists=None, fire_origin_xy=None, fire_radius_m=None):
    """One animation frame, reusing the fig/ax from create_scout_canvas
    instead of rebuilding the base graph. Only removes/redraws the small
    set of artists that actually change frame to frame (verified routes,
    this Scout's path, start/target markers, title, legend) -- everything
    else on the canvas (all the road edges) is left completely untouched.
    Returns the new list of dynamic artists so the caller can pass it back
    in on the next call, to be removed in turn.
    """
    for artist in (dynamic_artists or []):
        try:
            artist.remove()
        except (ValueError, NotImplementedError):
            pass

    new_artists = []
    handles = list(base_handles)

    _draw_live_fire(ax, new_artists, handles, fire_origin_xy, fire_radius_m)

    verified_styles = [
        ("#60CE56", 2.8, "solid", "Verified route 1"),
        ("#3B82C4", 2.4, (0, (6, 3)), "Verified route 2"),
        ("#9B59B6", 2.0, (0, (2, 2)), "Verified route 3"),
    ]
    for i, route in enumerate((verified_routes or [])[:3]):
        color, width, style, label = verified_styles[i]
        rx = [nodes[n]["utm_x"] for n in route if n in nodes]
        ry = [nodes[n]["utm_y"] for n in route if n in nodes]
        (line,) = ax.plot(rx, ry, color=color, linewidth=width, linestyle=style, zorder=3 + i, clip_on=False)
        new_artists.append(line)
        handles.append(Line2D([0], [0], color=color, linewidth=width, linestyle=style, label=label))

    if scout_route:
        rx = [nodes[n]["utm_x"] for n in scout_route if n in nodes]
        ry = [nodes[n]["utm_y"] for n in scout_route if n in nodes]
        (line,) = ax.plot(rx, ry, color="#FFA94D", linewidth=3.0, zorder=6, clip_on=False)
        new_artists.append(line)
        handles.append(Line2D([0], [0], color="#FFA94D", linewidth=3.0, label=f"Scout {scout_number} (this pass)"))

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
        f"Scout {scout_number}/{num_scouts} -- {status}  "
        f"({len(verified_routes or [])}/3 paths verified)",
        fontsize=10, color="#555",
    )
    # ax.legend() replaces any previous legend on this axes automatically,
    # so the old one doesn't need to be tracked/removed by hand.
    _place_legend(fig, ax, handles, fontsize=7.5)
    return new_artists


def create_carrier_canvas(nodes, edges, hazard_edges=None):
    """Same static base-graph canvas as create_scout_canvas -- kept as a
    separate name so dashboard.py's Carrier phase doesn't have to reuse a
    function named after Scouts, even though the drawing is identical."""
    return create_scout_canvas(nodes, edges, hazard_edges=hazard_edges)


def update_carrier_frame(fig, ax, base_handles, nodes, top_routes, carrier_id,
                          carrier_number, num_carriers, rank, route, current_node,
                          status, carriers_completed, start_node=None,
                          target_node=None, dynamic_artists=None,
                          fire_origin_xy=None, fire_radius_m=None):
    """One animation frame during the Carrier phase: the (up to 3) ranked
    routes drawn faintly as background context, the specific route THIS
    carrier is currently committed to highlighted (matters once a carrier
    falls back off its original rank route), and a marker at the carrier's
    current node that moves frame to frame -- called once per Carrier step,
    so the truck marker visibly travels edge by edge instead of just
    snapping straight to the destination.
    """
    for artist in (dynamic_artists or []):
        try:
            artist.remove()
        except (ValueError, NotImplementedError):
            pass

    new_artists = []
    handles = list(base_handles)

    _draw_live_fire(ax, new_artists, handles, fire_origin_xy, fire_radius_m)

    rank_colors = {1: "#60CE56", 2: "#3B82C4", 3: "#9B59B6"}
    route_styles = [
        (rank_colors[1], 2.6, "solid", "Rank 1 route"),
        (rank_colors[2], 2.2, (0, (6, 3)), "Rank 2 route"),
        (rank_colors[3], 1.8, (0, (2, 2)), "Rank 3 route"),
    ]
    for i, route_info in enumerate((top_routes or [])[:3]):
        r = route_info["route"]
        color, width, style, label = route_styles[i]
        rx = [nodes[n]["utm_x"] for n in r if n in nodes]
        ry = [nodes[n]["utm_y"] for n in r if n in nodes]
        (line,) = ax.plot(rx, ry, color=color, linewidth=width, linestyle=style,
                           alpha=0.45, zorder=3 + i, clip_on=False)
        new_artists.append(line)
        handles.append(Line2D([0], [0], color=color, linewidth=width, linestyle=style, label=label))

    # The route this specific carrier is actually walking right now, drawn
    # bold and on top -- usually matches its assigned rank route, but can
    # differ after a fallback swap mid-journey.
    if route:
        rx = [nodes[n]["utm_x"] for n in route if n in nodes]
        ry = [nodes[n]["utm_y"] for n in route if n in nodes]
        (line,) = ax.plot(rx, ry, color=rank_colors.get(rank, "#FF8C00"), linewidth=3.4,
                           alpha=0.9, zorder=6, clip_on=False)
        new_artists.append(line)

    if current_node and current_node in nodes:
        cx, cy = nodes[current_node]["utm_x"], nodes[current_node]["utm_y"]
        marker_color = rank_colors.get(rank, "#FF8C00")
        scatter = ax.scatter([cx], [cy], color=marker_color, marker="s", s=170, zorder=8,
                              edgecolors="black", linewidths=0.9, clip_on=False)
        new_artists.append(scatter)
        label_artist = ax.annotate(
            carrier_id, (cx, cy), textcoords="offset points", xytext=(0, 11),
            fontsize=8, fontweight="bold", color="#333", ha="center", zorder=9,
        )
        new_artists.append(label_artist)
        handles.append(Line2D([0], [0], marker="s", color="w", markerfacecolor=marker_color,
                               markeredgecolor="black", markersize=10,
                               label=f"{carrier_id} (rank {rank})"))

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

    status_label = {
        "starting": "starting out",
        "moving": "en route",
        "reached": "reached target!",
        "blocked": "blocked -- no verified fallback available",
    }.get(status, status)
    ax.set_title(
        f"Carrier {carrier_number}/{num_carriers} ({carrier_id}, rank {rank}) -- {status_label}  "
        f"({carriers_completed}/{num_carriers} arrived)",
        fontsize=10, color="#555",
    )
    _place_legend(fig, ax, handles, fontsize=7.5)
    return new_artists


def plot_graph_with_route(results):
    nodes = results["nodes"]
    edges = results["edges"]
    top_routes = results.get("top_routes") or ([{"route": results["best_route"], "length_m": results["best_length_m"]}] if results["best_route"] else [])

    fig, ax = plt.subplots(figsize=(9.6, 6.4))
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
            alpha=0.25, zorder=2, clip_on=False,
        )
        ax.add_patch(fire_circle)
        ax.scatter([results["fire_origin_x"]], [results["fire_origin_y"]], color="#CC3333", marker="*", s=180, zorder=3, clip_on=False)
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
        ax.plot(rx, ry, color=color, linewidth=width, linestyle=style, zorder=4 + i, clip_on=False)
        handles.append(Line2D([0], [0], color=color, linewidth=width, linestyle=style, label=label))

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