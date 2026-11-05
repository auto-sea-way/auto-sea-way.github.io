# auto-sea-way.github.io

The website of [auto-sea-way](https://github.com/auto-sea-way/asw), open source sea routing: https://auto-sea-way.github.io

It is a static site. The comparison of sea routers lives in `data/`:

- `data/summary.json`: every number per router and route
- `data/routes/<route>.json`: the lines of all routers for one route, and the parts over land
- `data/tools.json`: versions, licenses and settings of the routers
- `data/asw-bench.md`: the latest `asw bench` tables

`method/` has the scripts that ran the routers and measured the lines. After a change in `data/`, run `python3 build.py` to update the tables in `index.html` and `benchmarks.html`.

Third-party files: MapLibre GL JS 6.15.0 (BSD-3-Clause, `vendor/`), Spectral and Barlow Semi Condensed (SIL Open Font License, `fonts/`). Map tiles from OpenFreeMap, © OpenMapTiles, data from OpenStreetMap.
