"""
30-trial batch for Dijkstra and A* (same seeds as ACO batches).
"""

import time
import pandas as pd
from baselines import run_baseline

GRAPH_FILE = "baseco_osm_graph_scored.json"
NUM_TRIALS = 30
SEEDS = list(range(1000, 1000 + NUM_TRIALS))


def run_batch(algorithm, out_csv, summary_csv):
    print("=" * 60)
    print(f"{algorithm.upper()} – 30-Trial Batch Runner")
    print("=" * 60)

    rows = []
    for i, seed in enumerate(SEEDS, start=1):
        print(f"  Trial {i:02d}/30 (seed={seed}) ...", end=" ", flush=True)
        t0 = time.time()
        result = run_baseline(
            algorithm=algorithm,
            graph_file=GRAPH_FILE,
            num_random_hazards=5,
            random_hazard_seed=seed,
        )
        elapsed = time.time() - t0
        print(f"done in {elapsed:.2f}s | success={result['success']} "
              f"ETA={result.get('eta_seconds')}")

        rows.append({
            "trial": i,
            "seed": seed,
            "success": result["success"],
            "eta_seconds": result.get("eta_seconds"),
            "best_length_m": result.get("best_length_m"),
            "num_verified_routes": result.get("num_verified_routes"),
            "carrier_success_rate": result.get("carrier_success_rate"),
            "wall_clock_s": round(elapsed, 3),
        })

    df = pd.DataFrame(rows)
    df.to_csv(out_csv, index=False)

    ok = df[df["success"] == True]
    summary = pd.DataFrame({
        "metric": ["eta_seconds", "best_length_m", "num_verified_routes", "carrier_success_rate"],
        "mean": [
            ok["eta_seconds"].mean(),
            ok["best_length_m"].mean(),
            ok["num_verified_routes"].mean(),
            ok["carrier_success_rate"].mean(),
        ],
        "std": [
            ok["eta_seconds"].std(),
            ok["best_length_m"].std(),
            ok["num_verified_routes"].std(),
            ok["carrier_success_rate"].std(),
        ],
        "min": [
            ok["eta_seconds"].min(),
            ok["best_length_m"].min(),
            ok["num_verified_routes"].min(),
            ok["carrier_success_rate"].min(),
        ],
        "max": [
            ok["eta_seconds"].max(),
            ok["best_length_m"].max(),
            ok["num_verified_routes"].max(),
            ok["carrier_success_rate"].max(),
        ],
        "n_success": [len(ok)] * 4,
    })
    summary.to_csv(summary_csv, index=False)

    print("\n" + summary.to_string(index=False, float_format="%.2f"))
    print(f"\nSuccess rate: {len(ok)}/{NUM_TRIALS}")
    print("Done!\n")


if __name__ == "__main__":
    run_batch("dijkstra",
              "batch_results_dijkstra_30trials.csv",
              "batch_summary_dijkstra.csv")
    run_batch("astar",
              "batch_results_astar_30trials.csv",
              "batch_summary_astar.csv")