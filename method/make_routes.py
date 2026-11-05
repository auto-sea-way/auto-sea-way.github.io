"""Collect the benchmark routes from the asw sources into routes.json."""
import json, re, sys
repo, out = sys.argv[1], sys.argv[2]
bench = open(f"{repo}/crates/asw-cli/src/bench.rs").read()
ref = open(f"{repo}/crates/asw-core/tests/reference_distances.rs").read()
num = r"(-?\d+(?:\.\d+)?)"
routes = []
block = bench.split("const ROUTES")[1].split("];")[0]
for i, m in enumerate(re.finditer(rf'\("([^"]+)",\s*{num},\s*{num},\s*{num},\s*{num}\)', block)):
    name, a, b, c, d = m.groups()
    routes.append({"name": name, "set": "sailing" if i < 13 else "passage",
                   "from": [float(a), float(b)], "to": [float(c), float(d)]})
block = ref.split("const PUB151")[1].split("];")[0]
for m in re.finditer(rf'\("([^"]+)",\s*{num},\s*{num},\s*{num},\s*{num},\s*{num}\)', block):
    name, a, b, c, d, nm = m.groups()
    routes.append({"name": name, "set": "pub151", "from": [float(a), float(b)],
                   "to": [float(c), float(d)], "pub151_nm": float(nm)})
for r in routes:
    r["id"] = re.sub(r"[^a-z0-9]+", "-", r["name"].lower()).strip("-")
assert len(routes) == 45, len(routes)
assert len({r["id"] for r in routes}) == 45
json.dump(routes, open(out, "w"), indent=1)
print(len(routes), "routes")
