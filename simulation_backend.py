"""
Importable version of the Scout/Carrier ACO simulation, built for
dashboard.py to call directly instead of running as a standalone script.

Includes:
- A live fire-spread model (hazard grows over time from a fire origin)
- Random static hazards (fallen debris/collapsed structures) to test
  whether agents correctly avoid them regardless of the fire
- Fixed start point at the Baseco Fire Station (real coordinates)
- Tracks the top 3 distinct routes found, not just the single best
"""

import json
import math
import random
from collections import defaultdict

import networkx as nx
from pyproj import Transformer

from aco_core.hazard import HazardTier, HazardReading, adaptive_evaporation, unified_pheromone_update
from aco_core.desirability import EdgeAttributes, normalize_edge_attributes, desirability, transition_probability
from aco_core.verification import VerificationTracker
from aco_core.agents import Carrier
from aco_core.fire_model import FireModel

# Baseco Fire Station -- fixed real-world starting point for all Scout and
# Carrier agents, so there's no ambiguity about where agents originate.
FIRE_STATION_LAT = 14.591934865975574
FIRE_STATION_LON = 120.95668125249459

FIRETRUCK_SPEED_KMH = 25  # standard heavy fire apparatus average speed, Metro Manila
FIRETRUCK_SPEED_MPS = FIRETRUCK_SPEED_KMH * 1000 / 3600


def latlon_to_utm(lat, lon, epsg="EPSG:32651"):
    transformer = Transformer.from_crs("EPSG:4326", epsg, always_xy=True)
    x, y = transformer.transform(lon, lat)
    return x, y


def load_graph(path):
    with open(path) as f:
        data = json.load(f)
    return data["nodes"], data["edges"]


def build_adjacency(edges):
    adj = defaultdict(set)
    for e in edges.values():
        adj[e["from"]].add(e["to"])
        adj[e["to"]].add(e["from"])
    return adj


def build_edge_lookup(edges):
    lookup = {}
    for e in edges.values():
        lookup[(e["from"], e["to"])] = e
        lookup[(e["to"], e["from"])] = e
    return lookup


def build_edge_midpoints(lookup, nodes):
    midpoints = {}
    for (u, v) in lookup:
        if u in nodes and v in nodes:
            mx = (nodes[u]["utm_x"] + nodes[v]["utm_x"]) / 2
            my = (nodes[u]["utm_y"] + nodes[v]["utm_y"]) / 2
            midpoints[(u, v)] = (mx, my)
    return midpoints


def get_largest_component_nodes(adj):
    G = nx.Graph()
    for u, neighbors in adj.items():
        for v in neighbors:
            G.add_edge(u, v)
    components = sorted(nx.connected_components(G), key=len, reverse=True)
    return list(components[0]), len(components)


def nearest_node(nodes, x, y, node_pool):
    return min(node_pool, key=lambda n: math.dist((nodes[n]["utm_x"], nodes[n]["utm_y"]), (x, y)))


def compute_baseline_corridor_edges(nodes, lookup, start, target, hop_radius=1):
    """Shortest path from start to target by raw distance (ignoring hazard),
    used only to define a realistic "corridor" for placing random hazards --
    so debris/collapsed structures land somewhere an agent would actually
    have wanted to walk, not on a random unrelated edge across the map."""
    G = nx.Graph()
    for (u, v), e in lookup.items():
        G.add_edge(u, v, weight=e["distance_m"])
    try:
        path_nodes = nx.shortest_path(G, start, target, weight="weight")
    except nx.NetworkXNoPath:
        return set(lookup.keys())  # fallback: whole graph is fair game

    corridor_nodes = set(path_nodes)
    for _ in range(hop_radius):
        expanded = set(corridor_nodes)
        for n in corridor_nodes:
            expanded.update(G.neighbors(n))
        corridor_nodes = expanded

    corridor_edges = set()
    for (u, v) in lookup:
        if u in corridor_nodes and v in corridor_nodes:
            corridor_edges.add((u, v))
    return corridor_edges


def pick_random_hazard_edges(lookup, count, corridor_edges=None, exclude_nodes=(), seed=None):
    """Picks `count` distinct undirected edges to mark as permanently
    IMPASSABLE (fallen debris, collapsed roof/wall, etc.), independent of
    the fire. Restricted to `corridor_edges` when given, so hazards land on
    the way to the fire instead of scattered anywhere on the map. Returns a
    set containing BOTH directions of each picked edge."""
    rng = random.Random(seed)
    candidate_pool = corridor_edges if corridor_edges is not None else lookup.keys()

    undirected_seen = set()
    unique_edges = []
    for (u, v) in candidate_pool:
        key = frozenset((u, v))
        if key in undirected_seen:
            continue
        undirected_seen.add(key)
        if u in exclude_nodes or v in exclude_nodes:
            continue
        unique_edges.append((u, v))

    count = min(count, len(unique_edges))
    chosen = rng.sample(unique_edges, count) if count > 0 else []

    blocked = set()
    for (u, v) in chosen:
        blocked.add((u, v))
        blocked.add((v, u))
    return blocked


def roulette_pick(candidates):
    total = sum(p for _, p in candidates)
    if total <= 0:
        return None
    r = random.uniform(0, total)
    cum = 0.0
    for node, p in candidates:
        cum += p
        if r <= cum:
            return node
    return candidates[-1][0]


def run_one_scout(start, target, adj, normalized, pheromone, hazard_by_edge, w1, w2, w3, alpha, beta, max_steps):
    """Randomized DFS with backtracking. Edges marked IMPASSABLE (by fire
    OR by a random hazard) are removed from the candidate list entirely."""
    stack = [start]
    on_path = {start}
    steps = 0
    while stack and steps < max_steps:
        current = stack[-1]
        if current == target:
            return stack
        neighbors = [
            n for n in adj[current]
            if n not in on_path
            and hazard_by_edge.get((current, n), HazardTier.SAFE) != HazardTier.IMPASSABLE
        ]
        if not neighbors:
            on_path.discard(stack.pop())
            steps += 1
            continue
        allowed = {}
        for n in neighbors:
            d_n, r_n, c_n = normalized[(current, n)]
            eta = desirability(d_n, r_n, c_n, w1, w2, w3)
            tau = pheromone.get((current, n), 1.0)
            allowed[(current, n)] = (tau, eta)
        candidates = [
            (v, transition_probability(tau, eta, allowed, alpha, beta))
            for (u, v), (tau, eta) in allowed.items()
        ]
        next_node = roulette_pick(candidates)
        if next_node is None:
            on_path.discard(stack.pop())
            steps += 1
            continue
        stack.append(next_node)
        on_path.add(next_node)
        steps += 1
    return None


def route_length(route, lookup):
    return sum(lookup[(route[i], route[i + 1])]["distance_m"] for i in range(len(route) - 1))


def run_full_simulation(
    graph_file,
    w1, w2, w3,
    rho_min, rho_max,
    num_scouts,
    num_carriers,
    num_iterations=20,
    max_steps_per_scout=600,
    alpha=1.0, beta=1.0,
    delta_tau_plus=1.0, delta_tau_minus=1.5,
    start_node=None, target_node=None,
    fire_origin_x=None, fire_origin_y=None,
    spread_rate_mps=0.5,
    time_per_iteration_s=30,
    enable_fire=True,
    num_random_hazards=0,
    random_hazard_seed=None,
    progress_callback=None,
):
    nodes, edges = load_graph(graph_file)
    adj = build_adjacency(edges)
    lookup = build_edge_lookup(edges)
    midpoints = build_edge_midpoints(lookup, nodes)

    raw_attrs = {
        (u, v): EdgeAttributes(
            distance=e["distance_m"],
            risk=e.get("risk_score") or 5,
            turn_angle=e.get("turn_complexity_deg", 0),
        )
        for (u, v), e in lookup.items()
    }
    normalized = normalize_edge_attributes(raw_attrs)

    largest_nodes, num_components = get_largest_component_nodes(adj)

    # Default fire origin: geometric centroid of the largest component, if not given
    if fire_origin_x is None or fire_origin_y is None:
        xs = [nodes[n]["utm_x"] for n in largest_nodes]
        ys = [nodes[n]["utm_y"] for n in largest_nodes]
        fire_origin_x = sum(xs) / len(xs)
        fire_origin_y = sum(ys) / len(ys)

    # Target = nearest real node to the fire itself -- Carriers are trying
    # to REACH the emergency, not walk to an arbitrary far corner of the map.
    if target_node is None:
        target_node = nearest_node(nodes, fire_origin_x, fire_origin_y, largest_nodes)

    # Start = Baseco Fire Station, always -- fixed real-world coordinate,
    # no ambiguity about where Scouts/Carriers originate.
    if start_node is None:
        station_x, station_y = latlon_to_utm(FIRE_STATION_LAT, FIRE_STATION_LON)
        start_node = nearest_node(nodes, station_x, station_y, largest_nodes)

    fire_model = FireModel(
        origin_x=fire_origin_x, origin_y=fire_origin_y,
        spread_rate_mps=spread_rate_mps if enable_fire else 0.0,
        time_per_iteration_s=time_per_iteration_s,
    )

    corridor_edges = compute_baseline_corridor_edges(nodes, lookup, start_node, target_node, hop_radius=1)
    random_hazard_edges = pick_random_hazard_edges(
        lookup, num_random_hazards, corridor_edges=corridor_edges,
        exclude_nodes={start_node, target_node}, seed=random_hazard_seed,
    )

    pheromone = {edge: 1.0 for edge in lookup}
    tracker = VerificationTracker(scout_population=num_scouts, window_size=num_scouts)

    best_route, best_length = None, float("inf")
    # NEW: elapsed_s at the moment best_route was actually found -- the
    # Carrier phase needs this so it isn't walking the route through a much
    # older (falsely aged) fire than what the route was verified against.
    best_route_elapsed_s = 0.0
    discovered_routes = {}  # tuple(route) -> length_m, deduped across all iterations
    scout_successes_last_iter = 0
    # Iteration-level, not agent-level: how many of the num_iterations waves
    # had at least one scout reach the target. Chosen over a raw cumulative
    # agent count (e.g. "12/1200") because that number is num_scouts *
    # num_iterations under the hood -- technically correct, but confusing
    # when what you set on the slider was "60 scouts," not "1200."
    iterations_with_success = 0
    edges_blocked_last_iter = 0

    for iteration in range(num_iterations):
        elapsed_s = iteration * time_per_iteration_s

        hazard_by_edge = {}
        for edge, (mx, my) in midpoints.items():
            if edge in random_hazard_edges:
                hazard_by_edge[edge] = HazardTier.IMPASSABLE
            else:
                hazard_by_edge[edge] = fire_model.hazard_tier_for_point(mx, my, elapsed_s)
        # NEW: only count edges genuinely blocked by the fire itself here --
        # this used to also include random-hazard edges (which are static
        # and unrelated to fire growth), silently doubling this count and
        # making "Edges Blocked by Fire" misleading whenever hazards were
        # enabled. Random hazards are already reported separately via
        # num_random_hazards in the returned dict.
        edges_blocked_last_iter = sum(
            1 for edge, h in hazard_by_edge.items()
            if h == HazardTier.IMPASSABLE and edge not in random_hazard_edges
        )

        successful_routes = []
        for _s in range(num_scouts):
            route = run_one_scout(start_node, target_node, adj, normalized, pheromone, hazard_by_edge, w1, w2, w3, alpha, beta, max_steps_per_scout)
            if route:
                length = route_length(route, lookup)
                successful_routes.append((route, length))
                discovered_routes[tuple(route)] = length
                if length < best_length:
                    best_length, best_route = length, route
                    best_route_elapsed_s = elapsed_s
                for i in range(len(route) - 1):
                    tracker.record_scout_pass((route[i], route[i + 1]), True)

        scout_successes_last_iter = len(successful_routes)
        if successful_routes:
            iterations_with_success += 1

        for edge_pair in lookup:
            tier = hazard_by_edge.get(edge_pair, HazardTier.SAFE)
            h_reading = HazardReading(tier)
            h_norm = h_reading.h_normalized
            rho = adaptive_evaporation(rho_min, rho_max, h_norm)
            pheromone[edge_pair] = unified_pheromone_update(
                pheromone[edge_pair], rho, h_norm, delta_tau_plus, delta_tau_minus,
            )
        for route, length in successful_routes:
            for i in range(len(route) - 1):
                edge = (route[i], route[i + 1])
                pheromone[edge] = pheromone.get(edge, 1.0) + (10.0 / length)

        if progress_callback is not None:
            progress_callback(
                iteration=iteration + 1,
                num_iterations=num_iterations,
                scout_routes=[r for r, _ in successful_routes],
                best_route=best_route,
            )

    # Top 3 distinct routes discovered across the whole run, shortest first.
    # Computed BEFORE the Carrier phase now (used to be after) so it can be
    # handed to the Carrier as real fallback options instead of just the
    # single best route.
    top_routes = [
        {"route": list(route), "length_m": length}
        for route, length in sorted(discovered_routes.items(), key=lambda kv: kv[1])[:3]
    ]

    # Carrier phase -- fire keeps spreading while Carriers walk, so each
    # Carrier step rechecks hazard at the CURRENT elapsed time. Random
    # hazard edges stay blocked the whole time, same as during scouting.
    #
    # FIXED: previously this started the clock at the end of ALL scouting
    # (num_iterations * time_per_iteration_s) even if best_route was found
    # much earlier, and advanced a full scouting-iteration's worth of time
    # (time_per_iteration_s) per single edge hop -- both of which made the
    # fire look far older than it should by the time a Carrier evaluated
    # each edge, causing routes that were clean when found to read as
    # blocked almost immediately. Now: start from when best_route was
    # actually found, and advance by real travel time per edge.
    def carrier_hazard_lookup_factory():
        state = {"elapsed_s": best_route_elapsed_s}

        def lookup_fn(edge):
            if edge in random_hazard_edges:
                return HazardReading(HazardTier.IMPASSABLE)
            edge_info = lookup.get(edge)
            step_seconds = (edge_info["distance_m"] / FIRETRUCK_SPEED_MPS) if edge_info else time_per_iteration_s
            state["elapsed_s"] += step_seconds
            mx, my = midpoints.get(edge, (fire_model.origin_x, fire_model.origin_y))
            tier = fire_model.hazard_tier_for_point(mx, my, state["elapsed_s"])
            return HazardReading(tier)

        return lookup_fn

    carrier_successes = 0
    if best_route:
        # FIXED: was [best_route] only, so the Carrier's fallback logic
        # (_handle_blocked_edge) had nothing to actually fall back to and
        # would fail outright the first time any edge read at or above its
        # hazard_threshold. Now it gets the real top-3 routes.
        carrier_route_rank_list = [r["route"] for r in top_routes] if top_routes else [best_route]
        for _ in range(num_carriers):
            carrier = Carrier(
                carrier_id="C",
                current_node=best_route[0],
                committed_route=best_route,
                route_rank_list=carrier_route_rank_list,
                hazard_lookup=carrier_hazard_lookup_factory(),
                # FIXED: was HazardTier.MODERATE (the default). Since
                # target_node is defined as the node nearest the fire
                # itself, the final approach to ANY route is almost always
                # going to read at least MODERATE -- blocking on that made
                # arrival close to structurally impossible. Matching
                # Scouts' own IMPASSABLE-only threshold instead.
                hazard_threshold=HazardTier.IMPASSABLE,
            )
            for _step in range(len(best_route) + 5):
                if carrier.current_node == best_route[-1]:
                    carrier_successes += 1
                    break
                result = carrier.next_step(tracker, pheromone)
                if result is None:
                    break

    final_fire_radius_m = fire_model.radius_at(num_iterations * time_per_iteration_s)
    eta_seconds = (best_length / FIRETRUCK_SPEED_MPS) if best_route else None

    # Route-quality percentages for the Analytics page: average normalized
    # D/R/C across the best route's edges, as a 0-100 scale.
    avg_distance_pct = avg_complexity_pct = avg_risk_pct = None
    if best_route:
        d_vals, r_vals, c_vals = [], [], []
        for i in range(len(best_route) - 1):
            edge = (best_route[i], best_route[i + 1])
            d_n, r_n, c_n = normalized[edge]
            d_vals.append(d_n)
            r_vals.append(r_n)
            c_vals.append(c_n)
        avg_distance_pct = round(100 * sum(d_vals) / len(d_vals))
        avg_risk_pct = round(100 * sum(r_vals) / len(r_vals))
        avg_complexity_pct = round(100 * sum(c_vals) / len(c_vals))

    return {
        "success": best_route is not None,
        "best_route": best_route,
        "best_length_m": best_length if best_route else None,
        "top_routes": top_routes,
        "start_node": start_node,
        "target_node": target_node,
        "num_components": num_components,
        "scout_successes_last_iter": scout_successes_last_iter,
        "iterations_with_success": iterations_with_success,
        "num_iterations": num_iterations,
        "num_scouts": num_scouts,
        "carrier_successes": carrier_successes,
        "num_carriers": num_carriers,
        "nodes": nodes,
        "edges": edges,
        "fire_origin_x": fire_origin_x,
        "fire_origin_y": fire_origin_y,
        "final_fire_radius_m": final_fire_radius_m,
        "edges_blocked_last_iter": edges_blocked_last_iter,
        "enable_fire": enable_fire,
        "random_hazard_edges": list(random_hazard_edges),
        "num_random_hazards": num_random_hazards,
        "eta_seconds": eta_seconds,
        "firetruck_speed_kmh": FIRETRUCK_SPEED_KMH,
        "avg_distance_pct": avg_distance_pct,
        "avg_complexity_pct": avg_complexity_pct,
        "avg_risk_pct": avg_risk_pct,
    }