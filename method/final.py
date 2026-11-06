"""Final site data: land away from inland endpoints, clean route files, tool table.

Usage: final.py site_data_dir out_dir

Land within END_NM of a requested point that is itself on OSM land is
reported apart ("at an inland start or end point"): every tool has to
cross it. Everything else is "land on the way".
"""
import json, math, sys
from pathlib import Path

R = 3440.065
END_NM = 10.0
site, out = Path(sys.argv[1]), Path(sys.argv[2])


def hav(a, b):
    (lo1, la1), (lo2, la2) = a, b
    p1, p2 = math.radians(la1), math.radians(la2)
    h = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lo2 - lo1) / 2) ** 2
    return 2 * R * math.asin(min(1.0, math.sqrt(h)))


summary = json.load(open(site / "summary.json"))
for r in summary["routes"]:
    ends = [e for e, flag in ((r["from"][::-1], r["from_on_land"]), (r["to"][::-1], r["to_on_land"])) if flag]
    g = json.load(open(site / "routes" / f"{r['id']}.json"))
    for t, v in g["tools"].items():
        m = r["tools"][t]
        for key, src in (("ne", "land"), ("osm", "land_osm")):
            way = end = 0.0
            runs = []
            for run in v.pop(src, []):
                cur, cur_end = [], None
                for lon, lat, seg in run:
                    at_end = any(hav([lon, lat], e) <= END_NM for e in ends)
                    if at_end:
                        end += seg
                    else:
                        way += seg
                    if cur and at_end != cur_end:
                        runs.append({"end": cur_end, "c": cur}); cur = []
                    cur.append([lon, lat]); cur_end = at_end
                if cur:
                    runs.append({"end": cur_end, "c": cur})
            # land samples are in -180..180; move each run next to the (unwrapped) line
            for run in runs:
                c = run["c"]
                for i in range(1, len(c)):
                    while c[i][0] - c[i - 1][0] > 180: c[i][0] -= 360
                    while c[i][0] - c[i - 1][0] < -180: c[i][0] += 360
                shift = min((-720, -360, 0, 360, 720), key=lambda s: min(
                    abs(c[0][0] + s - p[0]) + abs(c[0][1] - p[1]) for p in v["line"]))
                run["c"] = [[round(x + shift, 4), y] for x, y in c]
            m[f"land_{key}_way_nm"] = round(way, 1)
            m[f"land_{key}_end_nm"] = round(end, 1)
            if key == "osm":
                v["land"] = runs
        m.pop("land_nm", None)
        m.pop("land_osm_nm", None)
    json.dump(g, open(site / "routes" / f"{r['id']}.json", "w"), separators=(",", ":"))
summary["method"] = {"end_nm": END_NM, "ne_step_nm": 2.0, "ne_deep_nm": 3.0, "osm_step_nm": 0.5, "osm_deep_nm": 0.1,
                     "earth_radius_nm": R, "ne_skips": "all passage boxes of auto-sea-way",
                     "osm_skips": "nothing; OSM water polygons count as water inside the Panama and Kiel canal boxes",
                     "compared": "only lines with no land on the way (OSM check)"}
json.dump(summary, open(site / "summary.json", "w"), indent=1)
print("done")
