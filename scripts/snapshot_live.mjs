// Save live SPHEREx frames for the preset points so the demo works even when IRSA is down.
// Uses the production API (Vercel talks to IRSA). Run from the repo root:
//   node scripts/snapshot_live.mjs            (all presets)
//   node scripts/snapshot_live.mjs orion-nebula
// Output: web/public/data/live/<slug>.json  (real frames only; nothing is invented)
import { mkdirSync, writeFileSync, existsSync } from 'node:fs';

const API = process.env.API ?? 'https://nasa-spherex-seven.vercel.app';
const PRESETS = [
  { slug: 'orion-nebula', name: 'Orion Nebula', ra: 83.822, dec: -5.391 },
  { slug: 'pleiades', name: 'Pleiades', ra: 56.601, dec: 24.114 },
  { slug: 'm31', name: 'M31', ra: 10.685, dec: 41.269 },
  { slug: 'm101', name: 'M101', ra: 210.802, dec: 54.349 },
  { slug: 'crab-nebula', name: 'Crab Nebula', ra: 83.633, dec: 22.015 },
];
const MAX = 48;
const only = process.argv[2];
mkdirSync('web/public/data/live', { recursive: true });

async function getJson(url, tries = 4) {
  for (let i = 0; i < tries; i++) {
    try {
      const r = await fetch(url, { signal: AbortSignal.timeout(70000) });
      const j = await r.json();
      if (r.ok) return j;
      console.log('  retry', r.status, j.error ?? '');
    } catch (e) { console.log('  retry', String(e.message ?? e)); }
    await new Promise((res) => setTimeout(res, 3000 * (i + 1)));
  }
  throw new Error('failed: ' + url);
}

for (const p of PRESETS.filter((x) => !only || x.slug === only)) {
  const out = `web/public/data/live/${p.slug}.json`;
  if (existsSync(out) && !process.env.FORCE) { console.log('skip (exists)', out); continue; }
  console.log('==', p.name);
  const list = await getJson(`${API}/api/sky-frames?ra=${p.ra}&dec=${p.dec}`);
  const swir = list.exposures.filter((e) => e.detector <= 3);
  const pool = swir.length >= 12 ? swir : list.exposures;
  const pick = pool.length <= MAX ? pool : Array.from({ length: MAX }, (_, i) => pool[Math.floor((i * pool.length) / MAX)]);
  const frames = [];
  let next = 0;
  await Promise.all(Array.from({ length: 6 }, async () => {
    while (next < pick.length) {
      const e = pick[next++];
      try {
        const f = await getJson(`${API}/api/sky-frame?ra=${p.ra}&dec=${p.dec}&url=${encodeURIComponent(e.file_url)}`, 2);
        if (f.center_inside && f.bad_pixel_fraction <= 0.6) frames.push(f);
        process.stdout.write('.');
      } catch { process.stdout.write('x'); }
    }
  }));
  console.log(`\n  ${frames.length} frames of ${list.n_exposures} exposures`);
  writeFileSync(out, JSON.stringify({ ...p, total: list.n_exposures, saved_utc: new Date().toISOString(), source: 'NASA/IPAC IRSA via /api (real SPHEREx L2 cutouts)', frames }));
}
