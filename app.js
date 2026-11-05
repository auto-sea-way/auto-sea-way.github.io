import { Map, NavigationControl, AttributionControl, LngLatBounds } from './vendor/maplibre-gl-6.15.0/maplibre-gl.mjs';

const ORDER = ['eurostat', 'searoute-ts', 'scgraph', 'searoute-py', 'asw']; // drawing order, asw on top
const STYLE = { light: 'https://tiles.openfreemap.org/styles/positron', dark: 'https://tiles.openfreemap.org/styles/dark' };
const GROUPS = [['sailing', 'Sailing routes'], ['passage', 'Passages'], ['pub151', 'NGA Pub 151 port pairs']];

const $ = (s) => document.querySelector(s);
const fmt = (x, d = 1) => (x == null ? '' : x.toLocaleString('en-GB', { minimumFractionDigits: d, maximumFractionDigits: d }));
const theme = () => {
  const t = document.documentElement.dataset.theme;
  if (t === 'light' || t === 'dark') return t;
  return matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
};

let tools, summary, map, current, hidden = new Set(), focusTool = null;

async function main() {
  [tools, summary] = await Promise.all([
    fetch('data/tools.json').then((r) => r.json()),
    fetch('data/summary.json').then((r) => r.json()),
  ]);
  const sel = $('#route');
  for (const [set, label] of GROUPS) {
    const g = document.createElement('optgroup');
    g.label = label;
    for (const r of summary.routes.filter((x) => x.set === set)) g.append(new Option(r.name.replace(' - ', ' to ').replace('-', ' to '), r.id));
    sel.append(g);
  }
  sel.addEventListener('change', () => { location.hash = 'route=' + sel.value; });
  window.addEventListener('hashchange', fromHash);

  try {
    map = new Map({
      container: 'map', style: STYLE[theme()], center: [20, 30], zoom: 1.5,
      attributionControl: false, cooperativeGestures: matchMedia('(pointer: coarse)').matches,
    });
    map.addControl(new NavigationControl({ showCompass: false }), 'top-right');
    map.addControl(new AttributionControl({ compact: false }));
    map.on('style.load', () => { addLayers(); if (current) draw(current); });
    matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => map.setStyle(STYLE[theme()]));
  } catch (e) {
    $('#map').innerHTML = '<p style="padding:1rem">The map could not start in this browser (it needs WebGL). The numbers for each route are in the table.</p>';
    map = null;
  }
  fromHash();
}

function fromHash() {
  const m = location.hash.match(/route=([a-z0-9-]+)/);
  const id = m && summary.routes.some((r) => r.id === m[1]) ? m[1] : 'aegean-hop';
  $('#route').value = id;
  if (m) document.getElementById('compare').scrollIntoView({ block: 'start' });
  load(id);
}

async function load(id) {
  const geo = await fetch(`data/routes/${id}.json`).then((r) => r.json());
  current = geo;
  table(id);
  if (map && map.isStyleLoaded() && map.getSource('lines')) draw(geo);
}

function addLayers() {
  const t = theme();
  const empty = { type: 'FeatureCollection', features: [] };
  for (const s of ['lines', 'land', 'points']) map.addSource(s, { type: 'geojson', data: empty });
  map.addLayer({ id: 'land-end', type: 'line', source: 'land', filter: ['==', ['get', 'end'], true],
    layout: { 'line-cap': 'round', 'line-join': 'round' },
    paint: { 'line-color': t === 'dark' ? '#a3b6c7' : '#4a6278', 'line-width': 9, 'line-opacity': 0.35, 'line-dasharray': [0.6, 1.2] } });
  map.addLayer({ id: 'land-way', type: 'line', source: 'land', filter: ['==', ['get', 'end'], false],
    layout: { 'line-cap': 'round', 'line-join': 'round' },
    paint: { 'line-color': t === 'dark' ? '#ff6a55' : '#d7301f', 'line-width': 12, 'line-opacity': 0.55 } });
  for (const k of ORDER) {
    const paint = { 'line-color': tools[k][t], 'line-width': k === 'asw' ? 4 : 2.5 };
    if (tools[k].dash) paint['line-dasharray'] = tools[k].dash;
    map.addLayer({ id: 'line-' + k, type: 'line', source: 'lines', filter: ['==', ['get', 'tool'], k],
      layout: { 'line-join': 'round', 'line-cap': k === 'asw' ? 'round' : 'butt' }, paint });
  }
  map.addLayer({ id: 'points', type: 'circle', source: 'points',
    paint: { 'circle-radius': 6, 'circle-color': ['case', ['==', ['get', 'kind'], 'start'], t === 'dark' ? '#e3ecf3' : '#0e2f4f', t === 'dark' ? '#0c1d2e' : '#ffffff'],
      'circle-stroke-width': 2.5, 'circle-stroke-color': t === 'dark' ? '#e3ecf3' : '#0e2f4f' } });
  applyVisibility();
}

function draw(geo) {
  const lines = [], land = [];
  const b = new LngLatBounds();
  for (const [k, v] of Object.entries(geo.tools)) {
    lines.push({ type: 'Feature', properties: { tool: k }, geometry: { type: 'LineString', coordinates: v.line } });
    for (const run of v.land) {
      land.push({ type: 'Feature', properties: { tool: k, end: run.end },
        geometry: run.c.length > 1 ? { type: 'LineString', coordinates: run.c } : { type: 'LineString', coordinates: [run.c[0], run.c[0]] } });
    }
    if (!hidden.has(k)) for (const c of v.line) b.extend(c);
  }
  const shift = geo.tools.asw.line[0][0] - geo.from[0];
  const pts = [{ kind: 'start', c: [geo.from[0] + shift, geo.from[1]] }, { kind: 'end', c: geo.tools.asw.line.at(-1) }];
  map.getSource('lines').setData({ type: 'FeatureCollection', features: lines });
  map.getSource('land').setData({ type: 'FeatureCollection', features: land });
  map.getSource('points').setData({ type: 'FeatureCollection', features: pts.map((p) => ({ type: 'Feature', properties: { kind: p.kind }, geometry: { type: 'Point', coordinates: p.c } })) });
  applyVisibility();
  if (!b.isEmpty()) map.fitBounds(b, { padding: 40, maxZoom: 11, duration: matchMedia('(prefers-reduced-motion: reduce)').matches ? 0 : 600 });
}

function applyVisibility() {
  if (!map || !map.getLayer('line-asw')) return;
  for (const k of ORDER) {
    map.setLayoutProperty('line-' + k, 'visibility', hidden.has(k) ? 'none' : 'visible');
    map.setPaintProperty('line-' + k, 'line-opacity', focusTool && focusTool !== k ? 0.2 : 1);
  }
  const shown = ['in', ['get', 'tool'], ['literal', ORDER.filter((k) => !hidden.has(k) && (!focusTool || focusTool === k))]];
  map.setFilter('land-way', ['all', ['==', ['get', 'end'], false], shown]);
  map.setFilter('land-end', ['all', ['==', ['get', 'end'], true], shown]);
}

function table(id) {
  const r = summary.routes.find((x) => x.id === id);
  const t = theme();
  const facts = [['Straight line', fmt(r.great_circle_nm) + ' nm']];
  if (r.pub151_nm) facts.push(['NGA Pub 151', fmt(r.pub151_nm, 0) + ' nm']);
  $('#facts').innerHTML = facts.map(([a, b]) => `<div><span>${a}</span><span>${b}</span></div>`).join('');
  $('#pubcol').hidden = !r.pub151_nm;
  const rows = [...ORDER].reverse().map((k) => {
    const m = r.tools[k];
    const land = m.land_osm_way_nm;
    const time = m.median_ms != null ? fmt(m.median_ms, m.median_ms < 10 ? 2 : 0) : '<span title="batch only">n/a</span>';
    const dash = tools[k].dash ? 'dashed' : 'solid';
    return `<tr data-tool="${k}">
      <th scope="row"><label><input type="checkbox" ${hidden.has(k) ? '' : 'checked'} aria-label="Show ${tools[k].name} on the map"><span class="swatch" style="border-top-color:${tools[k][t]};border-top-style:${dash}"></span>${k === 'asw' ? 'auto-sea-way' : tools[k].short}</label></th>
      <td>${fmt(m.total_nm)}</td>
      <td ${r.pub151_nm ? '' : 'hidden'}>${m.pub151_err_pct != null ? (m.pub151_err_pct > 0 ? '+' : '') + fmt(m.pub151_err_pct, 1) + ' %' : ''}</td>
      <td class="${land > 0 ? 'land' : ''}">${fmt(land)}</td>
      <td>${time}</td></tr>`;
  });
  const tb = $('#rtable tbody');
  tb.innerHTML = rows.join('');
  for (const tr of tb.querySelectorAll('tr')) {
    const k = tr.dataset.tool;
    tr.querySelector('input').addEventListener('change', (e) => {
      e.target.checked ? hidden.delete(k) : hidden.add(k);
      applyVisibility();
    });
    const on = () => { focusTool = k; applyVisibility(); tb.querySelectorAll('tr').forEach((x) => x.classList.toggle('dim', x !== tr)); };
    const off = () => { focusTool = null; applyVisibility(); tb.querySelectorAll('tr').forEach((x) => x.classList.remove('dim')); };
    tr.addEventListener('mouseenter', on); tr.addEventListener('mouseleave', off);
    tr.addEventListener('focusin', on); tr.addEventListener('focusout', off);
  }
  $('#routenote').textContent = NOTES[id] || '';
}

// Notes for routes where the numbers need a sentence. Facts from the measured data.
const NOTES = {
  'shanghai-rotterdam': 'scgraph goes through the Northern Sea Route, which the other routers close by default. scgraph has no option to close it.',
  'dardanelles': 'The start point is on land between the Gulf of Saros and the Sea of Marmara. auto-sea-way joins the water on the Saros side and goes around the peninsula, so searoute-ts and searoute-py are shorter here.',
  'honolulu-sydney': 'The eurostat/searoute line has two gaps at the 180th meridian (236 nm and 131 nm). They are joined with straight lines here.',
  'kiel-canal': 'searoute-py and scgraph have no Kiel Canal and go around Denmark.',
  'malacca-route': 'The end point is in the town of Phuket. eurostat/searoute ends its line 98 nm from it.',
};

main();
