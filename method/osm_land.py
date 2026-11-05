"""Second land check on the OSM land polygons (detailed coastline).

Usage: osm_land.py land_polygons.shp passages.rs site_data_dir

Every route line in site_data_dir/routes/*.json (already joined to the
requested start and end) is walked along great circles every 0.5 nm. A
sample is land when it and the four points 0.1 nm north, south, east and
west of it are all inside OSM land polygons. Passage corridor boxes are
skipped, as in the Natural Earth check. Adds land_osm_nm to summary.json
and the land runs (key "land_osm") to each route file.
"""
import json, math, re, struct, sys
from pathlib import Path
import numpy as np
import shapefile, shapely
from shapely import STRtree

R = 3440.065
STEP = 0.5
DEEP = 0.1
shp_path, passages_rs, site = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])

boxes = [tuple(map(float, m)) for m in re.findall(
    r"corridor:\s*\(\s*(-?[\d.]+),\s*(-?[\d.]+),\s*(-?[\d.]+),\s*(-?[\d.]+)\s*\)", passages_rs.read_text())]
boxes.append((-80.02, 9.25, -79.92, 9.34))


def hav(a, b):
    (lo1, la1), (lo2, la2) = a, b
    p1, p2 = math.radians(la1), math.radians(la2)
    h = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lo2 - lo1) / 2) ** 2
    return 2 * R * math.asin(min(1.0, math.sqrt(h)))


def slerp(a, b, f):
    def v(lon, lat):
        lo, la = math.radians(lon), math.radians(lat)
        return [math.cos(la) * math.cos(lo), math.cos(la) * math.sin(lo), math.sin(la)]
    va, vb = v(*a), v(*b)
    d = math.acos(max(-1.0, min(1.0, sum(x * y for x, y in zip(va, vb)))))
    if d < 1e-12:
        return list(a)
    wa, wb = math.sin((1 - f) * d) / math.sin(d), math.sin(f * d) / math.sin(d)
    p = [wa * x + wb * y for x, y in zip(va, vb)]
    return [math.degrees(math.atan2(p[1], p[0])), math.degrees(math.atan2(p[2], math.hypot(p[0], p[1])))]


def wrap(lon):
    return (lon + 540.0) % 360.0 - 180.0


# 1. all samples of all lines
jobs = []  # (route_id, tool, samples[(lon,lat)], seg_len[])
for f in sorted((site / "routes").glob("*.json")):
    g = json.load(open(f))
    for tool, v in g["tools"].items():
        line = v["line"]
        samples, seg = [], []
        for a, b in zip(line, line[1:]):
            d = hav(a, b)
            n = max(1, math.ceil(d / STEP))
            for k in range(1, n + 1):
                samples.append(slerp(a, b, k / n))
                seg.append(d / n)
        jobs.append((g["id"], tool, samples, seg))
allpts = np.array([[wrap(lo), la] for _, _, s, _ in jobs for lo, la in s])
print("samples", len(allpts), flush=True)

# 2. polygon bboxes straight from the .shp records (offsets from the .shx)
shx = np.fromfile(shp_path.with_suffix(".shx"), dtype=">i4", offset=100).reshape(-1, 2)
offsets = shx[:, 0].astype(np.int64) * 2
mm = np.memmap(shp_path, dtype=np.uint8, mode="r")
idx = offsets[:, None] + 12 + np.arange(32)[None, :]
bb = np.frombuffer(np.asarray(mm[idx]).tobytes(), dtype="<f8").reshape(-1, 4)  # xmin ymin xmax ymax
print("polygons", len(bb), flush=True)
btree = STRtree(shapely.box(bb[:, 0], bb[:, 1], bb[:, 2], bb[:, 3]))
dlat = DEEP / 60.0
dlon = DEEP / (60.0 * np.maximum(np.cos(np.radians(allpts[:, 1])), 0.01))
offs = [(0, 0), (0, dlat), (0, -dlat), (dlon, 0), (-dlon, 0)]
need = set()
for ox, oy in offs:
    q = shapely.points(np.column_stack([allpts[:, 0] + ox, np.clip(allpts[:, 1] + oy, -90, 90)]))
    _, hit = btree.query(q, predicate="intersects")
    need.update(hit.tolist())
_ends = [[r[k][1], r[k][0]] for r in json.load(open(site / "summary.json"))["routes"] for k in ("from", "to")]
_, hit = btree.query(shapely.points(np.array(_ends)), predicate="intersects")
need.update(hit.tolist())
print("candidate polygons", len(need), flush=True)

# 3. load only those polygons
rd = shapefile.Reader(str(shp_path))
ids = sorted(need)
polys = [shapely.geometry.shape(rd.shape(i).__geo_interface__) for i in ids]
for p in polys:
    shapely.prepare(p)
tree = STRtree(polys)
inside = np.ones(len(allpts), bool)
for ox, oy in offs:
    q = shapely.points(np.column_stack([allpts[:, 0] + ox, np.clip(allpts[:, 1] + oy, -90, 90)]))
    a, _ = tree.query(q, predicate="within")
    m = np.zeros(len(allpts), bool)
    m[a] = True
    inside &= m
print("land samples before passage boxes", int(inside.sum()), flush=True)

# 4. is each requested point on OSM land?
summary = json.load(open(site / "summary.json"))
def on_land(lon, lat):
    p = shapely.points([[lon, lat]])
    a, _ = tree.query(p, predicate="within")
    return bool(len(a))
for r in summary["routes"]:
    r["from_on_land"] = on_land(r["from"][1], r["from"][0])
    r["to_on_land"] = on_land(r["to"][1], r["to"][0])
# 5. per line: land nm and runs
rows = {r["id"]: r for r in summary["routes"]}
files = {}
pos = 0
for rid, tool, samples, seg in jobs:
    n = len(samples)
    mask = inside[pos:pos + n]
    pos += n
    land, runs, cur = 0.0, [], []
    for (lo, la), m, sl in zip(samples, mask, seg):
        w = wrap(lo)
        if m and not any(x0 <= w <= x1 and y0 <= la <= y1 for x0, y0, x1, y1 in boxes):
            land += sl
            cur.append([round(lo, 4), round(la, 4), round(sl, 3)])
        elif cur:
            runs.append(cur); cur = []
    if cur:
        runs.append(cur)
    rows[rid]["tools"][tool]["land_osm_nm"] = round(land, 1)
    g = files.setdefault(rid, json.load(open(site / "routes" / f"{rid}.json")))
    g["tools"][tool]["land_osm"] = runs
for rid, g in files.items():
    json.dump(g, open(site / "routes" / f"{rid}.json", "w"), separators=(",", ":"))
json.dump(summary, open(site / "summary.json", "w"), indent=1)
for r in summary["routes"]:
    print(f'{r["id"]:32s}', " ".join(f'{t[:8]:8s} {m.get("land_osm_nm", "-"):>6}' for t, m in r["tools"].items()))
