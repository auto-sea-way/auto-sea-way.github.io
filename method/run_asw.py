"""Query a running `asw serve` for every route. Usage: run_asw.py routes.json out.json port key pid [shore_buffer_nm]"""
import json, statistics, subprocess, sys, time, urllib.request
routes_path, out_path, port, key, pid = sys.argv[1:6]
buffer_nm = float(sys.argv[6]) if len(sys.argv) > 6 else 0.0
routes = json.load(open(routes_path))
def get(path):
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", headers={"X-Api-Key": key})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.load(r)
def route(r):
    return get(f"/route?from={r['from'][0]},{r['from'][1]}&to={r['to'][0]},{r['to'][1]}&shore_buffer={buffer_nm}")
info = get("/info")
# HTTP overhead: /health round trip
times = []
for _ in range(20):
    t = time.perf_counter(); urllib.request.urlopen(f"http://127.0.0.1:{port}/health").read(); times.append(time.perf_counter() - t)
http_s = statistics.median(times)
res = {}
for r in routes:
    try:
        t = time.perf_counter(); f = route(r); first = time.perf_counter() - t
        n = 3 if first > 1 else 10
        ts = []
        for _ in range(n):
            t = time.perf_counter(); route(r); ts.append(time.perf_counter() - t)
        res[r["id"]] = {"coords": f["geometry"]["coordinates"], "reported_nm": f["distance_nm"], "land_legs": f["land_legs"],
                        "first_s": first, "median_s": statistics.median(ts), "runs": n}
    except Exception as e:
        res[r["id"]] = {"error": f"{type(e).__name__}: {e}"[:300]}
    print(r["id"], res[r["id"]].get("reported_nm", res[r["id"]].get("error")), flush=True)
rss = int(subprocess.check_output(["ps", "-o", "rss=", "-p", pid]).decode()) / 1e3
json.dump({"tool": "asw", "version": info["version"], "settings": f"asw serve, GET /route?from=lat,lon&to=lat,lon&shore_buffer={buffer_nm} (canals open, Arctic closed)",
           "info": info, "http_overhead_s": http_s, "rss_mb_after": rss, "routes": res}, open(out_path, "w"))
print("http overhead", round(http_s * 1000, 2), "ms; rss after", round(rss), "MB")
