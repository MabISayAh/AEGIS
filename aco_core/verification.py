"""
Frequency-based verification, with a sliding window so old Scout
confirmations don't stay trusted forever while the fire keeps spreading.
"""

from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Dict, List, Tuple

Edge = Tuple[str, str]


@dataclass
class EdgeVerification:
    """Tracks recent clean (non-hazardous) Scout traversals of one edge."""
    window_size: int
    recent_passes: Deque[bool] = field(default_factory=deque)

    def record_pass(self, was_clean: bool) -> None:
        self.recent_passes.append(was_clean)
        if len(self.recent_passes) > self.window_size:
            self.recent_passes.popleft()

    @property
    def frequency(self) -> int:
        """f_ij(t): count of clean passes inside the current window."""
        return sum(self.recent_passes)


class VerificationTracker:
    """
    One EdgeVerification per edge, plus the f_min threshold Carriers
    require before they'll trust a route.

    f_min defaults to 5% of the Scout population (Tc = 0.05 * ms, per the
    algorithm's confidence threshold) -- tune this in your experiments
    section as one of your parameters.
    """

    def __init__(self, scout_population: int, window_size: int = 10,
                 min_fraction: float = 0.05):
        self.window_size = window_size
        self.f_min = max(1, round(min_fraction * scout_population))
        self._edges: Dict[Edge, EdgeVerification] = {}

    def _get(self, edge: Edge) -> EdgeVerification:
        if edge not in self._edges:
            self._edges[edge] = EdgeVerification(self.window_size)
        return self._edges[edge]

    def record_scout_pass(self, edge: Edge, was_clean: bool) -> None:
        self._get(edge).record_pass(was_clean)

    def frequency(self, edge: Edge) -> int:
        return self._get(edge).frequency

    def is_verified(self, edge: Edge) -> bool:
        return self.frequency(edge) >= self.f_min

    def route_frequency(self, route: List[str]) -> int:
        """
        Route-level verification uses the MINIMUM edge frequency along
        the route, not sum/average. Conservative on purpose.
        """
        edges = list(zip(route, route[1:]))
        if not edges:
            return 0
        return min(self.frequency(e) for e in edges)

    def is_route_verified(self, route: List[str]) -> bool:
        return self.route_frequency(route) >= self.f_min