"""
Deterministic baselines for thesis comparison:
- Dijkstra (pure shortest path on distance)
- A* (shortest path with Euclidean heuristic)

Both respect the same random-hazard edges used by ACO trials
so the comparison is fair under identical blockage conditions.
"""

import json
import math
import heapq
import random
from collections import defaultdict

import networkx as nx
from pyproj import Transformer

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
    return min(node_pool, key=lambda n: math.dist(
        (nodes[n]["utm_x"], nodes[n]["utm_y"]), (x, y)
    ))


def pick_random_hazard_edges(lookup, count, seed=None):
    """Same idea as simulation_backend – both directions blocked."""
    rng = random.Random(seed)
    undirected = set()
    unique = []
    for (u, v) in lookup:
        key = frozenset((u, v))
        if key not in undirected:
            undirected.add(key)
            unique.append((u, v))
    count = min(count, len(unique))
    chosen = rng.sample(unique, count) if count > 0 else []
    blocked = set()
    for (u, v) in chosen:
        blocked.add((u, v))
        blocked.add((v, u))
    return blocked


def route_length(route, lookup):
    return sum(lookup[(route[i], route[i + 1])]["distance_m"]
               for i in range(len(route) - 1))


def dijkstra(start, target, adj, lookup, blocked):
    """Classic Dijkstra on distance, skipping blocked edges."""
    dist = {start: 0.0}
    prev = {}
    pq = [(0.0, start)]
    visited = set()

    while pq:
        d, u = heapq.heappop(pq)
        if u in visited:
            continue
        visited.add(u)
        if u == target:
            break
        for v in adj[u]:
            if (u, v) in blocked:
                continue
            edge = lookup.get((u, v))
            if edge is None:
                continue
            nd = d + edge["distance_m"]
            if v not in dist or nd < dist[v]:
                dist[v] = nd
                prev[v] = u
                heapq.heappush(pq, (nd, v))

    if target not in prev and start != target:
        return None, None

    # reconstruct
    route = [target]
    cur = target
    while cur != start:
        cur = prev[cur]
        route.append(cur)
    route.reverse()
    return route, dist[target]


def astar(start, target, adj, lookup, blocked, nodes):
    """A* with Euclidean heuristic on UTM coordinates."""
    def h(n):
        return math.dist(
            (nodes[n]["utm_x"], nodes[n]["utm_y"]),
            (nodes[target]["utm_x"], nodes[target]["utm_y"]),
        )

    g = {start: 0.0}
    f = {start: h(start)}
    prev = {}
    pq = [(f[start], start)]
    visited = set()

    while pq:
        _, u = heapq.heappop(pq)
        if u in visited:
            continue
        visited.add(u)
        if u == target:
            break
        for v in adj[u]:
            if (u, v) in blocked:
                continue
            edge = lookup.get((u, v))
            if edge is None:
                continue
            ng = g[u] + edge["distance_m"]
            if v not in g or ng < g[v]:
                g[v] = ng
                f[v] = ng + h(v)
                prev[v] = u
                heapq.heappush(pq, (f[v], v))

    if target not in prev and start != target:
        return None, None

    route = [target]
    cur = target
    while cur != start:
        cur = prev[cur]
        route.append(cur)
    route.reverse()
    return route, g[target]


def run_baseline(algorithm, graph_file, num_random_hazards=5, random_hazard_seed=None):
    """
    algorithm: "dijkstra" or "astar"
    Returns a result dict comparable to the ACO batch outputs.
    """
    nodes, edges = load_graph(graph_file)
    adj = build_adjacency(edges)
    lookup = build_edge_lookup(edges)
    largest = get_largest_component_nodes(adj)

    station_x, station_y = latlon_to_utm(FIRE_STATION_LAT, FIRE_STATION_LON)
    start = nearest_node(nodes, station_x, station_y, largest)

    xs = [nodes[n]["utm_x"] for n in largest]
    ys = [nodes[n]["utm_y"] for n in largest]
    fire_x = sum(xs) / len(xs)
    fire_y = sum(ys) / len(ys)
    target = nearest_node(nodes, fire_x, fire_y, largest)

    blocked = pick_random_hazard_edges(lookup, num_random_hazards, seed=random_hazard_seed)

    if algorithm == "dijkstra":
        route, length = dijkstra(start, target, adj, lookup, blocked)
    elif algorithm == "astar":
        route, length = astar(start, target, adj, lookup, blocked, nodes)
    else:
        raise ValueError("algorithm must be 'dijkstra' or 'astar'")

    if route is None:
        return {
            "success": False,
            "best_length_m": None,
            "eta_seconds": None,
            "num_verified_routes": 0,
            "carrier_success_rate": 0.0,
        }

    eta = length / FIRETRUCK_SPEED_MPS
    return {
        "success": True,
        "best_route": route,
        "best_length_m": length,
        "eta_seconds": eta,
        "num_verified_routes": 1,          # deterministic algorithms return one path
        "carrier_success_rate": 100.0,
    }