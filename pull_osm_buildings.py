"""
Pulls building footprints around the Baseco study area from OpenStreetMap
and saves them as a compact GeoJSON file. The dashboard's interactive map
draws them as grey blocks on a plain grey background -- no street names,
no labels, no map-tile service (so no API key either).

Run this ONCE, with internet, from your project folder:

    python pull_osm_buildings.py

Nothing to install: it talks to OpenStreetMap's public Overpass API using
only Python's built-in libraries. It writes baseco_buildings.geojson next
to your graph file; folium_map.py picks it up automatically. If the file
is missing, the map simply falls back to normal street tiles.

The public Overpass servers are shared and often overloaded (HTTP 504 /
500 / 429). So this script asks for as little as it can, retries with
waits in between, and rotates through several servers. A run can take a
minute or two when the servers are busy -- that's normal; progress is
printed as it goes.

This only affects how the map LOOKS. The routing graph is untouched.
"""

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

# Same center as pull_osm_graph.py, but a larger radius than the graph's
# 400 m so blocks fill the whole map frame instead of ending at the
# edge of the street network.
CENTER_POINT = (14.5913, 120.9600)   # (lat, lon)
RADIUS_METERS = 600
OUTPUT_FILE = "baseco_buildings.geojson"

# Plain building ways cover almost every house. Multipolygon relations
# (a few big buildings with courtyards) are slower for the server to
# resolve, so they're off by default to make a busy server more likely
# to accept the request. Set True to include them.
INCLUDE_RELATIONS = False

# Public Overpass servers, tried in order. Edit freely.
OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]
USER_AGENT = "AEGIS-thesis-buildings/1.0 (one-time building footprint download)"

# A busy Overpass server answers 504 when it can't spare the time/memory a
# request DECLARES it needs -- so declare little. Both limits are far
# below the defaults and still plenty for ~1 km^2 of building outlines.
SERVER_TIMEOUT_S = 60                 # [timeout:...] told to the server
CLIENT_TIMEOUT_S = 90                 # how long we wait for a reply
MAXSIZE_STEPS = [64 * 1024 * 1024,    # try small first ...
                 256 * 1024 * 1024]   # ... bigger only if the server says it ran out of memory

# Waits (seconds) before each full pass over the server list.
BACKOFF_S = [0, 10, 30, 60]

# 6 decimal places of lat/lon is ~0.1 m -- far finer than anything
# visible on screen. Full-precision floats would make the file about
# twice as big, and the whole file is re-sent to the browser every time
# the map redraws.
COORD_DECIMALS = 6


def build_query(center, dist, maxsize, include_relations=INCLUDE_RELATIONS):
    lat, lon = center
    parts = [f'  way["building"](around:{dist},{lat},{lon});']
    if include_relations:
        parts.append(f'  relation["building"](around:{dist},{lat},{lon});')
    return (
        f"[out:json][timeout:{SERVER_TIMEOUT_S}][maxsize:{maxsize}];\n"
        "(\n" + "\n".join(parts) + "\n);\n"
        "out geom;"
    )


def _post(url, query):
    body = urllib.parse.urlencode({"data": query}).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=CLIENT_TIMEOUT_S) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _host(url):
    return urllib.parse.urlparse(url).netloc


def fetch_overpass(center, dist, log=print, sleep=time.sleep):
    """Tries every server, several passes with growing waits between them.
    Returns the parsed JSON. `log` and `sleep` are injectable for testing."""
    last_error = {}                       # url -> most recent problem
    for pass_no, wait in enumerate(BACKOFF_S, start=1):
        if wait:
            log(f"  all servers busy -- waiting {wait}s, then trying again (pass {pass_no}/{len(BACKOFF_S)}) ...")
            sleep(wait)
        for url in OVERPASS_URLS:
            for maxsize in MAXSIZE_STEPS:
                query = build_query(center, dist, maxsize)
                try:
                    data = _post(url, query)
                except urllib.error.HTTPError as exc:
                    if exc.code in (429, 500, 502, 503, 504):
                        last_error[url] = f"HTTP {exc.code} ({exc.reason})"
                        log(f"  {_host(url)}: HTTP {exc.code} -- server busy")
                        break             # next server; a bigger maxsize wouldn't help
                    detail = exc.read().decode("utf-8", "replace")[:300]
                    raise RuntimeError(
                        f"{_host(url)} rejected the request (HTTP {exc.code}). "
                        f"This isn't a busy-server problem:\n{detail}"
                    ) from exc
                except (urllib.error.URLError, OSError, ValueError) as exc:
                    last_error[url] = f"{type(exc).__name__}: {exc}"
                    log(f"  {_host(url)}: {type(exc).__name__} -- trying next server")
                    break
                remark = (data.get("remark") or "")
                if "runtime error" in remark.lower():
                    if "memory" in remark.lower() or "maxsize" in remark.lower():
                        log(f"  {_host(url)}: ran out of memory at {maxsize // (1024 * 1024)} MiB -- retrying with more")
                        last_error[url] = remark[:200]
                        continue          # same server, larger maxsize
                    last_error[url] = remark[:200]
                    log(f"  {_host(url)}: {remark[:120]}")
                    break
                return data
    problems = "\n".join(f"  {url}: {msg}" for url, msg in last_error.items())
    raise RuntimeError(
        "Couldn't get building data from any Overpass server, even after retrying:\n"
        f"{problems}\n"
        "The public servers are overloaded right now. Wait a while (15-30 minutes is "
        "usually enough) and run this again. Nothing else is affected: the map keeps "
        "working with normal street tiles until baseco_buildings.geojson exists."
    )


def _ring(geometry, ndigits=COORD_DECIMALS):
    """Overpass geometry [{lat, lon}, ...] -> closed GeoJSON ring of
    [lon, lat] pairs, or None if it isn't a valid closed ring."""
    pts = [[round(p["lon"], ndigits), round(p["lat"], ndigits)] for p in geometry or []]
    if len(pts) < 4 or pts[0] != pts[-1]:
        return None
    return pts


def _relation_geometry(rel):
    """Simple multipolygon relations only: closed outer rings, plus inner
    rings as holes when there is exactly one outer. Anything that would
    need stitching several ways together into one ring is skipped."""
    if (rel.get("tags") or {}).get("type") != "multipolygon":
        return None
    outers, inners = [], []
    for mem in rel.get("members", []):
        if mem.get("type") != "way":
            continue
        ring = _ring(mem.get("geometry"))
        if ring is None:
            continue
        (inners if mem.get("role") == "inner" else outers).append(ring)
    if not outers:
        return None
    if len(outers) == 1:
        return {"type": "Polygon", "coordinates": [outers[0]] + inners}
    return {"type": "MultiPolygon", "coordinates": [[o] for o in outers]}


def elements_to_feature_collection(elements):
    """Overpass elements -> GeoJSON FeatureCollection of building outlines.
    Keeps only the shape: names, addresses and all other tags are dropped.
    Returns (feature_collection, number_of_buildings_kept)."""
    features = []
    for el in elements:
        geom = None
        if el.get("type") == "way":
            ring = _ring(el.get("geometry"))
            if ring is not None:
                geom = {"type": "Polygon", "coordinates": [ring]}
        elif el.get("type") == "relation":
            geom = _relation_geometry(el)
        if geom is not None:
            features.append({"type": "Feature", "properties": {}, "geometry": geom})
    return {"type": "FeatureCollection", "features": features}, len(features)


def main():
    print(f"Downloading building footprints within {RADIUS_METERS} m of {CENTER_POINT} ...")
    print("(public servers can be slow or busy -- retries are automatic)")
    data = fetch_overpass(CENTER_POINT, RADIUS_METERS)
    elements = data.get("elements", [])
    remark = data.get("remark")
    if remark:
        print(f"Overpass remark: {remark}")
    print(f"OpenStreetMap returned {len(elements)} elements.")

    fc, kept = elements_to_feature_collection(elements)
    with open(OUTPUT_FILE, "w") as f:
        json.dump(fc, f, separators=(",", ":"))

    size_kb = os.path.getsize(OUTPUT_FILE) / 1024
    print(f"Saved {kept} building outlines to {OUTPUT_FILE} ({size_kb:.0f} KB)")
    if kept < 50:
        print("NOTE: very few buildings came back -- OpenStreetMap coverage for this")
        print("      area may be thin, so the map will look sparse.")


if __name__ == "__main__":
    main()