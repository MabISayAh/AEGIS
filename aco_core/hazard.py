"""
Hazard tier definitions and adaptive evaporation logic.

Discrete hazard tiers (what a Scout's onboard detection actually outputs):
    0 -> Safe
    1 -> Low risk        (passable -- e.g. smoke, minor obstruction)
    2 -> Moderate risk    (active fire nearby, degraded structure)
    3 -> Impassable       (blocked / structural collapse / active flame)
"""

from dataclasses import dataclass
from enum import IntEnum


class HazardTier(IntEnum):
    SAFE = 0
    LOW = 1
    MODERATE = 2
    IMPASSABLE = 3

    @property
    def normalized(self) -> float:
        """H'_ij(t) = H_ij(t) / max_tier, scaled to [0, 1]."""
        return self.value / HazardTier.IMPASSABLE.value


@dataclass
class HazardReading:
    """A single Scout's hazard read on an edge at a point in time."""
    tier: HazardTier
    hazard_type: str = ""

    @property
    def h_normalized(self) -> float:
        return self.tier.normalized

    @property
    def is_passable(self) -> bool:
        return self.tier != HazardTier.IMPASSABLE


def adaptive_evaporation(rho_min: float, rho_max: float, h_normalized: float) -> float:
    """
    rho_ij(t) = rho_min + (rho_max - rho_min) * H'_ij(t)

    Computed ONCE per edge per iteration -- shared by both the reward
    and penalty cases below.
    """
    return rho_min + (rho_max - rho_min) * h_normalized


def unified_pheromone_update(
    tau_current: float,
    rho_ij: float,
    h_normalized: float,
    delta_tau_plus: float,
    delta_tau_minus: float,
) -> float:
    """
    tau_ij(t+1) = (1 - rho_ij(t)) * tau_ij(t)
                  + (1 - H'_ij(t)) * delta_tau_plus
                  - H'_ij(t) * delta_tau_minus

    Replaces the original If/Else hazard branch with one continuous
    formula. At H'=0 this is pure reward; at H'=1 (tier 3, impassable)
    it's pure penalty
    """
    reward = (1 - h_normalized) * delta_tau_plus
    penalty = h_normalized * delta_tau_minus
    new_tau = (1 - rho_ij) * tau_current + reward - penalty
    return max(new_tau, 0.0)  # pheromone can't go negative