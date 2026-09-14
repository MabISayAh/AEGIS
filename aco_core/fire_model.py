"""
Radial fire-spread model: a fire starts at one point and spreads outward
at a constant rate.
"""

import math

from .hazard import HazardTier


class FireModel:
    def __init__(
        self,
        origin_x: float,
        origin_y: float,
        spread_rate_mps: float,
        time_per_iteration_s: float = 30,
        moderate_buffer_m: float = 30,
        low_buffer_m: float = 80,
    ):
        self.origin_x = origin_x
        self.origin_y = origin_y
        self.spread_rate_mps = spread_rate_mps
        self.time_per_iteration_s = time_per_iteration_s
        self.moderate_buffer_m = moderate_buffer_m
        self.low_buffer_m = low_buffer_m

    def radius_at(self, elapsed_s: float) -> float:
        return self.spread_rate_mps * elapsed_s

    def radius_at_iteration(self, iteration: int) -> float:
        return self.radius_at(iteration * self.time_per_iteration_s)

    def hazard_tier_for_point(self, x: float, y: float, elapsed_s: float) -> HazardTier:
        dist = math.dist((x, y), (self.origin_x, self.origin_y))
        radius = self.radius_at(elapsed_s)
        if dist <= radius:
            return HazardTier.IMPASSABLE
        elif dist <= radius + self.moderate_buffer_m:
            return HazardTier.MODERATE
        elif dist <= radius + self.low_buffer_m:
            return HazardTier.LOW
        else:
            return HazardTier.SAFE
