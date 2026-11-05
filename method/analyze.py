"""Measure every tool's routes the same way and write the site data.

Usage: analyze.py out_dir passages.rs ne_10m_land.shp site_data_dir

Per tool and route:
- length: the tool's own line, haversine per leg (R = 3440.065 nm, as in asw).
- start/end gap: great-circle distance from the requested point to the
  line's first/last point. total = gap + line + gap, so every tool is
  measured from the requested start to the requested end.
- land: the line joined to the requested points is walked along great
  circles every 2 nm; a sample is land when it and the four points 3 nm
  north, south, east and west of it lie in the same Natural Earth 1:10m
  land polygon (the rule of asw's reference_distances test). Samples in
  the passage corridor boxes are skipped for every tool.
"""
import json, math, re, sys
from pathlib import Path
import numpy as np
import shapefile, shapely
from shapely import STRtree

R = 3440.065
STEP = 2.0
DEEP = float(sys.argv[5]) if len(sys.argv) > 5 else 3.0
out_dir, passages_rs, land_shp, site_dir = map(Path, sys.argv[1:5])
TOOLS = ["asw", "searoute-py", "scgraph", "searoute-ts", "eurostat"]


def hav(a, b):
    (lo1, la1), (lo2, la2) = a, b
    p1, p2 = math.radians(la1), math.radians(la2)
    dl, dp = math.radians(lo2 - lo1), p2 - p1
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(min(1.0, math.sqrt(h)))


def slerp(a, b, f):
    def v(lon, lat):
        lo, la = math.radians(lon), math.radians(lat)
        return [math.cos(la) * math.cos(lo), math.cos(la) * math.sin(lo), math.sin(la)]
    va, vb = v(*a), v(*b)
    d = math.acos(max(-1.0, min(1.0, sum(x * y for x, y in zip(va, vb)))))
    if d < 1e-12:
        return a
    wa, wb = math.sin((1 - f) * d) / math.sin(d), math.sin(f * d) / math.sin(d)
    p = [wa * x + wb * y for x, y in zip(va, vb)]
    return [math.degrees(math.atan2(p[1], p[0])), math.degrees(math.atan2(p[2], math.hypot(p[0], p[1])))]


def wrap(lon):
    return (lon + 540.0) % 360.0 - 180.0


# passage corridors (min_lon, min_lat, max_lon, max_lat), as in the reference test
src = Path(passages_rs).read_text()
boxes = [tuple(map(float, m)) for m in re.findall(
    r"corridor:\s*\(\s*(-?[\d.]+),\s*(-?[\d.]+),\s*(-?[\d.]+),\s*(-?[\d.]+)\s*\)", src)]
boxes.append((-80.02, 9.25, -79.92, 9.34))  # Gatun Dam box of the reference test
assert len(boxes) >= 20, len(boxes)

polys = []
for shp in shapefile.Reader(str(land_shp)).shapes():
    g = shapely.geometry.shape(shp.__geo_interface__)
    polys += list(g.geoms) if g.geom_type == "MultiPolygon" else [g]
for p in polys:
    shapely.prepare(p)
tree = STRtree(polys)


def deep_mask(pts):
    """pts: array (n, 2) lon/lat -> bool array, deep inside one land polygon."""
    if len(pts) == 0:
        return np.zeros(0, bool)
    lat = pts[:, 1]
    dlat = DEEP / 60.0
    dlon = DEEP / (60.0 * np.maximum(np.cos(np.radians(lat)), 0.01))
    offsets = [(0, 0), (0, dlat), (0, -dlat), (dlon, 0), (-dlon, 0)]
    common = None
    for ox, oy in offsets:
        q = np.column_stack([np.vectorize(wrap)(pts[:, 0] + ox), np.clip(pts[:, 1] + oy, -90, 90)])
        idx_in, idx_tree = tree.query(shapely.points(q), predicate="within")
        s = set(zip(idx_in.tolist(), idx_tree.tolist()))
        common = s if common is None else common & s
    mask = np.zeros(len(pts), bool)
    for i, _ in common:
        mask[i] = True
    return mask


def exempt(lon, lat):
    return any(x0 <= lon <= x1 and y0 <= lat <= y1 for x0, y0, x1, y1 in boxes)


def land_check(line):
    """line: [[lon, lat], ...] -> (land nm, list of land runs as [[lon, lat], ...])."""
    samples, seg_len = [], []
    for a, b in zip(line, line[1:]):
        d = hav(a, b)
        n = max(1, math.ceil(d / STEP))
        for k in range(1, n + 1):
            samples.append(slerp(a, b, k / n))
            seg_len.append(d / n)
    pts = np.array([[wrap(lo), la] for lo, la in samples]) if samples else np.zeros((0, 2))
    mask = deep_mask(pts)
    land_nm, runs, cur = 0.0, [], []
    for (lo, la), m, sl in zip(samples, mask, seg_len):
        if m and not exempt(wrap(lo), la):
            land_nm += sl
            cur.append([lo, la, round(sl, 3)])
        elif cur:
            runs.append(cur); cur = []
    if cur:
        runs.append(cur)
    return land_nm, runs


def unwrap(coords):
    out = []
    for lon, lat in coords:
        if out:
            while lon - out[-1][0] > 180: lon -= 360
            while lon - out[-1][0] < -180: lon += 360
        out.append([lon, lat])
    return out


def rnd(coords, nd=4):
    return [[round(x, nd), round(y, nd)] for x, y in coords]


routes = json.load(open(out_dir / "routes.json"))
raw = {t: json.load(open(out_dir / "raw" / f"{t}.json")) for t in TOOLS}
(site_dir / "routes").mkdir(parents=True, exist_ok=True)
summary = {"tools": {}, "routes": []}
for t in TOOLS:
    summary["tools"][t] = {k: v for k, v in raw[t].items() if k != "routes"}

for r in routes:
    req_from, req_to = [r["from"][1], r["from"][0]], [r["to"][1], r["to"][0]]
    row = {k: r[k] for k in ("id", "name", "set", "from", "to") }
    if "pub151_nm" in r:
        row["pub151_nm"] = r["pub151_nm"]
    row["great_circle_nm"] = round(hav(req_from, req_to), 1)
    row["tools"] = {}
    geo = {"id": r["id"], "name": r["name"], "from": req_from, "to": req_to, "tools": {}}
    for t in TOOLS:
        x = raw[t]["routes"].get(r["id"], {"error": "no result"})
        if "error" in x or not x.get("coords"):
            row["tools"][t] = {"error": x.get("error", "empty geometry")}
            continue
        coords = [[float(c[0]), float(c[1])] for c in x["coords"]]
        line_nm = sum(hav(a, b) for a, b in zip(coords, coords[1:]))
        gap_from, gap_to = hav(req_from, coords[0]), hav(coords[-1], req_to)
        full = [req_from] + coords + [req_to]
        land_nm, runs = land_check(full)
        m = {
            "reported_nm": round(float(x["reported_nm"]), 1) if x.get("reported_nm") is not None else None,
            "line_nm": round(line_nm, 1),
            "gap_from_nm": round(gap_from, 2),
            "gap_to_nm": round(gap_to, 2),
            "total_nm": round(gap_from + line_nm + gap_to, 1),
            "land_nm": round(land_nm, 1),
            "points": len(coords),
            "max_leg_nm": round(max((hav(a, b) for a, b in zip(coords, coords[1:])), default=0), 1),
        }
        if x.get("worst_join_nm", 0) > 1:
            m["hole_nm"] = round(x["worst_join_nm"], 1)
        if "median_s" in x:
            m["median_ms"] = round(x["median_s"] * 1000, 2)
            m["first_ms"] = round(x["first_s"] * 1000, 2)
        if "pub151_nm" in r:
            m["pub151_err_pct"] = round(100 * (m["total_nm"] - r["pub151_nm"]) / r["pub151_nm"], 2)
        row["tools"][t] = m
        geo["tools"][t] = {"line": rnd(unwrap(full)), "land": [[[round(a, 4), round(b, 4), c] for a, b, c in run] for run in runs]}
    summary["routes"].append(row)
    json.dump(geo, open(site_dir / "routes" / f"{r['id']}.json", "w"), separators=(",", ":"))
    print(r["id"], {t: (v.get("total_nm"), v.get("land_nm")) if "error" not in v else "ERR" for t, v in row["tools"].items()}, flush=True)

json.dump(summary, open(site_dir / "summary.json", "w"), indent=1)
print("passage boxes:", len(boxes))
