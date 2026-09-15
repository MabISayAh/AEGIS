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
    """Randomized DFS with backtracking, using a PERMANENT tabu list --
    once a node is visited it is never reconsidered for the rest of this
    Scout's search, not just while it's on the currently active path."""
    stack = [start]
    visited = {start}
    traversed_edges = set()
    steps = 0
    while stack and steps < max_steps:
        current = stack[-1]
        if current == target:
            return stack, traversed_edges, "reached"
        neighbors = [
            n for n in adj[current]
            if n not in visited
            and hazard_by_edge.get((current, n), HazardTier.SAFE) != HazardTier.IMPASSABLE
        ]
        if not neighbors:
            stack.pop()  # dead end -- backtrack, but leave `current` in
                          # `visited` permanently so it's never retried
            steps += 1
            continue
        allowed = {}
        for n in neighbors:
            d_n, r_n, c_n = normalized[(current, n)]
            eta = desirability(d_n, r_n, c_n, w1, w2, w3)
            tau = pheromone.get((current, n), 0.0)
            allowed[(current, n)] = (tau, eta)
        candidates = [
            (v, transition_probability(tau, eta, allowed, alpha, beta))
            for (u, v), (tau, eta) in allowed.items()
        ]
        next_node = roulette_pick(candidates)
        if next_node is None:
            stack.pop()
            steps += 1
            continue
        traversed_edges.add((current, next_node))
        stack.append(next_node)
        visited.add(next_node)
        steps += 1
    status = "no_path" if not stack else "step_budget"
    return None, traversed_edges, status



def route_length(route, lookup):
    return sum(lookup[(route[i], route[i + 1])]["distance_m"] for i in range(len(route) - 1))


PIVOT_PENALTY_FACTOR = 0.1  # temporary decay applied to a verified route
                             # to force the swarm to pivot away from
                             # over-converging on one path


def run_full_simulation(
    graph_file,
    w1, w2, w3,
    rho_min, rho_max,
    num_scouts,
    num_carriers,
    max_steps_per_scout=None,
    alpha=1.0, beta=1.0,          # ALPHA lowered to 0.5 to encourage spreading out
    delta_tau_plus=1.0, delta_tau_minus=1.0,
    confidence_fraction=0.05,     # Tc = confidence_fraction * num_scouts (kept at 0.05)
    start_node=None, target_node=None,
    fire_origin_x=None, fire_origin_y=None,
    spread_rate_mps=0.5,
    time_step_s=30,               # generic time unit
    scouting_phase_duration_s=600,  # total wall-clock time the fire is allowed to grow
    enable_fire=True,
    num_random_hazards=0,
    random_hazard_seed=None,
    progress_callback=None,
    carrier_progress_callback=None,
):
    nodes, edges = load_graph(graph_file)
    adj = build_adjacency(edges)
    lookup = build_edge_lookup(edges)
    midpoints = build_edge_midpoints(lookup, nodes)

    if max_steps_per_scout is None:
        max_steps_per_scout = max(800, len(nodes) * 4)

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

    if fire_origin_x is None or fire_origin_y is None:
        xs = [nodes[n]["utm_x"] for n in largest_nodes]
        ys = [nodes[n]["utm_y"] for n in largest_nodes]
        fire_origin_x = sum(xs) / len(xs)
        fire_origin_y = sum(ys) / len(ys)

    if target_node is None:
        target_node = nearest_node(nodes, fire_origin_x, fire_origin_y, largest_nodes)

    if start_node is None:
        station_x, station_y = latlon_to_utm(FIRE_STATION_LAT, FIRE_STATION_LON)
        start_node = nearest_node(nodes, station_x, station_y, largest_nodes)

    fire_model = FireModel(
        origin_x=fire_origin_x, origin_y=fire_origin_y,
        spread_rate_mps=spread_rate_mps if enable_fire else 0.0,
        time_per_iteration_s=time_step_s,
    )

    corridor_edges = compute_baseline_corridor_edges(nodes, lookup, start_node, target_node, hop_radius=1)
    random_hazard_edges = pick_random_hazard_edges(
        lookup, num_random_hazards, corridor_edges=corridor_edges,
        exclude_nodes={start_node, target_node}, seed=random_hazard_seed,
    )

    pheromone = {edge: 0.01 for edge in lookup}
    confidence_threshold = max(1, round(confidence_fraction * num_scouts))
    tracker = VerificationTracker(
        scout_population=num_scouts, window_size=num_scouts,
        min_fraction=confidence_fraction,
    )

    discovered_routes = {}
    route_first_seen_elapsed = {}

    route_visit_counts = {}
    zeroed_edges = set()  # edges belonging to verified routes, permanently pinned to 0.0
    verified_routes = []
    verified_routes_seen = set()
    early_termination = False

    scouts_reached_target = 0
    scouts_no_path = 0
    scouts_step_budget = 0
    edges_blocked_final = 0
    scouts_run = 0

    for scout_index in range(num_scouts):
        progress_fraction = scout_index / num_scouts
        elapsed_s = progress_fraction * scouting_phase_duration_s

        hazard_by_edge = {}
        for edge, (mx, my) in midpoints.items():
            if edge in random_hazard_edges:
                hazard_by_edge[edge] = HazardTier.IMPASSABLE
            else:
                hazard_by_edge[edge] = fire_model.hazard_tier_for_point(mx, my, elapsed_s)

        edges_blocked_final = sum(
            1 for edge, h in hazard_by_edge.items()
            if h == HazardTier.IMPASSABLE and edge not in random_hazard_edges
        )

        route, traversed, scout_status = run_one_scout(start_node, target_node, adj, normalized, pheromone, hazard_by_edge, w1, w2, w3, alpha, beta, max_steps_per_scout)
        scouts_run = scout_index + 1

        if route:
            scouts_reached_target += 1
        elif scout_status == "no_path":
            scouts_no_path += 1
        else:
            scouts_step_budget += 1

        if route:
            length = route_length(route, lookup)
            route_key = tuple(route)
            if route_key not in discovered_routes:
                route_first_seen_elapsed[route_key] = elapsed_s
            discovered_routes[route_key] = length
            for i in range(len(route) - 1):
                tracker.record_scout_pass((route[i], route[i + 1]), True)

            # Count total visits to this exact route across ALL scouts so far,
            # not just consecutive repeats. A route is verified once it has
            # accumulated `confidence_threshold` visits in total, regardless
            # of whether those visits happened back-to-back or were spread
            # out among other scouts exploring different routes.
            route_visit_counts[route_key] = route_visit_counts.get(route_key, 0) + 1

            if route_visit_counts[route_key] == confidence_threshold:
                if route_key not in verified_routes_seen:
                    verified_routes.append(list(route))
                    verified_routes_seen.add(route_key)

                # --- COMPLETE PHEROMONE EVAPORATION ---
                # Completely wipe the pheromones of the verified path to 0.0
                # and PIN them there (added to zeroed_edges below). This
                # guarantees scouts won't keep getting funneled back onto an
                # already-verified route, forcing exploration elsewhere.
                if len(route) >= 2:
                    for i in range(len(route) - 1):
                        verified_edge = (route[i], route[i + 1])
                        pheromone[verified_edge] = 0.0
                        zeroed_edges.add(verified_edge)

                if len(verified_routes) == 3:
                    early_termination = True

        for edge_pair in traversed:
            if edge_pair in zeroed_edges:
                # This edge belongs to an already-verified route. Skip the
                # normal reward/penalty update so it stays pinned at 0.0
                # instead of being rewarded back up by this same pass
                # (or by any later scout that happens to cross it).
                pheromone[edge_pair] = 0.0
                continue
            tier = hazard_by_edge.get(edge_pair, HazardTier.SAFE)
            h_binary = HazardReading(tier).h_binary
            rho_ij = adaptive_evaporation(rho_min, rho_max, h_binary)
            pheromone[edge_pair] = unified_pheromone_update(
                pheromone.get(edge_pair, 0.0), rho_ij, h_binary,
                delta_tau_plus, delta_tau_minus,
            )

        if progress_callback is not None:
            progress_callback(
                scout_number=scout_index + 1,
                num_scouts=num_scouts,
                scout_route=route,
                scout_status=scout_status,
                scout_traversed_edges=list(traversed),
                verified_routes=[list(r) for r in verified_routes],
                best_route=verified_routes[0] if verified_routes else None,
            )

        if early_termination:
            break

    final_routes = list(verified_routes)
    if len(final_routes) < 3:
        remaining = sorted(discovered_routes.items(), key=lambda kv: kv[1])
        for route_key, _length in remaining:
            if len(final_routes) == 3:
                break
            if route_key in verified_routes_seen:
                continue
            final_routes.append(list(route_key))

    top_routes = sorted(
        (
            {"route": route, "length_m": route_length(route, lookup)}
            for route in final_routes
        ),
        key=lambda r: r["length_m"],
    )

    best_route = top_routes[0]["route"] if top_routes else None
    best_length = top_routes[0]["length_m"] if top_routes else float("inf")
    best_route_elapsed_s = route_first_seen_elapsed.get(tuple(best_route), 0.0) if best_route else 0.0

    def carrier_hazard_lookup_factory():
        state = {"elapsed_s": best_route_elapsed_s}

        def lookup_fn(edge):
            if edge in random_hazard_edges:
                return HazardReading(HazardTier.IMPASSABLE)
            edge_info = lookup.get(edge)
            step_seconds = (edge_info["distance_m"] / FIRETRUCK_SPEED_MPS) if edge_info else time_step_s
            state["elapsed_s"] += step_seconds
            mx, my = midpoints.get(edge, (fire_model.origin_x, fire_model.origin_y))
            tier = fire_model.hazard_tier_for_point(mx, my, state["elapsed_s"])
            return HazardReading(tier)

        return lookup_fn

    carrier_successes = 0
    if top_routes:
        carrier_route_rank_list = [r["route"] for r in top_routes]
        n_ranks = len(carrier_route_rank_list)
        for i in range(num_carriers):
            rank = (i // 3) % n_ranks
            assigned_route = carrier_route_rank_list[rank]
            carrier = Carrier(
                carrier_id=f"C{i + 1}",
                current_node=assigned_route[0],
                committed_route=assigned_route,
                route_rank_list=carrier_route_rank_list,
                hazard_lookup=carrier_hazard_lookup_factory(),
                hazard_threshold=HazardTier.IMPASSABLE,
            )
            total_steps = len(assigned_route) + 5

            if carrier_progress_callback is not None:
                carrier_progress_callback(
                    carrier_id=carrier.carrier_id, carrier_number=i + 1, num_carriers=num_carriers,
                    rank=rank + 1, route=carrier.committed_route, current_node=carrier.current_node,
                    step=0, total_steps=total_steps, status="starting",
                    carriers_completed=carrier_successes, top_routes=top_routes,
                )

            succeeded = False
            for step_num in range(1, total_steps + 1):
                if carrier.current_node == target_node:
                    succeeded = True
                    break
                result = carrier.next_step(tracker, pheromone)
                if carrier_progress_callback is not None:
                    carrier_progress_callback(
                        carrier_id=carrier.carrier_id, carrier_number=i + 1, num_carriers=num_carriers,
                        rank=rank + 1, route=carrier.committed_route, current_node=carrier.current_node,
                        step=step_num, total_steps=total_steps,
                        status="moving" if result is not None else "blocked",
                        carriers_completed=carrier_successes, top_routes=top_routes,
                    )
                if result is None:
                    break

            if carrier.current_node == target_node:
                succeeded = True
            if succeeded:
                carrier_successes += 1

            if carrier_progress_callback is not None:
                carrier_progress_callback(
                    carrier_id=carrier.carrier_id, carrier_number=i + 1, num_carriers=num_carriers,
                    rank=rank + 1, route=carrier.committed_route, current_node=carrier.current_node,
                    step=total_steps, total_steps=total_steps,
                    status="reached" if succeeded else "blocked",
                    carriers_completed=carrier_successes, top_routes=top_routes,
                )

    final_fire_radius_m = fire_model.radius_at((scouts_run / num_scouts) * scouting_phase_duration_s)
    eta_seconds = (best_length / FIRETRUCK_SPEED_MPS) if best_route else None

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
        "scouts_reached_target": scouts_reached_target,
        "scouts_no_path": scouts_no_path,
        "scouts_step_budget": scouts_step_budget,
        "max_steps_per_scout": max_steps_per_scout,
        "scouts_run": scouts_run,
        "early_termination": early_termination,
        "num_scouts": num_scouts,
        "carrier_successes": carrier_successes,
        "num_carriers": num_carriers,
        "nodes": nodes,
        "edges": edges,
        "fire_origin_x": fire_origin_x,
        "fire_origin_y": fire_origin_y,
        "final_fire_radius_m": final_fire_radius_m,
        "edges_blocked_final": edges_blocked_final,
        "enable_fire": enable_fire,
        "random_hazard_edges": list(random_hazard_edges),
        "num_random_hazards": num_random_hazards,
        "eta_seconds": eta_seconds,
        "firetruck_speed_kmh": FIRETRUCK_SPEED_KMH,
        "avg_distance_pct": avg_distance_pct,
        "avg_complexity_pct": avg_complexity_pct,
        "avg_risk_pct": avg_risk_pct,
    }