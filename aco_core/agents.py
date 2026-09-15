"""
Scout and Carrier agent behavior, including the Carrier fallback
sequence for when live conditions have escalated since verification.
"""

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

from .hazard import HazardTier, HazardReading
from .verification import VerificationTracker

Edge = Tuple[str, str]


@dataclass
class Scout:
    scout_id: str
    current_node: str
    target_node: str
    visited_path: List[str] = field(default_factory=list)

    def traverse_edge(
        self,
        next_node: str,
        hazard_reading: HazardReading,
        tracker: VerificationTracker,
    ) -> bool:
        """
        Move onto (current_node, next_node), report the hazard reading,
        and update the verification tracker. Returns whether the edge
        was clean (passable, below the impassable tier).
        """
        edge = (self.current_node, next_node)
        was_clean = hazard_reading.is_passable
        tracker.record_scout_pass(edge, was_clean)

        self.visited_path.append(self.current_node)
        self.current_node = next_node
        return was_clean


@dataclass
class Carrier:
    carrier_id: str
    current_node: str
    committed_route: List[str]
    route_rank_list: List[List[str]]
    hazard_lookup: Callable[[Edge], HazardReading]
    hazard_threshold: HazardTier = HazardTier.MODERATE
    emergency_decay: float = 0.1
    # Shared across carriers so that once a route is found impassable,
    # later carriers skip it entirely instead of still being assigned to it.
    impassable_routes: Optional[Set[Tuple[str, ...]]] = None

    _route_index: int = field(default=0, init=False)
    _committed_key: Optional[Tuple[str, ...]] = field(default=None, init=False)

    def __post_init__(self):
        self._committed_key = tuple(self.committed_route)
        if self.impassable_routes is None:
            self.impassable_routes = set()

    def _recheck_edge(self, edge: Edge) -> HazardReading:
        return self.hazard_lookup(edge)

    def next_step(
        self, tracker: VerificationTracker, pheromone: Dict[Edge, float]
    ) -> Optional[str]:
        if self._route_index >= len(self.committed_route) - 1:
            return None

        next_node = self.committed_route[self._route_index + 1]
        edge = (self.current_node, next_node)
        reading = self._recheck_edge(edge)

        if reading.tier >= self.hazard_threshold:
            return self._handle_blocked_edge(edge, pheromone, tracker)

        self.current_node = next_node
        self._route_index += 1
        return self.current_node

    def _handle_blocked_edge(
        self, edge: Edge, pheromone: Dict[Edge, float], tracker: VerificationTracker
    ) -> Optional[str]:
        # 1. Immediate penalty on the blocked edge
        if edge in pheromone:
            pheromone[edge] *= self.emergency_decay

        # Mark the currently committed route as impassable so subsequent
        # carriers are not assigned to it
        if self._committed_key is not None:
            self.impassable_routes.add(self._committed_key)

        # 2. Fall back to the next-best ALREADY-VERIFIED route that is
        #    not already known to be impassable
        for candidate in self.route_rank_list:
            cand_key = tuple(candidate)
            if cand_key in self.impassable_routes:
                continue
            if self.current_node not in candidate:
                continue
            start = candidate.index(self.current_node)
            remaining = candidate[start:]
            if tracker.is_route_verified(remaining):
                self.committed_route = candidate
                self._committed_key = cand_key
                self._route_index = start
                return self.current_node

        # 3. No verified alternative
        return None