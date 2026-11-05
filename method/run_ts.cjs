// Run searoute-ts on every route. Usage: node run_ts.cjs routes.json out.json  (cwd = folder with node_modules)
const fs = require('fs');
const [routesPath, outPath] = process.argv.slice(2);
const routes = JSON.parse(fs.readFileSync(routesPath, 'utf8'));
const now = () => Number(process.hrtime.bigint()) / 1e9;
const t0 = now();
const req = require('module').createRequire(process.cwd() + '/package.json');
const s = req('searoute-ts');
const net = req('searoute-ts/marnet-20km').DEFAULT_MARNET;
const version = JSON.parse(fs.readFileSync(process.cwd() + '/node_modules/searoute-ts/package.json')).version;
const route = r => {
  const f = s.seaRoute([r.from[1], r.from[0]], [r.to[1], r.to[0]], { network: net, appendOriginDestination: true, units: 'nauticalmiles' });
  return [f.geometry, f.properties.length];
};
try { route(routes[0]); } catch (e) {}
try { route(routes[routes.length - 1]); } catch (e) {}
const startup = now() - t0;
let maxRss = process.memoryUsage().rss;
const res = {};
for (const r of routes) {
  try {
    let t = now(); const [geom, nm] = route(r); const first = now() - t;
    const n = first > 1 ? 3 : 10; const times = [];
    for (let i = 0; i < n; i++) { t = now(); route(r); times.push(now() - t); }
    times.sort((a, b) => a - b);
    const coords = geom.type === 'MultiLineString' ? geom.coordinates.flat() : geom.coordinates;
    res[r.id] = { coords, reported_nm: nm, first_s: first, median_s: (times[(n - 1) >> 1] + times[n >> 1]) / 2, runs: n, geom_type: geom.type };
  } catch (e) { res[r.id] = { error: `${e.name}: ${e.message}`.slice(0, 300) }; }
  maxRss = Math.max(maxRss, process.memoryUsage().rss);
  console.log(r.id, res[r.id].reported_nm ?? res[r.id].error);
}
fs.writeFileSync(outPath, JSON.stringify({ tool: 'searoute-ts', version,
  settings: "seaRoute(origin, destination, {network: marnet-20km, appendOriginDestination: true, units: 'nauticalmiles'})",
  startup_s: startup, max_rss_mb: maxRss / 1e6, routes: res }));
console.log('startup', startup.toFixed(2), 's; max rss', Math.round(maxRss / 1e6), 'MB');
