"""Chain eurostat's MultiLineString parts (network edges, any order and direction) into one line."""
import json, math, sys
src, routes_path, out = sys.argv[1:4]
R = 3440.065
def hav(a, b):
    (lo1, la1), (lo2, la2) = a, b
    p1, p2 = math.radians(la1), math.radians(la2)
    h = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lo2 - lo1) / 2) ** 2
    return 2 * R * math.asin(min(1.0, math.sqrt(h)))
routes = {r["id"]: r for r in json.load(open(routes_path))}
d = json.load(open(src))
res = {}
for f in d["features"]:
    p, g = f["properties"], f["geometry"]
    r = routes[p["id"]]
    parts = [list(map(list, x)) for x in (g["coordinates"] if g["type"] == "MultiLineString" else [g["coordinates"]])]
    start = [r["from"][1], r["from"][0]]
    # first part: the one with an end nearest the requested start
    best = min(range(len(parts)), key=lambda i: min(hav(start, parts[i][0]), hav(start, parts[i][-1])))
    cur = parts.pop(best)
    if hav(start, cur[-1]) < hav(start, cur[0]):
        cur.reverse()
    line, worst = cur, 0.0
    while parts:
        end = line[-1]
        i = min(range(len(parts)), key=lambda i: min(hav(end, parts[i][0]), hav(end, parts[i][-1])))
        nxt = parts.pop(i)
        if hav(end, nxt[-1]) < hav(end, nxt[0]):
            nxt.reverse()
        worst = max(worst, hav(end, nxt[0]))
        line += nxt[1:] if hav(end, nxt[0]) < 1e-6 else nxt
    reported = float(p["distKM"]) / 1.852
    line_nm = sum(hav(a, b) for a, b in zip(line, line[1:]))
    res[p["id"]] = {"coords": line, "reported_nm": reported, "snap_from_km": p["dFromKM"], "snap_to_km": p["dToKM"], "worst_join_nm": worst}
    flag = "" if abs(line_nm - reported) < 0.01 * reported + 1 else "  <-- MISMATCH"
    print(f'{p["id"]:32s} parts->line {line_nm:9.1f} reported {reported:9.1f} worst join {worst:.3f}{flag}')
json.dump({"tool": "eurostat", "version": "3.6",
           "settings": "java -jar searoute-jar-3.6.jar -i in.csv -o out.geojson -res 5 -kiel 1 -corinth 1 (5 km network, the finest; Kiel and Corinth opened to match asw; other passages at their defaults, Northwest and Northeast passages closed)",
           "startup_s": 1.4, "max_rss_mb": 372.8,
           "batch_note": "45 routes in one run: 9.1 s, 19.5 s and 17.3 s in three runs; one route alone: 1.4 to 1.6 s (JVM start and network build)",
           "routes": res}, open(out, "w"))
