"""Fill the generated parts of index.html and benchmarks.html from data/.

Run after changing anything in data/: python3 build.py
Generated parts sit between <!-- build:NAME --> and <!-- /build:NAME --> markers.
"""
import html, json, re, statistics as st
from pathlib import Path

ROOT = Path(__file__).parent
S = json.load(open(ROOT / "data/summary.json"))
T = json.load(open(ROOT / "data/tools.json"))
ORDER = ["asw", "searoute-py", "scgraph", "searoute-ts", "eurostat"]
ROUTES = S["routes"]
PUB = [r for r in ROUTES if r["set"] == "pub151"]
e = html.escape


def label(r):
    return r["name"].replace(" - ", " to ").replace("-", " to ")


def f1(x):
    return f"{x:,.1f}"


def stats():
    out = {}
    closest = {k: 0 for k in ORDER}
    for r in PUB:
        errs = {k: abs(r["tools"][k]["pub151_err_pct"]) for k in ORDER}
        best = min(errs.values())
        for k, v in errs.items():
            closest[k] += v == best
    shortest = {k: 0 for k in ORDER}
    for r in ROUTES:
        ok = {k: m["total_nm"] for k, m in r["tools"].items() if m["land_osm_way_nm"] == 0}
        if ok:
            best = min(ok.values())
            for k, v in ok.items():
                shortest[k] += v <= best + 0.05
    for k in ORDER:
        ms = [r["tools"][k] for r in ROUTES]
        pe = [r["tools"][k]["pub151_err_pct"] for r in PUB]
        tm = [m["median_ms"] for m in ms if "median_ms" in m]
        out[k] = {
            "closest": closest[k],
            "within2": sum(abs(x) <= 2 for x in pe),
            "mean_abs": st.mean(abs(x) for x in pe),
            "max_abs": max(abs(x) for x in pe),
            "land_way": sum(m["land_osm_way_nm"] for m in ms),
            "land_way_routes": sum(m["land_osm_way_nm"] > 0 for m in ms),
            "land_ne_routes": sum(m["land_ne_way_nm"] > 0 for m in ms),
            "land_ne": sum(m["land_ne_way_nm"] for m in ms),
            "median_ms": st.median(tm) if tm else None,
            "max_ms": max(tm) if tm else None,
            "shortest": shortest[k],
        }
    return out


ST = stats()


def name(k):
    t = T[k]
    extra = " (inactive since 2022)" if t.get("inactive") else ""
    return f'<a href="{t["url"]}">{e(t["name"])}</a>{extra}'


def titleblock():
    a = ST["asw"]
    others = [ST[k] for k in ORDER[1:]]
    return f"""<h2 id="tb-title">Test of 5 November 2026</h2>
<p class="small">45 routes and 5 open source sea routers. Every router got the same coordinates.</p>
<dl>
<dt>{a['closest']} of {len(PUB)}</dt><dd>port pairs where auto-sea-way is the closest to the NGA Pub 151 distance. The next router: {max(o['closest'] for o in others)}.</dd>
<dt>{a['within2']} of {len(PUB)}</dt><dd>port pairs within 2&nbsp;% of Pub 151. The other routers: {min(o['within2'] for o in others)} to {max(o['within2'] for o in others)}.</dd>
<dt>{f1(a['land_way'])} nm</dt><dd>over land on all 45 routes together, in one harbour leg that auto-sea-way marks as land itself. The other routers: {min(o['land_way'] for o in others):,.0f} to {max(o['land_way'] for o in others):,.0f} nm.</dd>
<dt>{a['shortest']} of 45</dt><dd>routes where auto-sea-way has the shortest of the lines that stay on water.</dd>
</dl>
<p class="links"><a href="#results">All results</a>, <a href="#others">where the others are better</a>, <a href="benchmarks.html#method">method</a></p>"""


def results():
    rows = []
    for k in ORDER:
        s, t = ST[k], T[k]
        time = f"{s['median_ms']:.2f} ms" if s["median_ms"] is not None and s["median_ms"] < 10 else (
            f"{s['median_ms']:.0f} ms" if s["median_ms"] is not None else "batch only")
        rows.append(f"""<tr><th scope="row"><span class="swatch" style="border-top-color:{t['light']}"></span>{name(k)} {e(t['version'])}</th>
<td>{s['closest']}</td><td>{s['within2']} of 22</td><td>{s['mean_abs']:.2f}&nbsp;%</td><td>{s['max_abs']:.1f}&nbsp;%</td>
<td>{s['land_way_routes']}</td><td>{s['land_way']:,.1f}</td><td>{s['land_ne_routes']}</td><td>{s['shortest']}</td><td>{time}</td></tr>""")
    return f"""<div class="scroll"><table>
<caption>Five routers on the same 45 routes</caption>
<thead><tr><th scope="col">Router</th><th scope="col">Closest to Pub 151</th><th scope="col">Within 2&nbsp;% of Pub 151</th><th scope="col">Mean difference from Pub 151</th><th scope="col">Largest difference</th><th scope="col">Routes over land</th><th scope="col">Over land, nm</th><th scope="col">Routes over land, Natural Earth</th><th scope="col">Shortest line on water</th><th scope="col">Median time per route</th></tr></thead>
<tbody>
{chr(10).join(rows)}
</tbody></table></div>"""


def route_link(r):
    return f'<a class="water" href="index.html#route={r["id"]}">{e(label(r))}</a>'


def per_route_table(caption, routes, cell, extra_cols=()):
    head = "".join(f'<th scope="col">{e(h)}</th>' for h, _ in extra_cols) + "".join(
        f'<th scope="col">{e(T[k]["name"])}</th>' for k in ORDER)
    body = []
    for r in routes:
        cells = "".join(f"<td>{fn(r)}</td>" for _, fn in extra_cols) + "".join(cell(r, k) for k in ORDER)
        body.append(f'<tr><th scope="row">{route_link(r)}</th>{cells}</tr>')
    return f"""<div class="scroll"><table>
<caption>{caption}</caption>
<thead><tr><th scope="col">Route</th>{head}</tr></thead>
<tbody>
{chr(10).join(body)}
</tbody></table></div>"""


def length_cell(r, k):
    m = r["tools"][k]
    ok = [x["total_nm"] for x in r["tools"].values() if x["land_osm_way_nm"] == 0]
    cls = []
    if m["land_osm_way_nm"] > 0:
        cls.append("land")
    elif ok and m["total_nm"] <= min(ok) + 0.05:
        cls.append("best")
    return f'<td class="{" ".join(cls)}">{f1(m["total_nm"])}</td>'


def pub_cell(r, k):
    v = r["tools"][k]["pub151_err_pct"]
    best = min(abs(r["tools"][x]["pub151_err_pct"]) for x in ORDER)
    return f'<td class="{"best" if abs(v) == best else ""}">{v:+.2f}&nbsp;%</td>'


def land_cell(r, k):
    m = r["tools"][k]
    w, n = m["land_osm_way_nm"], m["land_ne_way_nm"]
    txt = "" if w == 0 and n == 0 else f1(w) + (f" ({f1(n)})" if n else "")
    return f'<td class="{"land" if w > 0 else ""}">{txt}</td>'


def time_cell(r, k):
    m = r["tools"][k]
    if "median_ms" not in m:
        return "<td>n/a</td>"
    v = m["median_ms"]
    return f"<td>{v:.2f}</td>" if v < 10 else f"<td>{v:,.0f}</td>"


def tools_table():
    rows = []
    for k in ORDER:
        t = T[k]
        rows.append(f"""<tr><th scope="row">{name(k)}</th><td class="text">{e(t['version'])}</td><td class="text">{e(t['language'])}</td><td class="text">{e(t['license'])}</td><td class="text">{e(t['last_commit'])}</td><td class="text">{e(t['network'])}</td><td class="text">{e(t['install'])}</td><td class="text">{e(t['size'])}</td><td class="text">{e(t['memory'])}</td></tr>""")
    settings = "".join(f"<li><strong>{e(T[k]['name'])}</strong>: <code>{e(T[k]['settings'])}</code>. {e(T[k]['time_note'])}</li>" for k in ORDER)
    return f"""<div class="scroll"><table>
<caption>Routers in the test</caption>
<thead><tr><th scope="col">Router</th><th scope="col">Version</th><th scope="col">Language</th><th scope="col">License</th><th scope="col">Last commit</th><th scope="col">Network</th><th scope="col">Install</th><th scope="col">Size</th><th scope="col">Memory in this test</th></tr></thead>
<tbody>
{chr(10).join(rows)}
</tbody></table></div>
<h3>Settings used</h3>
<ul class="note-list">{settings}</ul>"""


def asw_bench():
    md = (ROOT / "data/asw-bench.md").read_text()
    head = re.search(r"\*\*Graph\*\*: (.*?)\n\*\*Commit\*\*: `(\w+)` \| \*\*Date\*\*: ([\d-]+) \| \*\*Iterations\*\*: (\d+)", md)
    out = [f'<p>auto-sea-way {T["asw"]["version"]} on the planet graph ({e(head.group(1))}), {head.group(4)} runs of each route, measured in the program without HTTP on {head.group(3)}. Distances count only the water legs.</p>']
    for title in ("Sailing Routes", "Passage Transits"):
        block = md.split(f"## {title}")[1].split("##")[0]
        rows = [l for l in block.strip().splitlines() if l.startswith("|") and not l.startswith("|--") and "Route" not in l]
        body = []
        for l in rows:
            c = [x.strip() for x in l.strip("|").split("|")]
            body.append(f'<tr><th scope="row" class="water">{e(c[0].replace("-", " to "))}</th>' + "".join(f"<td>{e(x.replace('nm', ' nm').replace('us', ' µs').replace('ms', ' ms'))}</td>" for x in c[1:]) + "</tr>")
        cap = "Sailing routes" if title == "Sailing Routes" else "Passages"
        out.append(f"""<div class="scroll"><table><caption>{cap}</caption>
<thead><tr><th scope="col">Route</th><th scope="col">Distance</th><th scope="col">Min</th><th scope="col">Median</th><th scope="col">95th percentile</th><th scope="col">Max</th><th scope="col">Graph hops, then legs</th></tr></thead>
<tbody>{chr(10).join(body)}</tbody></table></div>""")
    return "\n".join(out)


def fill(path, parts):
    p = ROOT / path
    s = p.read_text()
    for key, content in parts.items():
        pat = re.compile(rf"(<!-- build:{key} -->\n).*?(<!-- /build:{key} -->)", re.S)
        assert pat.search(s), (path, key)
        s = pat.sub(lambda m: m.group(1) + content + "\n" + m.group(2), s)
    p.write_text(s)


fill("index.html", {"titleblock": titleblock(), "results": results()})
fill("benchmarks.html", {
    "tools": tools_table(),
    "length": per_route_table("Length from the requested start to the requested end, nm", ROUTES, length_cell,
                              [("Straight line", lambda r: f1(r["great_circle_nm"]))]),
    "pub": per_route_table("Difference from the NGA Pub 151 distance", PUB, pub_cell,
                           [("Pub 151, nm", lambda r: f"{r['pub151_nm']:,.0f}")]),
    "land": per_route_table("Over land on the way, nm: OpenStreetMap check (Natural Earth check in brackets)", ROUTES, land_cell),
    "time": per_route_table("Median time per route, ms", [r for r in ROUTES], time_cell),
    "aswbench": asw_bench(),
})
for k in ORDER:
    print(k, {x: (round(y, 2) if isinstance(y, float) else y) for x, y in ST[k].items()})
