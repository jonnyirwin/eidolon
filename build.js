#!/usr/bin/env node
// Local Ergogen build that injects the custom footprints in ./footprints/
// (the npm CLI doesn't auto-load an external footprint folder).
//
//   node build.js            -> output/
//   node build.js --no-debug -> skip points/demo extras
//
// Online ergogen.xyz users: paste footprints/*.js into the web app's Footprints
// section under the same name (e.g. "reset_button").
const fs = require('fs');
const path = require('path');
const yaml = require('js-yaml');
const ergogen = require('ergogen');

const FP_DIR = path.join(__dirname, 'footprints');
const OUT = path.join(__dirname, 'output');
const debug = !process.argv.includes('--no-debug');

// inject every footprint module in ./footprints/ by filename
for (const file of fs.readdirSync(FP_DIR).filter(f => f.endsWith('.js'))) {
  const name = path.basename(file, '.js');
  ergogen.inject('footprint', name, require(path.join(FP_DIR, file)));
  console.log(`injected footprint: ${name}`);
}

const write = (rel, data) => {
  if (!data) return;
  const abs = path.join(OUT, rel);
  fs.mkdirSync(path.dirname(abs), { recursive: true });
  fs.writeFileSync(abs, abs.endsWith('.yaml') ? yaml.dump(data) : data);
};
const composite = (data, rel) => {
  if (!data) return;
  if (data.yaml) write(rel + '.yaml', data.yaml);
  for (const fmt of ['svg', 'dxf', 'jscad']) if (data[fmt]) write(rel + '.' + fmt, data[fmt]);
};

(async () => {
  const raw = fs.readFileSync(path.join(__dirname, 'config.yaml'), 'utf8');
  const results = await ergogen.process(raw, { debug, svg: true }, console.log);
  fs.rmSync(OUT, { recursive: true, force: true });
  for (const [n, o] of Object.entries(results.outlines || {})) composite(o, `outlines/${n}`);
  for (const [n, c] of Object.entries(results.cases || {})) composite(c, `cases/${n}`);
  for (const [n, pcb] of Object.entries(results.pcbs || {})) write(`pcbs/${n}.kicad_pcb`, pcb);
  composite(results.demo, 'points/demo');
  if (results.points) write('points/points.yaml', results.points);
  console.log('Done. PCBs:', Object.keys(results.pcbs || {}).join(', ') || '(none)');
})().catch(e => { console.error(e.message || e); process.exit(1); });
