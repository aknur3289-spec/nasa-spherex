'use strict';
// IRSA access for the live "any point" mode. Runs on Vercel (US), not in the browser.
const TAP = 'https://irsa.ipac.caltech.edu/TAP/sync';
const FILE_RE = /^https:\/\/irsa\.ipac\.caltech\.edu\/ibe\/data\/spherex\/(dr1|qr3|qr2|qr)\/[A-Za-z0-9_.\/-]+\.fits$/;

async function fetchRetry(url, opts = {}, tries = 3) {
  let last;
  for (let i = 0; i < tries; i++) {
    try {
      const r = await fetch(url, { ...opts, signal: AbortSignal.timeout(opts.timeout || 25000) });
      if (r.ok) return r;
      last = new Error('IRSA HTTP ' + r.status);
      if (r.status < 500 && r.status !== 429) break;
    } catch (e) { last = e; }
    await new Promise(res => setTimeout(res, 800 * (i + 1)));
  }
  throw last;
}

function parseCsv(text) {
  const rows = [];
  let row = [], cell = '', q = false;
  for (let i = 0; i < text.length; i++) {
    const ch = text[i];
    if (q) {
      if (ch === '"') { if (text[i + 1] === '"') { cell += '"'; i++; } else q = false; }
      else cell += ch;
    } else if (ch === '"') q = true;
    else if (ch === ',') { row.push(cell); cell = ''; }
    else if (ch === '\n' || ch === '\r') {
      if (ch === '\r' && text[i + 1] === '\n') i++;
      row.push(cell); cell = '';
      if (row.length > 1 || row[0] !== '') rows.push(row);
      row = [];
    } else cell += ch;
  }
  if (cell !== '' || row.length) { row.push(cell); rows.push(row); }
  const [head, ...body] = rows;
  return body.map(r => Object.fromEntries(head.map((h, i) => [h.trim().toLowerCase(), (r[i] ?? '').trim()])));
}

const version = url => {
  const m = /l2b(?:_retry)?-v(\d+)-(\d+)-(\d+)/i.exec(url);
  return m ? m.slice(1).map(Number) : [0, 0, 0];
};
const newer = (a, b) => { for (let i = 0; i < 3; i++) if (a[i] !== b[i]) return a[i] > b[i]; return false; };

async function searchExposures(ra, dec) {
  const query =
    "SELECT 'https://irsa.ipac.caltech.edu/' || a.uri AS file_url, a.uri, p.time_bounds_lower, " +
    'p.energy_bandpassname, p.obsid ' +
    'FROM spherex.artifact a JOIN spherex.plane p ON a.planeid = p.planeid ' +
    `WHERE 1 = CONTAINS(POINT('ICRS', ${ra}, ${dec}), p.poly) ` +
    "AND (a.uri LIKE '%/spherex/dr1/%' OR a.uri LIKE '%/spherex/qr3/%') " +
    'ORDER BY p.time_bounds_lower';
  const url = `${TAP}?REQUEST=doQuery&LANG=ADQL&FORMAT=csv&QUERY=${encodeURIComponent(query)}`;
  const text = await (await fetchRetry(url, { timeout: 40000 }, 2)).text();
  if (/^\s*</.test(text)) throw new Error('IRSA TAP returned an error document');
  const kept = new Map();
  for (const r of parseCsv(text)) {
    const file = r.file_url;
    if (!FILE_RE.test(file)) continue;
    const band = r.energy_bandpassname || '';
    const detector = Number(band.split('D').pop());
    const key = `${r.obsid}:${detector}`;
    const item = {
      file_url: file, obs_id: r.obsid, detector,
      mjd: Number(r.time_bounds_lower),
      collection: /\/spherex\/qr3\//.test(file) ? 'spherex_qr3' : 'spherex_dr1',
    };
    const old = kept.get(key);
    if (!old || newer(version(file), version(old.file_url))) kept.set(key, item);
  }
  return [...kept.values()].filter(x => Number.isFinite(x.mjd) && x.detector >= 1 && x.detector <= 6)
    .sort((a, b) => a.mjd - b.mjd);
}

async function fetchCutout(fileUrl, ra, dec, sizeDeg) {
  if (!FILE_RE.test(fileUrl)) throw new Error('Not a SPHEREx L2 file URL');
  const url = `${fileUrl}?center=${ra},${dec}d&size=${sizeDeg}`;
  const r = await fetchRetry(url, { timeout: 30000 }, 3);
  return { buf: Buffer.from(await r.arrayBuffer()), url };
}

module.exports = { searchExposures, fetchCutout, parseCsv, FILE_RE };
