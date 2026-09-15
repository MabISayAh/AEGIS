"""
30-trial batch for the TRUE Classical ACO
"""

import time
import pandas as pd
from classical_aco import classical_aco

GRAPH_FILE = "baseco_osm_graph_scored.json"
NUM_TRIALS = 30

OUTPUT_CSV = "batch_results_true_classical_30trials.csv"
SUMMARY_CSV = "batch_summary_true_classical.csv"


def main():
    print("=" * 60)
    print("TRUE Classical ACO – 30-Trial Batch Runner")
    print("=" * 60)

    seeds = list(range(1000, 1000 + NUM_TRIALS))
    rows = []

    for i, seed in enumerate(seeds, start=1):
        print(f"  Trial {i:02d}/30 (seed={seed}) ...", end=" ", flush=True)
        start = time.time()

        result = classical_aco(
            graph_file=GRAPH_FILE,
            num_ants=50,
            max_iterations=40,
            alpha=1.0,
            beta=2.0,
            rho=0.1,
            Q=100.0,
            num_random_hazards=5,
            random_hazard_seed=seed,
        )

        elapsed = time.time() - start
        print(f"done in {elapsed:.1f}s | success={result['success']} ETA={result.get('eta_seconds')}")

        rows.append({
            "trial": i,
            "seed": seed,
            "success": result["success"],
            "eta_seconds": result.get("eta_seconds"),
            "best_length_m": result.get("best_length_m"),
            "num_verified_routes": result.get("num_verified_routes"),
            "carrier_success_rate": result.get("carrier_success_rate"),
            "wall_clock_s": round(elapsed, 2),
        })

    df = pd.DataFrame(rows)
    df.to_csv(OUTPUT_CSV, index=False)

    success_df = df[df["success"] == True]
    summary = {
        "metric": ["eta_seconds", "best_length_m", "num_verified_routes", "carrier_success_rate"],
        "mean": [
            success_df["eta_seconds"].mean(),
            success_df["best_length_m"].mean(),
            success_df["num_verified_routes"].mean(),
            success_df["carrier_success_rate"].mean(),
        ],
        "std": [
            success_df["eta_seconds"].std(),
            success_df["best_length_m"].std(),
            success_df["num_verified_routes"].std(),
            success_df["carrier_success_rate"].std(),
        ],
        "min": [
            success_df["eta_seconds"].min(),
            success_df["best_length_m"].min(),
            success_df["num_verified_routes"].min(),
            success_df["carrier_success_rate"].min(),
        ],
        "max": [
            success_df["eta_seconds"].max(),
            success_df["best_length_m"].max(),
            success_df["num_verified_routes"].max(),
            success_df["carrier_success_rate"].max(),
        ],
        "n_success": [len(success_df)] * 4,
    }

    summary_df = pd.DataFrame(summary)
    summary_df.to_csv(SUMMARY_CSV, index=False)

    print("\n" + "=" * 60)
    print(summary_df.to_string(index=False, float_format="%.2f"))
    print("=" * 60)
    print(f"Success rate: {len(success_df)}/{NUM_TRIALS}")
    print("Done!")


if __name__ == "__main__":
    main()