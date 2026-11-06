"""Fill the generated parts of index.html and benchmarks.html from data/.

Run after changing anything in data/: python3 build.py
Generated parts sit between <!-- build:NAME --> and <!-- /build:NAME --> markers.
"""
import html, json, re, statistics as st
from pathlib import Path

ROOT = Path(__file__).parent
S = json.load(open(ROOT / "data/summary.json"))
T = json.load(open(ROOT / "data/tools.json"))
ORDER = ["asw", "searoute-py", "scgraph", "searoute-ts", "eurostat", "arcnautical"]
ROUTES = S["routes"]
PUB = [r for r in ROUTES if r["set"] == "pub151"]
e = html.escape


def label(r):
    return r["name"].replace(" - ", " to ").replace("-", " to ")


def f1(x):
    return f"{x:,.1f}"


SHORT = [r for r in ROUTES if r["great_circle_nm"] < 200]  # straits, canals and short crossings


def on_water(r, key="total_nm"):
    """Values of the lines with no land on the way. A line over land is not compared."""
    return {k: abs(m[key]) for k, m in r["tools"].items() if m["land_osm_way_nm"] == 0}


def winners(routes, key="total_nm", tol=0.05):
    won = {k: 0 for k in ORDER}
    for r in routes:
        ok = on_water(r, key)
        if ok:
            best = min(ok.values())
            for k, v in ok.items():
                won[k] += v <= best + tol
    return won


def stats():
    out = {}
    closest = winners(PUB, "pub151_err_pct", 0)
    shortest = winners(ROUTES)
    shortest_short = winners(SHORT)
    for k in ORDER:
        ms = [r["tools"][k] for r in ROUTES]
        pe = [r["tools"][k]["pub151_err_pct"] for r in PUB]
        tm = [m["median_ms"] for m in ms if "median_ms" in m]
        out[k] = {
            "closest": closest[k],
            "mean_abs": st.mean(abs(x) for x in pe),
            "land_way": sum(m["land_osm_way_nm"] for m in ms),
            "land_way_routes": sum(m["land_osm_way_nm"] > 0 for m in ms),
            "median_ms": st.median(tm) if tm else None,
            "shortest": shortest[k],
            "shortest_short": shortest_short[k],
            "short_above": st.median(100 * (r["tools"][k]["total_nm"] / min(on_water(r).values()) - 1)
                                     for r in SHORT if on_water(r)),
            "short_land_routes": sum(r["tools"][k]["land_osm_way_nm"] > 0 for r in SHORT),
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
    best = lambda key: max(o[key] for o in others)
    return f"""<h2 id="tb-title">Six open source sea routers, 45 routes</h2>
<p class="small">Tested on 5 and 6 November 2026. Every router got the same start and end points.</p>
<table class="tb">
<thead><tr><td></td><th scope="col">auto-sea-way</th><th scope="col">Best other router</th></tr></thead>
<tbody>
<tr><th scope="row">Shortest by sea, {len(SHORT)} short routes</th><td>{a['shortest_short']}</td><td>{best('shortest_short')}</td></tr>
<tr><th scope="row">Shortest by sea, all 45 routes</th><td>{a['shortest']}</td><td>{best('shortest')}</td></tr>
<tr><th scope="row">Closest to official distances, {len(PUB)} port pairs</th><td>{a['closest']}</td><td>{best('closest')}</td></tr>
<tr><th scope="row">Land crossed, all routes</th><td>{f1(a['land_way'])}&nbsp;nm*</td><td>{min(o['land_way'] for o in others):,.0f}&nbsp;nm</td></tr>
</tbody></table>
<p class="small note">Short routes are under 200&nbsp;nm. A route that crosses land does not count as by sea. *&nbsp;One 0.4&nbsp;nm leg in Honolulu harbour, which auto-sea-way reports as land.</p>
<p class="links"><a href="#results">All results</a>, <a href="#others">where the others are better</a>, <a href="benchmarks.html#method">method</a></p>"""


def results():
    rows = []
    for k in ORDER:
        s, t = ST[k], T[k]
        time = f"{s['median_ms']:.2f} ms" if s["median_ms"] is not None and s["median_ms"] < 10 else (
            f"{s['median_ms']:.0f} ms" if s["median_ms"] is not None else "batch only")
        short = "auto-sea-way" if k == "asw" else t["short"]  # full names are on the benchmarks page
        rows.append(f"""<tr><th scope="row"><span class="swatch" style="border-top-color:{t['light']}"></span><a href="{t['url']}">{e(short)}</a> <span class="ver">{e(t['version'])}</span></th>
<td>{s['shortest']}</td><td>{s['shortest_short']}</td><td>{s['closest']}</td><td>{s['mean_abs']:.2f}&nbsp;%</td><td>{s['land_way_routes']}</td><td>{time}</td></tr>""")
    return f"""<div class="scroll"><table aria-label="Results of {len(ORDER)} routers on 45 routes">
<thead><tr><th scope="col">Router</th><th scope="col">Shortest by sea, all 45 routes</th><th scope="col">Shortest by sea, {len(SHORT)} short routes</th><th scope="col">Closest to Pub 151, {len(PUB)} pairs</th><th scope="col">Mean difference from Pub 151</th><th scope="col">Routes over land</th><th scope="col">Median time per route</th></tr></thead>
<tbody>
{chr(10).join(rows)}
</tbody></table></div>"""


def route_link(r):
    return f'<a class="water" href="./#{r["id"]}">{e(label(r))}</a>'


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
    ok = on_water(r, "pub151_err_pct")
    cls = "land" if k not in ok else ("best" if abs(v) == min(ok.values()) else "")
    return f'<td class="{cls}">{v:+.2f}&nbsp;%</td>'


def short_table():
    rows = []
    for k in ORDER:
        s = ST[k]
        rows.append(f'<tr><th scope="row">{name(k)}</th><td>{s["shortest_short"]} of {len(SHORT)}</td>'
                    f'<td>{s["short_above"]:.1f}&nbsp;%</td><td>{s["short_land_routes"]} of {len(SHORT)}</td></tr>')
    names = ", ".join(e(label(r)) for r in SHORT)
    return f"""<div class="scroll"><table>
<caption>The {len(SHORT)} routes under 200&nbsp;nm</caption>
<thead><tr><th scope="col">Router</th><th scope="col">Shortest line on water</th><th scope="col">Median length above the shortest line on water</th><th scope="col">Routes over land</th></tr></thead>
<tbody>
{chr(10).join(rows)}
</tbody></table></div>
<p class="small">The routes: {names}.</p>"""


def land_cell(r, k):
    m = r["tools"][k]
    w, n = m["land_osm_way_nm"], m["land_ne_way_nm"]
    txt = "" if w == 0 and n == 0 else f1(w) + (f" ({f1(n)})" if n else "")
    return f'<td class="{"land" if w > 0 else ""}">{txt}</td>'




def tools_table():
    rows = []
    for k in ORDER:
        t = T[k]
        rows.append(f"""<tr><th scope="row">{name(k)}</th><td class="text">{e(t['version'])}</td><td class="text">{e(t['language'])}</td><td class="text">{e(t['license'])}</td><td class="text">{e(t['last_commit'])}</td><td class="text">{e(t['network'])}</td><td class="text">{e(t['install'])}</td><td class="text">{e(t['size'])}</td><td class="text">{e(t['memory'])}</td></tr>""")
    settings = "".join(f"<li><strong>{e(T[k]['name'])}</strong>: <code>{e(T[k]['settings'])}</code>. {e(T[k]['time_note'])}</li>" for k in ORDER)
    return f"""<div class="scroll"><table>
<caption>Routers in the test</caption>
<thead><tr><th scope="col">Router</th><th scope="col">Version</th><th scope="col">Language</th><th scope="col">License</th><th scope="col">Last commit</th><th scope="col">Network</th><th scope="col">Install</th><th scope="col">Size on disk</th><th scope="col">Memory in this test</th></tr></thead>
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
    "aswbench": asw_bench(),
    "short": short_table(),
})
for k in ORDER:
    print(k, {x: (round(y, 2) if isinstance(y, float) else y) for x, y in ST[k].items()})
