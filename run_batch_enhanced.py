"""
AEGIS Enhanced Model – 30-Trial Batch Runner
(with dual safeguards against premature / unrepresentative lock-in)

Safeguards:
  1. warmup_scouts = 10
     → No route may verify until at least 10 Scouts have explored.
       Prevents an early, unrepresentative route from locking in.

  2. max_verified_length_ratio = 1.5
     → Even after warmup, a route that hits the confidence threshold is
       only accepted into the final 3 if its length ≤ 1.5 × baseline.
       Prevents a long but popular route from winning the race later.
"""

import time
import pandas as pd

from simulation_backend import run_full_simulation

# ============================================================
# CONFIGURATION
# ============================================================
GRAPH_FILE = "baseco_osm_graph_scored.json"
NUM_TRIALS = 30

NUM_SCOUTS = 100
NUM_CARRIERS = 3                 # or 9 if you want 3 carriers per path
W1, W2, W3 = 0.40, 0.40, 0.20   # Distance / Risk / Complexity
RHO_MIN, RHO_MAX = 0.10, 0.50
ALPHA, BETA = 2.0, 1.0
CONFIDENCE_FRACTION = 0.02       # Tc = 2 at 100 scouts

# --- Dual safeguards ---
WARMUP_SCOUTS = 10
MAX_VERIFIED_LENGTH_RATIO = 1.5  # tighter than the backend default of 2.0

ENABLE_FIRE = True
SPREAD_RATE_MPS = 1.0 / 60       # 1.0 m/min
NUM_RANDOM_HAZARDS = 5
SCOUTING_PHASE_DURATION_S = 600

OUTPUT_CSV = "batch_results_enhanced_v2_30trials.csv"
SUMMARY_CSV = "batch_summary_enhanced_v2.csv"
# ============================================================


def run_one_trial(trial_id: int, seed: int):
    print(f"  Trial {trial_id:02d}/30  (seed={seed}) ...", end=" ", flush=True)
    t0 = time.time()

    result = run_full_simulation(
        graph_file=GRAPH_FILE,
        w1=W1, w2=W2, w3=W3,
        rho_min=RHO_MIN, rho_max=RHO_MAX,
        num_scouts=NUM_SCOUTS,
        num_carriers=NUM_CARRIERS,
        alpha=ALPHA, beta=BETA,
        confidence_fraction=CONFIDENCE_FRACTION,
        warmup_scouts=WARMUP_SCOUTS,
        max_verified_length_ratio=MAX_VERIFIED_LENGTH_RATIO,
        enable_fire=ENABLE_FIRE,
        spread_rate_mps=SPREAD_RATE_MPS,
        num_random_hazards=NUM_RANDOM_HAZARDS,
        random_hazard_seed=seed,
        scouting_phase_duration_s=SCOUTING_PHASE_DURATION_S,
    )

    elapsed = time.time() - t0
    print(f"done in {elapsed:.1f}s  |  success={result['success']}  "
          f"ETA={result.get('eta_seconds')}  "
          f"true_verified={result.get('num_true_verified_routes')}  "
          f"rejected_len={result.get('routes_rejected_for_length')}")

    return {
        "trial": trial_id,
        "seed": seed,
        "success": result["success"],
        "eta_seconds": result.get("eta_seconds"),
        "best_length_m": result.get("best_length_m"),
        "num_verified_routes": len(result.get("top_routes", [])),
        "num_true_verified_routes": result.get("num_true_verified_routes"),
        "routes_rejected_for_length": result.get("routes_rejected_for_length"),
        "scouts_reached_target": result.get("scouts_reached_target"),
        "scouts_run": result.get("scouts_run"),
        "carrier_successes": result.get("carrier_successes"),
        "num_carriers": result.get("num_carriers"),
        "carrier_success_rate": (
            result.get("carrier_successes", 0) / max(result.get("num_carriers", 1), 1)
        ) * 100,
        "avg_risk_pct": result.get("avg_risk_pct"),
        "avg_complexity_pct": result.get("avg_complexity_pct"),
        "edges_blocked_final": result.get("edges_blocked_final"),
        "final_fire_radius_m": result.get("final_fire_radius_m"),
        "early_termination": result.get("early_termination"),
        "wall_clock_s": round(elapsed, 2),
    }


def main():
    print("=" * 60)
    print("AEGIS Enhanced Model – 30-Trial Batch (v2 safeguards)")
    print("=" * 60)
    print(f"Graph               : {GRAPH_FILE}")
    print(f"Scouts / Carriers   : {NUM_SCOUTS} / {NUM_CARRIERS}")
    print(f"Weights (D/R/C)     : {W1} / {W2} / {W3}")
    print(f"ρ range             : {RHO_MIN} – {RHO_MAX}")
    print(f"Alpha / Beta        : {ALPHA} / {BETA}")
    print(f"Confidence fraction : {CONFIDENCE_FRACTION}")
    print(f"Warmup scouts       : {WARMUP_SCOUTS}")
    print(f"Max verified ratio  : {MAX_VERIFIED_LENGTH_RATIO}")
    print(f"Random hazards      : {NUM_RANDOM_HAZARDS}")
    print(f"Fire enabled        : {ENABLE_FIRE}")
    print("=" * 60)

    seeds = list(range(1000, 1000 + NUM_TRIALS))
    rows = [run_one_trial(i, seed) for i, seed in enumerate(seeds, start=1)]

    df = pd.DataFrame(rows)
    df.to_csv(OUTPUT_CSV, index=False)
    print(f"\nDetailed results → {OUTPUT_CSV}")

    ok = df[df["success"] == True]
    metrics = [
        "eta_seconds", "best_length_m",
        "num_verified_routes", "num_true_verified_routes",
        "routes_rejected_for_length",
        "scouts_reached_target", "carrier_successes", "carrier_success_rate",
        "avg_risk_pct", "avg_complexity_pct",
        "edges_blocked_final", "final_fire_radius_m", "wall_clock_s",
    ]

    summary = {
        "metric": [], "mean": [], "std": [], "min": [], "max": [], "n_success": []
    }
    for m in metrics:
        if m in ok.columns:
            summary["metric"].append(m)
            summary["mean"].append(ok[m].mean())
            summary["std"].append(ok[m].std())
            summary["min"].append(ok[m].min())
            summary["max"].append(ok[m].max())
            summary["n_success"].append(len(ok))

    summary_df = pd.DataFrame(summary)
    summary_df.to_csv(SUMMARY_CSV, index=False)
    print(f"Summary statistics → {SUMMARY_CSV}")

    print("\n" + "=" * 60)
    print("SUMMARY (successful trials only)")
    print("=" * 60)
    print(summary_df.to_string(index=False, float_format="%.2f"))
    print("=" * 60)
    print(f"\nSuccess rate: {len(ok)}/{NUM_TRIALS} ({100 * len(ok) / NUM_TRIALS:.1f}%)")
    print("Done! Use these numbers for the Enhanced column in Table 4.1.")


if __name__ == "__main__":
    main()