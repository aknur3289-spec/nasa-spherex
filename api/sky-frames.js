'use strict';
// GET /api/sky-frames?ra=&dec=  → every SPHEREx L2 exposure (DR1 + QR3) covering the point.
const { searchExposures } = require('./_lib/irsa.js');
const { coords, send, query } = require('./_lib/http.js');

module.exports = async (req, res) => {
  const q = query(req);
  const c = coords(q);
  if (!c) return send(res, 400, { error: 'ra and dec in degrees are required' });
  const [ra, dec] = c.map(v => Math.round(v * 1e5) / 1e5);
  try {
    const exposures = await searchExposures(ra, dec);
    send(res, 200, {
      ra_deg: ra, dec_deg: dec, n_exposures: exposures.length, exposures,
      source: 'NASA/IPAC IRSA TAP, SPHEREx L2 (DR1 + QR3)', generated_utc: new Date().toISOString(),
    }, 'public, s-maxage=21600, stale-while-revalidate=86400');
  } catch (e) {
    send(res, 503, { error: 'IRSA did not answer: ' + String(e.message || e), retry: true });
  }
};
