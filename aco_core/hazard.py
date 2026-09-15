"""
Hazard tier definitions and binary-hazard adaptive evaporation / pheromone
update logic.

Discrete hazard tiers (what a Scout's onboard detection actually outputs):
    0 -> Safe
    1 -> Low risk        (passable -- e.g. smoke, minor obstruction)
    2 -> Moderate risk    (active fire nearby, degraded structure)
    3 -> Impassable       (blocked / structural collapse / active flame)

NOTE: the pheromone update itself uses a BINARY hazard flag H (1 if a
Scout encountered any hazard on the edge, 0 if not), per the thesis
algorithm's If/Else branch. The 4-tier `normalized` value is kept around
for analytics/reporting elsewhere, but it is no longer what drives the
adaptive evaporation / reward / penalty formulas below.
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
        """H'_ij(t) = H_ij(t) / max_tier, scaled to [0, 1].

        Continuous 4-tier value, retained for analytics/reporting only.
        The pheromone update uses HazardReading.h_binary instead.
        """
        return self.value / HazardTier.IMPASSABLE.value


@dataclass
class HazardReading:
    """A single Scout's hazard read on an edge at a point in time."""
    tier: HazardTier
    hazard_type: str = ""

    @property
    def h_normalized(self) -> float:
        """Continuous [0, 1] hazard value -- analytics use only."""
        return self.tier.normalized

    @property
    def h_binary(self) -> float:
        """
        H_ij(t): the binary hazard flag used by the adaptive pheromone
        update. Returns 1.0 if the Scout encountered ANY hazard on this
        edge (tier != SAFE), else 0.0.
        """
        return 1.0 if self.tier != HazardTier.SAFE else 0.0

    @property
    def is_passable(self) -> bool:
        return self.tier != HazardTier.IMPASSABLE


def adaptive_evaporation(rho_min: float, rho_max: float, h: float) -> float:
    """
    Pij(t) = rho_min + (rho_max - rho_min) * H

    `h` is expected to be the BINARY hazard flag (0.0 or 1.0). With a
    binary H this collapses to exactly rho_max when a hazard was
    encountered, and exactly rho_min when it wasn't -- matching the two
    branches of the algorithm directly.
    """
    return rho_min + (rho_max - rho_min) * h


def unified_pheromone_update(
    tau_current: float,
    rho_ij: float,
    h_encountered: float,
    delta_tau_plus: float,
    delta_tau_minus: float,
) -> float:
    """
    Binary-hazard adaptive pheromone update -- the If/Else branch from the
    algorithm, written as one function:

    If a hazard was encountered on this edge (H = 1):
        Pij = rho_min + (rho_max - rho_min) * 1   (== rho_max)
        Tij(t+1) = (1 - Pij) * Tij(t) - delta_tau_minus

    Else (H = 0):
        Pij = rho_min + (rho_max - rho_min) * 0   (== rho_min)
        Tij(t+1) = (1 - Pij) * Tij(t) + delta_tau_plus

    Callers should compute rho_ij via adaptive_evaporation() using the
    SAME h_encountered value first, then pass both in here. Kept as two
    separate calls so the evaporation rate stays independently
    inspectable/loggable, even though algebraically rho_ij always
    collapses to rho_max or rho_min given a binary h.

    delta_tau_plus / delta_tau_minus should be 1.0 to match the
    algorithm's literal "+1.0" / "-1.0" terms; they're left as explicit
    parameters (not hardcoded) so they stay tunable in the experiments
    section, per the thesis's own note about f_min being a tunable
    parameter elsewhere.
    """
    if h_encountered:
        new_tau = (1 - rho_ij) * tau_current - delta_tau_minus
    else:
        new_tau = (1 - rho_ij) * tau_current + delta_tau_plus
    return max(new_tau, 0.0)  # pheromone can't go negative