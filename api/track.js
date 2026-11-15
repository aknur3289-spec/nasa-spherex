'use strict';
// GET /api/track?name=Ceres
// 1) JPL Horizons gives the object's daily sky position over the SPHEREx mission.
// 2) SPHEREx looks ~90° from the Sun, so it sees an object near quadrature: we keep days with
//    solar elongation within 6° of 90° and ask IRSA (batched TAP) which exposures cover the object that day.
// 3) Each exposure gets the object's position interpolated to its exposure time; frames are then
//    fetched with /api/sky-frame centred on that position (object-centred timelapse).
const { ephemeris, dateToMjd } = require('./_lib/horizons.js');
const { parseCsv } = require('./_lib/irsa.js');
const { send, query } = require('./_lib/http.js');

const TAP = 'https://irsa.ipac.caltech.edu/TAP/sync';
const FILE_RE = /^https:\/\/irsa\.ipac\.caltech\.edu\/ibe\/data\/spherex\/(dr1|qr3)\/[A-Za-z0-9_.\/-]+\.fits$/;

async function tap(conds) {
  const where = conds.map((c) =>
    `(1 = CONTAINS(POINT('ICRS', ${c.ra.toFixed(5)}, ${c.dec.toFixed(5)}), p.poly) AND p.time_bounds_lower BETWEEN ${(c.mjd - 0.5).toFixed(3)} AND ${(c.mjd + 0.5).toFixed(3)})`).join(' OR ');
  const q = "SELECT 'https://irsa.ipac.caltech.edu/' || a.uri AS file_url, p.time_bounds_lower, p.energy_bandpassname, p.obsid " +
    'FROM spherex.artifact a JOIN spherex.plane p ON a.planeid = p.planeid ' +
    `WHERE p.energy_bandpassname IN ('SPHEREx-D1','SPHEREx-D2','SPHEREx-D3') AND (${where})`;
  const url = `${TAP}?REQUEST=doQuery&LANG=ADQL&FORMAT=csv&MAXREC=3000&QUERY=${encodeURIComponent(q)}`;
  const r = await fetch(url, { signal: AbortSignal.timeout(40000) });
  if (!r.ok) throw new Error('IRSA HTTP ' + r.status);
  const text = await r.text();
  if (/^\s*</.test(text)) throw new Error('IRSA TAP error document');
  return parseCsv(text);
}

function interp(rows, mjd) {
  let i = rows.findIndex((r) => r.mjd > mjd);
  if (i <= 0) i = Math.max(1, Math.min(rows.length - 1, i < 0 ? rows.length - 1 : 1));
  const a = rows[i - 1], b = rows[i];
  const t = (mjd - a.mjd) / (b.mjd - a.mjd || 1);
  let dra = b.ra - a.ra;
  if (dra > 180) dra -= 360;
  if (dra < -180) dra += 360;
  return { ra: ((a.ra + t * dra) % 360 + 360) % 360, dec: a.dec + t * (b.dec - a.dec), delta_au: a.delta_au + t * (b.delta_au - a.delta_au) };
}

module.exports = async (req, res) => {
  const q = query(req);
  const name = String(q.name || '').slice(0, 60);
  if (!name.trim()) return send(res, 400, { error: 'name is required' });
  try {
    const eph = await ephemeris(name, '2025-05-01', '2026-10-15', '1d');
    const rows = eph.rows.map((r) => ({ ...r, mjd: dateToMjd(r.date) })).filter((r) => Number.isFinite(r.mjd));
    if (rows.length < 10) throw new Error('No ephemeris for this object');
    const days = rows.filter((r) => Math.abs(r.elong_deg - 90) <= 6);
    if (!days.length) return send(res, 200, { name, target: eph.target, exposures: [], note: 'The object never reached ~90° from the Sun during the mission, where SPHEREx looks.' });
    const batches = [];
    for (let i = 0; i < days.length; i += 8) batches.push(days.slice(i, i + 8));
    const settled = await Promise.allSettled(batches.map(tap));
    const found = new Map();
    let failures = 0;
    for (const s of settled) {
      if (s.status !== 'fulfilled') { failures++; continue; }
      for (const r of s.value) {
        if (!FILE_RE.test(r.file_url)) continue;
        const key = `${r.obsid}:${r.energy_bandpassname}`;
        if (!found.has(key)) found.set(key, r);
      }
    }
    if (!found.size && failures) throw new Error('IRSA did not answer');
    const exposures = [...found.values()].map((r) => {
      const mjd = Number(r.time_bounds_lower);
      const p = interp(rows, mjd);
      return { file_url: r.file_url, obs_id: r.obsid, detector: Number(String(r.energy_bandpassname).split('D').pop()), mjd, ra: p.ra, dec: p.dec, delta_au: p.delta_au };
    }).sort((a, b) => a.mjd - b.mjd);
    send(res, 200, {
      name, target: eph.target, n_exposures: exposures.length, exposures,
      windows: days.length, failures,
      source: 'Ephemeris: NASA JPL Horizons (geocentric). Images: NASA/IPAC IRSA SPHEREx L2 (DR1 + QR3).',
    }, 'public, s-maxage=21600, stale-while-revalidate=86400');
  } catch (e) {
    send(res, 503, { error: String(e.message || e), retry: true });
  }
};
