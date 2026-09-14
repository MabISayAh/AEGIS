"""
Normalized desirability (eta) and the ACO transition probability rule.

Normalizing D/R/C first means w1/w2/w3 actually behave like relative
importance weights.
"""

from dataclasses import dataclass
from typing import Dict, Tuple

Edge = Tuple[str, str]


@dataclass
class EdgeAttributes:
    distance: float     # D_ij, meters
    risk: float          # R_ij, raw structural-risk score
    turn_angle: float    # C_ij, degrees


def normalize_edge_attributes(
    edges: Dict[Edge, EdgeAttributes]
) -> Dict[Edge, Tuple[float, float, float]]:
    """
    Min-max normalize D, R, C across the whole graph.

    Returns {edge: (D', R', C')}, each in [0, 1].
    """
    d_max = max((e.distance for e in edges.values()), default=1.0) or 1.0
    r_max = max((e.risk for e in edges.values()), default=1.0) or 1.0
    c_max = max((e.turn_angle for e in edges.values()), default=1.0) or 1.0

    normalized = {}
    for edge, attrs in edges.items():
        normalized[edge] = (
            attrs.distance / d_max,
            attrs.risk / r_max,
            attrs.turn_angle / c_max,
        )
    return normalized


def desirability(
    d_norm: float, r_norm: float, c_norm: float,
    w1: float, w2: float, w3: float,
) -> float:
    """
    eta_ij = 1 / (w1*D'_ij + w2*R'_ij + w3*C'_ij)

    w1 + w2 + w3 should sum to 1.
    """
    denom = (w1 * d_norm) + (w2 * r_norm) + (w3 * c_norm)
    if denom <= 0:
        return float("inf")  # zero-cost edge: maximally desirable
    return 1.0 / denom


def transition_probability(
    tau_ij: float, eta_ij: float,
    allowed_edges: Dict[Edge, Tuple[float, float]],
    alpha: float, beta: float,
) -> float:
    """
    P_ij^k(t) = [tau_ij(t)]^alpha * [eta_ij]^beta
                / sum_{l in allowed_k} [tau_il(t)]^alpha * [eta_il]^beta

    allowed_edges: {edge: (tau, eta)} for every edge currently reachable
    from the Scout's node right now -- rebuild this fresh at each step,
    since tau changes every iteration.
    """
    numerator = (tau_ij ** alpha) * (eta_ij ** beta)
    denominator = sum(
        (tau ** alpha) * (eta ** beta)
        for tau, eta in allowed_edges.values()
    )
    if denominator == 0:
        return 0.0
    return numerator / denominator