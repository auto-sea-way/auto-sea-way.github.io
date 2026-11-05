"""Run one Python sea router on every route. Usage: run_py.py TOOL routes.json out.json cache_dir"""
import json, resource, statistics, sys, time
tool, routes_path, out_path, cache = sys.argv[1:5]
routes = json.load(open(routes_path))
t0 = time.perf_counter()
if tool == "searoute-py":
    import searoute as sr
    import importlib.metadata as md
    version = md.version("searoute")
    settings = "searoute(origin, destination, units='naut', append_orig_dest=True), default restrictions (Northwest Passage closed)"
    def route(r):
        f = sr.searoute([r["from"][1], r["from"][0]], [r["to"][1], r["to"][0]], units="naut", append_orig_dest=True)
        return f["geometry"]["coordinates"], f["properties"]["length"]
elif tool == "scgraph":
    from scgraph import GeoGraph
    import importlib.metadata as md
    version = md.version("scgraph")
    g = GeoGraph.load_geograph("marnet", cache_dir=cache)
    settings = "GeoGraph.load_geograph('marnet').get_shortest_path(origin, destination, output_units='km'), defaults otherwise"
    def route(r):
        p = g.get_shortest_path({"latitude": r["from"][0], "longitude": r["from"][1]},
                                {"latitude": r["to"][0], "longitude": r["to"][1]}, output_units="km")
        return [[lon, lat] for lat, lon in p["coordinate_path"]], p["length"] / 1.852
else:
    sys.exit("unknown tool")
# warm-up: the first call loads the network
warm = routes[0]
route(warm)
startup_s = time.perf_counter() - t0
res = {}
for r in routes:
    try:
        t = time.perf_counter(); coords, nm = route(r); cold = time.perf_counter() - t
        n = 3 if cold > 1 else 10
        times = []
        for _ in range(n):
            t = time.perf_counter(); route(r); times.append(time.perf_counter() - t)
        res[r["id"]] = {"coords": coords, "reported_nm": nm, "first_s": cold, "median_s": statistics.median(times), "runs": n}
    except Exception as e:
        res[r["id"]] = {"error": f"{type(e).__name__}: {e}"[:300]}
    print(r["id"], res[r["id"]].get("reported_nm", res[r["id"]].get("error")), flush=True)
rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e6  # bytes on macOS
json.dump({"tool": tool, "version": version, "settings": settings, "startup_s": startup_s,
           "max_rss_mb": rss, "routes": res}, open(out_path, "w"))
print("startup", round(startup_s, 2), "s; max rss", round(rss), "MB")
