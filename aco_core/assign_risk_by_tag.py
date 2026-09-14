"""
Fills in risk_score for every edge in baseco_osm_graph.json based on its
OSM highway_type tag -- narrower/more informal path types get a higher
baseline risk, wider/more formal ones get lower.
"""

import json

INPUT_FILE = "baseco_osm_graph.json"
OUTPUT_FILE = "../baseco_osm_graph_scored.json"

# Baseline risk score (1-10) per OSM highway tag.
RISK_BY_TAG = {
    "footway": 9,
    "path": 9,
    "steps": 9,
    "alley": 9,
    "pedestrian": 6,
    "living_street": 5,
    "unclassified": 5,
    "residential": 5,
    "service": 4,
    "track": 7,
    "primary": 4,
    "secondary": 4,
    "tertiary": 4,
    "trunk": 4,
}
DEFAULT_RISK = 5


def main():
    with open(INPUT_FILE) as f:
        data = json.load(f)

    tag_counts = {}
    for edge_key, edge in data["edges"].items():
        tag = edge.get("highway_type", "unknown")
        if isinstance(tag, list):
            tag = tag[0]

        risk = RISK_BY_TAG.get(tag, DEFAULT_RISK)
        edge["risk_score"] = risk

        tag_counts[tag] = tag_counts.get(tag, 0) + 1

    with open(OUTPUT_FILE, "w") as f:
        json.dump(data, f, indent=2)

    print(f"Scored {len(data['edges'])} edges.")
    print("\nTag breakdown (how many edges got which baseline risk):")
    for tag, count in sorted(tag_counts.items(), key=lambda x: -x[1]):
        risk = RISK_BY_TAG.get(tag, DEFAULT_RISK)
        print(f"  {tag:15s} -> risk {risk}  ({count} edges)")

    print(f"\nSaved to {OUTPUT_FILE}")
    print("You can still open this file and manually bump specific edges")
    print("up/down if you know a particular alley is riskier than its tag suggests.")


if __name__ == "__main__":
    main()
