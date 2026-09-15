"""
Batch runner for the Enhanced Multi-Tier Heterogeneous Scout-Ant ACO (AEGIS).
Runs 30 independent trials and saves detailed results + summary statistics.
"""

import json
import time
from pathlib import Path
import pandas as pd
import numpy as np

from simulation_backend import run_full_simulation

# ============================================================
# CONFIGURATION – change these if you want different settings
# ============================================================
GRAPH_FILE = "baseco_osm_graph_scored.json"   # or "aco_core/baseco_osm_graph_scored.json" if needed
NUM_TRIALS = 30

# Enhanced model parameters (typical good values from your dashboard)
NUM_SCOUTS = 100
NUM_CARRIERS = 3
W1 = 0.40          # distance weight
W2 = 0.40          # structural risk weight
W3 = 0.20          # complexity / turn weight
RHO_MIN = 0.10
RHO_MAX = 0.50
ALPHA = 1.0
BETA = 1.0
DELTA_TAU_PLUS = 1.0
DELTA_TAU_MINUS = 1.0
CONFIDENCE_FRACTION = 0.05

ENABLE_FIRE = True
SPREAD_RATE_MPS = 1.0 / 60          # 1.0 m/min → m/s (matches dashboard default)
NUM_RANDOM_HAZARDS = 5             # set to 0 if you want fire-only
SCOUTING_PHASE_DURATION_S = 600

# Output files
OUTPUT_CSV = "batch_results_enhanced_30trials.csv"
SUMMARY_CSV = "batch_summary_enhanced.csv"
# ============================================================


def run_one_trial(trial_id: int, seed: int):
    """Run a single enhanced simulation and extract the metrics we need."""
    print(f"  Trial {trial_id:02d}/30  (seed={seed}) ...", end=" ", flush=True)
    start_time = time.time()

    result = run_full_simulation(
        graph_file=GRAPH_FILE,
        w1=W1, w2=W2, w3=W3,
        rho_min=RHO_MIN, rho_max=RHO_MAX,
        num_scouts=NUM_SCOUTS,
        num_carriers=NUM_CARRIERS,
        alpha=ALPHA, beta=BETA,
        delta_tau_plus=DELTA_TAU_PLUS,
        delta_tau_minus=DELTA_TAU_MINUS,
        confidence_fraction=CONFIDENCE_FRACTION,
        enable_fire=ENABLE_FIRE,
        spread_rate_mps=SPREAD_RATE_MPS,
        num_random_hazards=NUM_RANDOM_HAZARDS,
        random_hazard_seed=seed,
        scouting_phase_duration_s=SCOUTING_PHASE_DURATION_S,
        # You can leave the rest at defaults
    )

    elapsed = time.time() - start_time
    print(f"done in {elapsed:.1f}s  |  success={result['success']}  ETA={result.get('eta_seconds')}")

    # Flatten the important metrics
    row = {
        "trial": trial_id,
        "seed": seed,
        "success": result["success"],
        "eta_seconds": result.get("eta_seconds"),
        "best_length_m": result.get("best_length_m"),
        "num_verified_routes": len(result.get("top_routes", [])),
        "scouts_reached_target": result.get("scouts_reached_target"),
        "scouts_run": result.get("scouts_run"),
        "scouts_no_path": result.get("scouts_no_path"),
        "scouts_step_budget": result.get("scouts_step_budget"),
        "carrier_successes": result.get("carrier_successes"),
        "num_carriers": result.get("num_carriers"),
        "carrier_success_rate": (result.get("carrier_successes", 0) / result.get("num_carriers", 1)) * 100,
        "avg_risk_pct": result.get("avg_risk_pct"),
        "avg_complexity_pct": result.get("avg_complexity_pct"),
        "avg_distance_pct": result.get("avg_distance_pct"),
        "edges_blocked_final": result.get("edges_blocked_final"),
        "num_random_hazards": result.get("num_random_hazards"),
        "final_fire_radius_m": result.get("final_fire_radius_m"),
        "early_termination": result.get("early_termination"),
        "wall_clock_s": round(elapsed, 2),
    }
    return row


def main():
    print("=" * 60)
    print("AEGIS Enhanced Model – 30-Trial Batch Runner")
    print("=" * 60)
    print(f"Graph          : {GRAPH_FILE}")
    print(f"Scouts         : {NUM_SCOUTS}")
    print(f"Carriers       : {NUM_CARRIERS}")
    print(f"Weights (D/R/C): {W1} / {W2} / {W3}")
    print(f"ρ range        : {RHO_MIN} – {RHO_MAX}")
    print(f"Random hazards : {NUM_RANDOM_HAZARDS}")
    print(f"Fire enabled   : {ENABLE_FIRE}")
    print("=" * 60)

    # Use a fixed set of seeds so the experiment is reproducible
    seeds = list(range(1000, 1000 + NUM_TRIALS))   # 1000 … 1029

    rows = []
    for i, seed in enumerate(seeds, start=1):
        row = run_one_trial(i, seed)
        rows.append(row)

    # Save detailed results
    df = pd.DataFrame(rows)
    df.to_csv(OUTPUT_CSV, index=False)
    print(f"\nDetailed results saved → {OUTPUT_CSV}")

    # Compute summary statistics (only successful trials)
    success_df = df[df["success"] == True].copy()

    summary = {
        "metric": [],
        "mean": [],
        "std": [],
        "min": [],
        "max": [],
        "n_success": [],
    }

    metrics_to_summarize = [
        "eta_seconds",
        "best_length_m",
        "num_verified_routes",
        "scouts_reached_target",
        "carrier_successes",
        "carrier_success_rate",
        "avg_risk_pct",
        "avg_complexity_pct",
        "edges_blocked_final",
        "final_fire_radius_m",
        "wall_clock_s",
    ]

    for m in metrics_to_summarize:
        if m in success_df.columns:
            summary["metric"].append(m)
            summary["mean"].append(success_df[m].mean())
            summary["std"].append(success_df[m].std())
            summary["min"].append(success_df[m].min())
            summary["max"].append(success_df[m].max())
            summary["n_success"].append(len(success_df))

    summary_df = pd.DataFrame(summary)
    summary_df.to_csv(SUMMARY_CSV, index=False)
    print(f"Summary statistics saved → {SUMMARY_CSV}")

    print("\n" + "=" * 60)
    print("SUMMARY (successful trials only)")
    print("=" * 60)
    print(summary_df.to_string(index=False, float_format="%.2f"))
    print("=" * 60)
    print(f"\nSuccess rate: {len(success_df)}/{NUM_TRIALS} ({100*len(success_df)/NUM_TRIALS:.1f}%)")
    print("Done! You can now fill Table 4.1 (Enhanced column) with these numbers.")


if __name__ == "__main__":
    main()