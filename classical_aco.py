"""
True Classical Ant Colony Optimization (baseline)
- Uniform evaporation
- Positive pheromone only
- Distance-only heuristic
- Homogeneous ants
- No Scout-Carrier hierarchy, no negative pheromone, no route zeroing
"""

import json
import math
import random
from collections import defaultdict
import networkx as nx
from pyproj import Transformer

# -------------------------------------------------
# Same constants as your enhanced system
# -------------------------------------------------
FIRE_STATION_LAT = 14.591934865975574
FIRE_STATION_LON = 120.95668125249459
FIRETRUCK_SPEED_KMH = 25
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


def get_largest_component_nodes(adj):
    G = nx.Graph()
    for u, neighbors in adj.items():
        for v in neighbors:
            G.add_edge(u, v)
    components = sorted(nx.connected_components(G), key=len, reverse=True)
    return list(components[0])


def nearest_node(nodes, x, y, node_pool):
    return min(node_pool, key=lambda n: math.dist((nodes[n]["utm_x"], nodes[n]["utm_y"]), (x, y)))


def route_length(route, lookup):
    return sum(lookup[(route[i], route[i+1])]["distance_m"] for i in range(len(route)-1))


def classical_aco(
    graph_file,
    num_ants=50,
    max_iterations=40,
    alpha=1.0,
    beta=2.0,
    rho=0.1,                    # uniform evaporation
    Q=100.0,                    # pheromone deposit constant
    num_random_hazards=5,
    random_hazard_seed=None,
    enable_fire=True,
    spread_rate_mps=1.0/60,
    scouting_phase_duration_s=600,
):
    """
    Pure Classical ACO on the Baseco graph.
    Returns a result dictionary comparable to the enhanced version.
    """
    nodes, edges = load_graph(graph_file)
    adj = build_adjacency(edges)
    lookup = build_edge_lookup(edges)
    largest_nodes = get_largest_component_nodes(adj)

    # Start = Fire Station, Target = centre of the largest component (or fire origin)
    station_x, station_y = latlon_to_utm(FIRE_STATION_LAT, FIRE_STATION_LON)
    start_node = nearest_node(nodes, station_x, station_y, largest_nodes)

    # Place fire origin roughly in the middle
    xs = [nodes[n]["utm_x"] for n in largest_nodes]
    ys = [nodes[n]["utm_y"] for n in largest_nodes]
    fire_x = sum(xs) / len(xs)
    fire_y = sum(ys) / len(ys)
    target_node = nearest_node(nodes, fire_x, fire_y, largest_nodes)

    # Simple random hazards (same idea as enhanced)
    random.seed(random_hazard_seed)
    all_edges = list(lookup.keys())
    random.shuffle(all_edges)
    blocked = set()
    for e in all_edges[:num_random_hazards*2]:  # both directions
        blocked.add(e)

    # Initialize pheromone
    pheromone = {edge: 0.1 for edge in lookup}

    best_route = None
    best_length = float("inf")

    for iteration in range(max_iterations):
        all_routes = []

        for ant in range(num_ants):
            current = start_node
            route = [current]
            visited = {current}
            steps = 0
            max_steps = len(nodes) * 3

            while current != target_node and steps < max_steps:
                candidates = []
                for neighbor in adj[current]:
                    if neighbor in visited:
                        continue
                    edge = (current, neighbor)
                    if edge in blocked:
                        continue

                    dist = lookup[edge]["distance_m"]
                    eta = 1.0 / dist if dist > 0 else 1e-6
                    tau = pheromone[edge]

                    prob = (tau ** alpha) * (eta ** beta)
                    candidates.append((neighbor, prob))

                if not candidates:
                    break  # dead end

                total = sum(p for _, p in candidates)
                if total <= 0:
                    break

                r = random.uniform(0, total)
                cum = 0.0
                next_node = None
                for node, p in candidates:
                    cum += p
                    if r <= cum:
                        next_node = node
                        break

                if next_node is None:
                    break

                route.append(next_node)
                visited.add(next_node)
                current = next_node
                steps += 1

            if current == target_node:
                length = route_length(route, lookup)
                all_routes.append((route, length))
                if length < best_length:
                    best_length = length
                    best_route = route

        # Classical pheromone update (uniform evaporation + positive deposit only)
        # 1. Evaporate
        for edge in pheromone:
            pheromone[edge] *= (1.0 - rho)

        # 2. Deposit (only on routes that reached the target)
        for route, length in all_routes:
            deposit = Q / length
            for i in range(len(route) - 1):
                edge = (route[i], route[i+1])
                pheromone[edge] += deposit
                # also the reverse direction (undirected)
                pheromone[(route[i+1], route[i])] += deposit

    # Prepare result in the same shape as the enhanced version
    eta_seconds = (best_length / FIRETRUCK_SPEED_MPS) if best_route else None

    return {
        "success": best_route is not None,
        "best_route": best_route,
        "best_length_m": best_length if best_route else None,
        "eta_seconds": eta_seconds,
        "num_verified_routes": 1 if best_route else 0,   # classical only keeps the single best
        "scouts_reached_target": None,                  # not applicable
        "carrier_successes": 1 if best_route else 0,
        "num_carriers": 1,
        "carrier_success_rate": 100.0 if best_route else 0.0,
        "avg_risk_pct": None,                           # classical does not use risk
        "avg_complexity_pct": None,
        "edges_blocked_final": len(blocked) // 2,
        "final_fire_radius_m": None,
    }