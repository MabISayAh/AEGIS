"""
Replay of a finished simulation run on the interactive (Folium / Leaflet)
map: the Scout swarm exploring, routes getting verified, then the fire
trucks driving to the fire -- smooth, in the browser, on the same
pan/zoom/drag map as the static views.

How it works
------------
1. run_full_simulation() is run ONCE, silently: instead of redrawing a
   chart on every callback (slow, flickery), ReplayRecorder just records
   what each Scout and Carrier did.
2. build_replay_payload() turns that record into plain data: lat/lon
   paths, travel times per edge (the same risk-aware edge_travel_time_s
   the ETA metric uses), the fire's growth, which carrier arrives first.
3. build_replay_html() builds the Folium base map and injects a small
   JavaScript player. The browser animates everything with
   requestAnimationFrame, so movement is smooth and the map stays fully
   pannable / zoomable while it plays.

Nothing here changes the simulation or the routing -- it only reads what
the simulation reports.
"""

import base64
import json
import os

import folium_map as fmap

# ------------------------------------------------------------------ tunables
SCOUT_MS = 90                  # playback ms per Scout at 1x speed
CARRIER_SIM_PER_SEC = 6.0      # simulated seconds that pass per real second at 1x
HOLD_MS = 700                  # pause between scouting and dispatch, and at the end
DEPART_STAGGER_S = 1.5         # sim-seconds between trucks leaving on the same route
DEFAULT_SPEED = 1.0
SCOUT_COLOR = "#FFA94D"
FIRE_COLOR = fmap.FIRE_COLOR

# Fire truck icon. Until you provide a PNG, a drawn top-down truck is used.
# Put your image next to dashboard.py as firetruck.png and set the two
# values below to match how the picture is drawn:
TRUCK_IMAGE_FILE = "firetruck.png"
TRUCK_IMAGE_MODE = "rotate"    # "rotate": top-down picture, turned to face its direction of travel
                               # "flip"  : side-view picture, mirrored when heading west (no rotation)
TRUCK_IMAGE_FACES = "up"       # which way the picture's FRONT points: "up" | "right" | "down" | "left"
TRUCK_SIZE_PX = 34


# ------------------------------------------------------------ recording a run
class ReplayRecorder:
    """Pass on_scout / on_carrier as run_full_simulation's callbacks. They
    only record -- nothing is drawn while the simulation runs."""

    def __init__(self):
        self.scouts = []        # one dict per Scout, in order
        self.verified = []      # routes in the order they got verified: {"scout": idx0, "route": [...]}
        self.carriers = {}      # carrier_id -> record
        self.carrier_order = []
        self.num_scouts_planned = 0

    def on_scout(self, scout_number, num_scouts, scout_route, scout_status=None,
                 verified_routes=(), elapsed_s=0.0, **_ignored):
        self.num_scouts_planned = num_scouts
        while len(self.verified) < len(verified_routes):
            self.verified.append({
                "scout": scout_number - 1,
                "route": list(verified_routes[len(self.verified)]),
            })
        self.scouts.append({
            "route": list(scout_route) if scout_route else None,
            "status": scout_status or ("reached" if scout_route else "no_path"),
            "verified": len(self.verified),
            "elapsed_s": float(elapsed_s or 0.0),
        })

    def on_carrier(self, carrier_id, carrier_number, num_carriers, rank, route,
                   current_node, status, elapsed_s=0.0, **_ignored):
        rec = self.carriers.get(carrier_id)
        if rec is None:
            rec = {
                "id": carrier_id, "number": carrier_number, "rank": rank,
                "path": [current_node], "last_route": list(route) if route else None,
                "switches": [], "status": status, "fire_clock0": float(elapsed_s or 0.0),
            }
            self.carriers[carrier_id] = rec
            self.carrier_order.append(carrier_id)
        if current_node != rec["path"][-1]:
            rec["path"].append(current_node)
        if route and rec["last_route"] and list(route) != rec["last_route"]:
            rec["switches"].append(len(rec["path"]) - 1)     # re-routed after this many moves
        if route:
            rec["last_route"] = list(route)
        if status in ("reached", "blocked"):
            rec["status"] = status
        elif rec["status"] not in ("reached", "blocked"):
            rec["status"] = status


# ------------------------------------------------------------ payload (data)
def _round_pt(ll):
    return [round(ll[0], 6), round(ll[1], 6)]


def build_replay_payload(recorder, results, edge_time_fn, fire_rate_mps=0.0):
    """Turns a recorded run into plain JSON-able data for the player.

    edge_time_fn(u, v) -> seconds to drive edge u->v (use the same
    risk-aware edge_travel_time_s the ETA metric uses).
    """
    nodes_ll = fmap.nodes_to_latlon(results["nodes"])

    route_index, route_table = {}, []

    def rid(route):
        key = tuple(route)
        if key not in route_index:
            route_index[key] = len(route_table)
            route_table.append([_round_pt(nodes_ll[n]) for n in route if n in nodes_ll])
        return route_index[key]

    scouts = []
    for s in recorder.scouts:
        scouts.append({
            "r": rid(s["route"]) if s["route"] else -1,
            "s": s["status"],
            "v": s["verified"],
            "f": round(fire_rate_mps * s["elapsed_s"], 2),
        })

    verified = [{"at": v["scout"], "r": rid(v["route"])} for v in recorder.verified]
    top_routes = [{"r": rid(t["route"]), "len": round(float(t.get("length_m", 0)), 1)}
                  for t in (results.get("top_routes") or [])[:3]]

    carriers, group_count = [], {}
    for cid in recorder.carrier_order:
        rec = recorder.carriers[cid]
        path = [n for n in rec["path"] if n in nodes_ll]
        times = [0.0]
        for u, v in zip(path, path[1:]):
            dt = edge_time_fn(u, v)
            times.append(times[-1] + (dt if dt is not None else 0.0))
        k = group_count.get(rec["rank"], 0)
        group_count[rec["rank"]] = k + 1
        style = fmap.ROUTE_STYLES[(rec["rank"] - 1) % len(fmap.ROUTE_STYLES)]
        carriers.append({
            "id": cid, "n": rec["number"], "rank": rec["rank"], "color": style[0],
            "pts": [_round_pt(nodes_ll[n]) for n in path],
            "t": [round(x, 3) for x in times],
            "delay": round(k * DEPART_STAGGER_S, 3),
            "status": rec["status"],
            "sw": rec["switches"],
        })

    arrivals = [(c["delay"] + c["t"][-1], c["id"]) for c in carriers if c["status"] == "reached"]
    first = min(arrivals) if arrivals else None

    first_rec = recorder.carriers[recorder.carrier_order[0]] if recorder.carrier_order else None
    last_scout_clock = recorder.scouts[-1]["elapsed_s"] if recorder.scouts else 0.0
    fire_xy = None
    if results.get("enable_fire") and "fire_origin_x" in results:
        fire_xy = fmap.utm_to_latlon(results["fire_origin_x"], results["fire_origin_y"])

    start_node, target_node = results.get("start_node"), results.get("target_node")
    return {
        "routes": route_table,
        "scouts": scouts,
        "numScouts": recorder.num_scouts_planned or len(scouts),
        "verified": verified,
        "topRoutes": top_routes,
        "carriers": carriers,
        "firstArrival": {"id": first[1], "t": round(first[0], 3)} if first else None,
        "fire": {
            "origin": _round_pt(fire_xy) if fire_xy else None,
            "rate": fire_rate_mps,
            "clock0": first_rec["fire_clock0"] if first_rec else last_scout_clock,
        },
        "start": _round_pt(nodes_ll[start_node]) if start_node in nodes_ll else None,
        "target": _round_pt(nodes_ll[target_node]) if target_node in nodes_ll else None,
    }


# ------------------------------------------------------------ the JS player
# Browser-side code. Everything above the "Leaflet adapter" line is pure
# (no DOM / Leaflet) and is unit-tested with node.
REPLAY_JS = r"""
(function (root) {
  "use strict";

  /* ======================= pure helpers (unit-tested) ======================= */

  // same shape as dashboard.format_timer: mm:ss.d
  function fmtClock(sec) {
    if (!(sec > 0)) sec = 0;
    var minutes = Math.floor(sec / 60);
    var s = (sec % 60).toFixed(1);
    if (s.length < 4) s = "0" + s;
    return (minutes < 10 ? "0" : "") + minutes + ":" + s;
  }

  // compass bearing a -> b in degrees, clockwise from north; null if same point
  function bearingDeg(a, b) {
    var rad = Math.PI / 180;
    var dLat = b[0] - a[0];
    var dLon = (b[1] - a[1]) * Math.cos(((a[0] + b[0]) / 2) * rad);
    if (dLat === 0 && dLon === 0) return null;
    return (Math.atan2(dLon, dLat) / rad + 360) % 360;
  }

  function segmentHeading(pts, i) {
    var k, j, h;
    for (k = i; k < pts.length - 1; k++) { h = bearingDeg(pts[k], pts[k + 1]); if (h !== null) return h; }
    for (j = Math.min(i, pts.length - 2); j >= 0; j--) { h = bearingDeg(pts[j], pts[j + 1]); if (h !== null) return h; }
    return 0;
  }

  // where carrier c is at simulated time t (seconds since dispatch)
  function carrierState(c, t) {
    var pts = c.pts, ts = c.t, n = pts.length;
    var local = t - c.delay;
    if (n < 2) {
      return {lat: pts[0][0], lon: pts[0][1], heading: 0, departed: local > 0, done: local >= 0, idx: 0};
    }
    var end = ts[n - 1];
    if (local <= 0) {
      return {lat: pts[0][0], lon: pts[0][1], heading: segmentHeading(pts, 0), departed: false, done: false, idx: 0};
    }
    if (local >= end) {
      return {lat: pts[n - 1][0], lon: pts[n - 1][1], heading: segmentHeading(pts, n - 2), departed: true, done: true, idx: n - 1};
    }
    var lo = 0, hi = n - 1;
    while (hi - lo > 1) {
      var mid = (lo + hi) >> 1;
      if (ts[mid] <= local) lo = mid; else hi = mid;
    }
    var f = (local - ts[lo]) / (ts[hi] - ts[lo]);
    return {
      lat: pts[lo][0] + (pts[hi][0] - pts[lo][0]) * f,
      lon: pts[lo][1] + (pts[hi][1] - pts[lo][1]) * f,
      heading: segmentHeading(pts, lo), departed: true, done: false, idx: lo
    };
  }

  // the part of the path already driven, ending at the truck's current position
  function trailPoints(c, st) {
    if (!st.departed) return [];
    var out = c.pts.slice(0, st.idx + 1);
    if (!st.done) out.push([st.lat, st.lon]);
    return out;
  }

  function arrivedCount(data, tSim) {
    var k = 0;
    data.carriers.forEach(function (c) {
      if (c.status === "reached" && tSim >= c.delay + c.t[c.t.length - 1]) k++;
    });
    return k;
  }

  // virtual timeline: scouting, a pause, driving, a pause (all in "virtual ms" at 1x)
  function buildTimeline(data, cfg) {
    var scoutVT = data.scouts.length * cfg.scoutMs;
    var maxEnd = 0;
    data.carriers.forEach(function (c) {
      var e = c.delay + c.t[c.t.length - 1];
      if (e > maxEnd) maxEnd = e;
    });
    var carrierVT = data.carriers.length ? (maxEnd / cfg.carrierSimPerSec) * 1000 : 0;
    return {
      scoutVT: scoutVT, holdVT: cfg.holdMs, carrierVT: carrierVT, maxEnd: maxEnd,
      total: scoutVT + cfg.holdMs + carrierVT + cfg.holdMs
    };
  }

  function fireRadius(data, f) {
    var fire = data.fire;
    if (!fire || !fire.origin) return 0;
    var last = data.scouts.length ? data.scouts[data.scouts.length - 1].f : 0;
    if (f.phase !== "carrier") {
      var s = data.scouts[f.scoutIndex];
      return s ? s.f : 0;
    }
    // never shrinks: max() with where scouting left it
    return Math.max(last, fire.rate * (fire.clock0 + f.tSim));
  }

  // everything that should be on screen at virtual time vt (pure, so scrubbing works)
  function frameAt(data, cfg, tl, vt) {
    vt = Math.max(0, Math.min(vt, tl.total));
    var nScouts = data.scouts.length;
    var f = {vt: vt, phase: "scout", scoutIndex: nScouts ? 0 : -1, scoutFrac: 0, tSim: 0,
             clockSec: 0, clockFrozen: false, arrived: 0, carrierDone: false, fireR: 0};
    if (vt < tl.scoutVT) {
      f.phase = "scout";
      f.scoutIndex = Math.min(nScouts - 1, Math.floor(vt / cfg.scoutMs));
      f.scoutFrac = (vt - f.scoutIndex * cfg.scoutMs) / cfg.scoutMs;
    } else if (vt < tl.scoutVT + tl.holdVT || !data.carriers.length) {
      f.phase = "scout_done";
      f.scoutIndex = nScouts - 1;
      f.scoutFrac = 1;
    } else {
      f.phase = "carrier";
      f.scoutIndex = nScouts - 1;
      f.scoutFrac = 1;
      f.tSim = Math.min(tl.maxEnd, ((vt - tl.scoutVT - tl.holdVT) / 1000) * cfg.carrierSimPerSec);
      f.carrierDone = f.tSim >= tl.maxEnd;
      var fa = data.firstArrival;
      f.clockSec = fa ? Math.min(f.tSim, fa.t) : f.tSim;
      f.clockFrozen = !!(fa && f.tSim >= fa.t);
      f.arrived = arrivedCount(data, f.tSim);
    }
    f.fireR = fireRadius(data, f);
    return f;
  }

  /* ============================ Leaflet adapter ============================ */

  var CSS = [
    ".aegis-hud{position:fixed;top:10px;left:50%;transform:translateX(-50%);z-index:9999;min-width:230px;",
    "background:rgba(255,255,255,.95);border-radius:10px;box-shadow:0 1px 6px rgba(0,0,0,.3);padding:6px 16px 7px;",
    "text-align:center;font:13px/1.35 sans-serif;color:#333;pointer-events:none}",
    ".aegis-hud-clock{font:700 26px/1.1 monospace;color:#555}",
    ".aegis-hud.live .aegis-hud-clock{color:#d9822b}",
    ".aegis-hud.frozen .aegis-hud-clock{color:#1f9d55}",
    ".aegis-hud-sub{font-size:11px;color:#777}",
    ".aegis-controls{position:fixed;left:50%;bottom:30px;transform:translateX(-50%);z-index:9999;display:flex;",
    "align-items:center;gap:8px;background:rgba(255,255,255,.95);border-radius:10px;padding:6px 10px;",
    "box-shadow:0 1px 6px rgba(0,0,0,.3);font:12px sans-serif}",
    ".aegis-btn{border:0;background:#477B9E;color:#fff;border-radius:6px;padding:4px 10px;cursor:pointer;font:600 12px sans-serif}",
    ".aegis-btn:hover{background:#3a688a}",
    ".aegis-slider{width:230px}",
    ".aegis-truck-wrap{background:transparent;border:0}",
    ".aegis-truck-inner{width:100%;height:100%;display:flex;align-items:center;justify-content:center;",
    "transform-origin:50% 50%;transition:transform .15s linear}",
    ".aegis-truck-inner svg,.aegis-truck-inner img{display:block}",
    ".aegis-blocked .aegis-truck-inner{filter:grayscale(1) opacity(.65)}",
    ".aegis-arrived .aegis-truck-inner{filter:drop-shadow(0 0 5px #1f9d55)}"
  ].join("");

  var TRUCK_SVG =
    '<svg viewBox="0 0 24 48" width="17" height="34" xmlns="http://www.w3.org/2000/svg">' +
    '<rect x="3" y="2" width="18" height="44" rx="4" fill="#d93025" stroke="#7a1410" stroke-width="1.5"/>' +
    '<rect x="5" y="5" width="14" height="9" rx="2" fill="#bfe3ff" stroke="#7a1410" stroke-width="1"/>' +
    '<rect x="9" y="18" width="6" height="24" fill="#f4f4f4" stroke="#999" stroke-width="1"/>' +
    '<circle cx="6.5" cy="3.5" r="1.7" fill="#ffd400"/><circle cx="17.5" cy="3.5" r="1.7" fill="#ffd400"/></svg>';

  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined) e.textContent = text;
    return e;
  }

  function mount(map, data, cfg) {
    var tl = buildTimeline(data, cfg);
    var N = data.numScouts;

    var style = document.createElement("style");
    style.textContent = CSS;
    document.head.appendChild(style);

    // ---- layers (created once, shown/hidden per frame so scrubbing works)
    var scoutLine = L.polyline([], {color: cfg.scoutColor, weight: 5, opacity: 0.95, lineCap: "round"});
    var scoutHead = L.circleMarker([0, 0], {radius: 6, color: "#ffffff", weight: 2, fillColor: cfg.scoutColor, fillOpacity: 1});
    var verifiedLayers = data.verified.map(function (v, i) {
      var st = cfg.routeStyles[i % cfg.routeStyles.length];
      return L.polyline(data.routes[v.r], {color: st.color, weight: st.weight, opacity: 0.95, dashArray: st.dash || null});
    });
    var rankLayers = data.topRoutes.map(function (t, i) {
      var st = cfg.routeStyles[i % cfg.routeStyles.length];
      return L.polyline(data.routes[t.r], {color: st.color, weight: st.weight, opacity: 0.8, dashArray: st.dash || null});
    });
    var fireCircle = (data.fire && data.fire.origin)
      ? L.circle(data.fire.origin, {radius: 1, color: cfg.fireColor, weight: 2, fillColor: cfg.fireColor, fillOpacity: 0.22})
      : null;

    var S = cfg.truckSize;
    var trucks = data.carriers.map(function (c) {
      var inner = cfg.truckImage
        ? '<img src="' + cfg.truckImage + '" style="width:' + S + 'px;height:auto;">'
        : TRUCK_SVG;
      var html = '<div class="aegis-truck-inner" style="filter:drop-shadow(0 0 3px ' + c.color + ') drop-shadow(0 0 1px #000);">' + inner + "</div>";
      var icon = L.divIcon({className: "aegis-truck-wrap", html: html, iconSize: [S, S], iconAnchor: [S / 2, S / 2]});
      var mk = L.marker(c.pts[0], {icon: icon, zIndexOffset: 1000});
      mk.bindTooltip(c.id + " \u00b7 route " + c.rank);
      var trail = L.polyline([], {color: c.color, weight: 4, opacity: 0.9});
      return {c: c, mk: mk, trail: trail};
    });

    function setShown(layer, show) {
      var has = map.hasLayer(layer);
      if (show && !has) layer.addTo(map);
      else if (!show && has) map.removeLayer(layer);
    }

    function styleTruck(t, st) {
      var node = t.mk.getElement ? t.mk.getElement() : null;
      if (!node || !node.firstChild) return;
      var inner = node.firstChild, tf;
      if (cfg.truckImage && cfg.imageMode === "flip") {
        var west = st.heading > 180 && st.heading < 360;
        tf = (cfg.imageFaces === "left" ? !west : west) ? "scaleX(-1)" : "none";
      } else {
        var face = {up: 0, right: 90, down: 180, left: 270}[cfg.truckImage ? cfg.imageFaces : "up"] || 0;
        tf = "rotate(" + (st.heading - face) + "deg)";
      }
      inner.style.transform = tf;
      node.classList.toggle("aegis-arrived", st.done && t.c.status === "reached");
      node.classList.toggle("aegis-blocked", st.done && t.c.status !== "reached");
    }

    // ---- HUD + controls
    var hud = el("div", "aegis-hud");
    var hudPhase = el("div", "aegis-hud-phase", "");
    var hudClock = el("div", "aegis-hud-clock", fmtClock(0));
    var hudSub = el("div", "aegis-hud-sub", "");
    hud.appendChild(hudPhase); hud.appendChild(hudClock); hud.appendChild(hudSub);
    document.body.appendChild(hud);

    var bar = el("div", "aegis-controls");
    var btnPlay = el("button", "aegis-btn", "Pause");
    var btnRestart = el("button", "aegis-btn", "Restart");
    var slider = el("input", "aegis-slider");
    slider.type = "range"; slider.min = 0; slider.max = 1000; slider.value = 0;
    var sel = el("select", "aegis-select");
    [0.5, 1, 2, 4, 8].forEach(function (s) {
      var o = el("option", "", s + "x"); o.value = String(s);
      if (s === cfg.speed) o.selected = true;
      sel.appendChild(o);
    });
    bar.appendChild(btnPlay); bar.appendChild(btnRestart); bar.appendChild(slider); bar.appendChild(sel);
    document.body.appendChild(bar);

    // ---- one frame
    function render(f) {
      var inScout = f.phase !== "carrier";
      var sc = data.scouts[f.scoutIndex];
      var pts = (inScout && sc && sc.r >= 0) ? data.routes[sc.r] : null;
      if (pts && pts.length) {
        var k = Math.max(2, Math.ceil(pts.length * Math.min(1, f.scoutFrac / 0.8)));
        var shown = pts.slice(0, Math.min(k, pts.length));
        scoutLine.setLatLngs(shown);
        scoutHead.setLatLng(shown[shown.length - 1]);
        setShown(scoutLine, true); setShown(scoutHead, true);
      } else {
        setShown(scoutLine, false); setShown(scoutHead, false);
      }
      data.verified.forEach(function (v, i) { setShown(verifiedLayers[i], inScout && v.at <= f.scoutIndex); });
      rankLayers.forEach(function (l) { setShown(l, !inScout); });
      if (fireCircle) {
        fireCircle.setRadius(Math.max(f.fireR, 0.01));
        setShown(fireCircle, f.fireR > 0.5);
      }
      trucks.forEach(function (t) {
        var show = !inScout;
        setShown(t.mk, show);
        if (!show) { setShown(t.trail, false); return; }
        var st = carrierState(t.c, f.tSim);
        t.mk.setLatLng([st.lat, st.lon]);
        var tp = trailPoints(t.c, st);
        if (tp.length >= 2) { t.trail.setLatLngs(tp); setShown(t.trail, true); } else { setShown(t.trail, false); }
        styleTruck(t, st);
      });
    }

    function hudText(f) {
      if (f.phase === "scout") {
        hudPhase.textContent = "Scout " + (f.scoutIndex + 1) + "/" + N + " exploring the network...";
        hudSub.textContent = "Clock starts when the fire engines leave";
      } else if (f.phase === "scout_done") {
        hudPhase.textContent = "Scouting complete";
        hudSub.textContent = "Clock starts when the fire engines leave";
      } else {
        var total = data.carriers.length;
        hudPhase.textContent = f.carrierDone
          ? (f.arrived + "/" + total + " fire engines arrived")
          : ("Fire engines en route \u00b7 " + f.arrived + "/" + total + " arrived");
        hudSub.textContent = f.clockFrozen ? "First engine arrived" : "Response time";
      }
      hud.className = "aegis-hud" + (f.phase === "carrier" ? " live" : "") + (f.clockFrozen ? " frozen" : "");
      hudClock.textContent = fmtClock(f.clockSec);
    }

    // ---- playback
    var vt = 0, speed = cfg.speed, playing = false, lastTs = null, scrubbing = false;

    function setPlayLabel() {
      btnPlay.textContent = playing ? "Pause" : (vt >= tl.total ? "Replay" : "Play");
    }
    function update() {
      var f = frameAt(data, cfg, tl, vt);
      render(f);
      hudText(f);
      if (!scrubbing) slider.value = tl.total > 0 ? Math.round((f.vt / tl.total) * 1000) : 0;
      setPlayLabel();
      return f;
    }
    function tick(ts) {
      if (!playing) return;
      if (lastTs === null) lastTs = ts;
      vt += (ts - lastTs) * speed;
      lastTs = ts;
      if (vt >= tl.total) { vt = tl.total; playing = false; }
      update();
      if (playing) requestAnimationFrame(tick);
    }
    function play() {
      if (vt >= tl.total) vt = 0;
      playing = true; lastTs = null; setPlayLabel();
      requestAnimationFrame(tick);
    }
    function pause() { playing = false; setPlayLabel(); }
    function seek(v) { vt = Math.max(0, Math.min(v, tl.total)); return update(); }

    btnPlay.addEventListener("click", function () { if (playing) pause(); else play(); });
    btnRestart.addEventListener("click", function () { seek(0); play(); });
    slider.addEventListener("input", function () {
      scrubbing = true; pause();
      seek((parseFloat(slider.value) / 1000) * tl.total);
      scrubbing = false;
    });
    sel.addEventListener("change", function () { speed = parseFloat(sel.value) || 1; });

    if (cfg.startAtEnd) seek(tl.total);
    else { seek(0); if (cfg.autoplay) setTimeout(play, 400); }

    return {play: play, pause: pause, seek: seek, timeline: tl, frame: function () { return frameAt(data, cfg, tl, vt); }};
  }

  root.AegisReplay = {
    fmtClock: fmtClock, bearingDeg: bearingDeg, carrierState: carrierState, trailPoints: trailPoints,
    buildTimeline: buildTimeline, frameAt: frameAt, fireRadius: fireRadius, arrivedCount: arrivedCount, mount: mount
  };
})(typeof window !== "undefined" ? window : globalThis);
"""

# Finds the Folium map object in the page and starts the player on it.
MOUNT_JS = r"""
(function () {
  function start() {
    var map = window["__MAP_NAME__"];
    if (!map || !map.setView) {
      for (var k in window) {
        if (k.indexOf("map_") === 0 && window[k] && window[k].setView) { map = window[k]; break; }
      }
    }
    if (!map) { console.error("AEGIS replay: could not find the map object"); return; }
    window.__aegisReplay = window.AegisReplay.mount(map, __DATA__, __CFG__);
  }
  if (document.readyState === "complete") { start(); }
  else { window.addEventListener("load", start); }
})();
"""


# ------------------------------------------------------------ page builder
def _truck_image_data_uri(path=None):
    path = path or TRUCK_IMAGE_FILE
    try:
        with open(path, "rb") as f:
            raw = f.read()
    except OSError:
        return None
    ext = os.path.splitext(path)[1].lower().lstrip(".") or "png"
    mime = {"jpg": "jpeg", "svg": "svg+xml"}.get(ext, ext)
    return f"data:image/{mime};base64," + base64.b64encode(raw).decode("ascii")


def _json_for_script(obj):
    # "</" inside a <script> would end it early; escape it.
    return json.dumps(obj, separators=(",", ":")).replace("</", "<\\/")


def build_cfg(autoplay=True, start_at_end=False, speed=DEFAULT_SPEED, truck_image=None):
    """Settings handed to the browser-side player."""
    if truck_image is None:
        truck_image = _truck_image_data_uri()
    return {
        "scoutMs": SCOUT_MS, "carrierSimPerSec": CARRIER_SIM_PER_SEC, "holdMs": HOLD_MS,
        "speed": speed, "autoplay": bool(autoplay), "startAtEnd": bool(start_at_end),
        "scoutColor": SCOUT_COLOR, "fireColor": FIRE_COLOR,
        "routeStyles": [{"color": c, "weight": w, "dash": d} for c, w, d, _l in fmap.ROUTE_STYLES],
        "truckImage": truck_image, "truckSize": TRUCK_SIZE_PX,
        "imageMode": TRUCK_IMAGE_MODE, "imageFaces": TRUCK_IMAGE_FACES,
    }


def build_replay_html(payload, results, edge_hazards=None, autoplay=True,
                      start_at_end=False, speed=DEFAULT_SPEED, truck_image=None):
    """Full standalone HTML page: the Folium base map + the replay player."""
    folium = fmap.folium
    nodes, edges = results["nodes"], results["edges"]
    nodes_ll = fmap.nodes_to_latlon(nodes)

    m = fmap._new_map(nodes_ll)
    fmap._add_base_graph(m, nodes_ll, edges)
    legend = fmap._road_legend_rows()
    if fmap._add_hazards(m, nodes_ll, edge_hazards if edge_hazards is not None else results.get("random_hazard_edges")):
        legend.append(("dashed", fmap.HAZARD_COLOR, "Debris / blocked (random hazard)"))

    if payload["fire"]["origin"]:
        lat, lon = payload["fire"]["origin"]
        folium.Marker(location=[lat, lon], tooltip="Fire origin",
                      icon=folium.Icon(color="red", icon="fire")).add_to(m)
        legend.append(("dot", fmap.PIN_RED, "Fire origin / spread"))
    if payload["start"]:
        folium.Marker(location=payload["start"], tooltip="Start (Fire Station)",
                      icon=folium.Icon(color="blue", icon="home")).add_to(m)
        legend.append(("dot", fmap.PIN_BLUE, "Start (Fire Station)"))
    if payload["target"]:
        folium.CircleMarker(
            location=payload["target"], radius=9, color="#FFFFFF", weight=2,
            fill=True, fill_color=fmap.TARGET_COLOR, fill_opacity=1.0, tooltip="Target (fire)",
        ).add_to(m)
        legend.append(("dot", fmap.TARGET_COLOR, "Target (fire)"))
    legend.append(("line", SCOUT_COLOR, "Scout path"))
    for _color, _w, dash, label in fmap.ROUTE_STYLES:
        legend.append(("dashed" if dash else "line", _color, label))
    fmap._add_legend(m, legend)

    cfg = build_cfg(autoplay, start_at_end, speed, truck_image)
    mount = (MOUNT_JS.replace("__MAP_NAME__", m.get_name())
                     .replace("__DATA__", _json_for_script(payload))
                     .replace("__CFG__", _json_for_script(cfg)))
    # {% raw %}: Folium runs element text through Jinja; this keeps any
    # brace sequences in the JS/JSON from being treated as template syntax.
    m.get_root().script.add_child(folium.Element("{% raw %}" + REPLAY_JS + mount + "{% endraw %}"))
    return m.get_root().render()