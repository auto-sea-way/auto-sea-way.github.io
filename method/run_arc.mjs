// Run @arcnautical/maritime-routing on every route.
// Usage: node run_arc.mjs <package dir> routes.json out.json
// findOceanPath keeps a cache of finished routes, so it is cleared before every call.
import fs from 'fs';
import { pathToFileURL } from 'url';

const [pkgDir, routesPath, outPath] = process.argv.slice(2);
const routes = JSON.parse(fs.readFileSync(routesPath, 'utf8'));
const now = () => Number(process.hrtime.bigint()) / 1e9;
const t0 = now();
const arc = await import(pathToFileURL(`${pkgDir}/dist/index.js`).href);
const version = JSON.parse(fs.readFileSync(`${pkgDir}/package.json`, 'utf8')).version;
// routes.json stores [lat, lon]; findOceanPath takes (fromLat, fromLon, toLat, toLon) and returns [lon, lat] pairs
const route = (r) => { arc.clearPathCache(); return arc.findOceanPath(r.from[0], r.from[1], r.to[0], r.to[1]); };
route(routes[0]);
route(routes[routes.length - 1]);
const startup = now() - t0;
let maxRss = process.memoryUsage().rss;
const res = {};
for (const r of routes) {
  try {
    let t = now(); const coords = route(r); const first = now() - t;
    const n = first > 1 ? 3 : 10; const times = [];
    for (let i = 0; i < n; i++) { t = now(); route(r); times.push(now() - t); }
    times.sort((a, b) => a - b);
    const starts = coords[0][0] === r.from[1] && coords[0][1] === r.from[0];
    res[r.id] = { coords, reported_nm: null, first_s: first, median_s: (times[(n - 1) >> 1] + times[n >> 1]) / 2, runs: n, starts_at_request: starts };
  } catch (e) { res[r.id] = { error: `${e.name}: ${e.message}`.slice(0, 300) }; }
  maxRss = Math.max(maxRss, process.memoryUsage().rss);
  console.log(r.id, res[r.id].error ?? `${res[r.id].coords.length} points, ${(res[r.id].median_s * 1000).toFixed(1)} ms`);
}
fs.writeFileSync(outPath, JSON.stringify({ tool: 'arcnautical', version,
  settings: 'findOceanPath(fromLat, fromLon, toLat, toLon), defaults; route cache cleared before every call',
  startup_s: startup, max_rss_mb: maxRss / 1e6, routes: res }));
console.log('startup', startup.toFixed(2), 's; max rss', Math.round(maxRss / 1e6), 'MB');
