'use strict';
// TAN-SIP celestial WCS (FITS 1-based pixels) and the SPHEREx WAVE-TAB wavelength lookup.
const D2R = Math.PI / 180;

function sipTerms(cards, prefix) {
  const order = cards.get(prefix + '_ORDER');
  const terms = [];
  if (!order) return terms;
  for (let p = 0; p <= order; p++) for (let q = 0; q + p <= order; q++) {
    const c = cards.get(`${prefix}_${p}_${q}`);
    if (c) terms.push([p, q, c]);
  }
  return terms;
}
const poly = (terms, u, v) => { let s = 0; for (const [p, q, c] of terms) s += c * u ** p * v ** q; return s; };

function celestial(cards) {
  const g = (k, d) => (cards.has(k) ? cards.get(k) : d);
  const c1 = g('CDELT1', 1), c2 = g('CDELT2', 1);
  let m;
  if (cards.has('CD1_1')) m = [g('CD1_1', 0), g('CD1_2', 0), g('CD2_1', 0), g('CD2_2', 0)];
  else m = [g('PC1_1', 1) * c1, g('PC1_2', 0) * c1, g('PC2_1', 0) * c2, g('PC2_2', 1) * c2];
  const det = m[0] * m[3] - m[1] * m[2];
  const inv = [m[3] / det, -m[1] / det, -m[2] / det, m[0] / det];
  const w = {
    crpix: [g('CRPIX1'), g('CRPIX2')], ra0: g('CRVAL1') * D2R, dec0: g('CRVAL2') * D2R, m, inv,
    A: sipTerms(cards, 'A'), B: sipTerms(cards, 'B'), AP: sipTerms(cards, 'AP'), BP: sipTerms(cards, 'BP'),
  };
  if (!/TAN/.test(String(g('CTYPE1', '')))) throw new Error('Only TAN projection supported');
  return w;
}

function pix2sky(w, x, y) {
  const u = x - w.crpix[0], v = y - w.crpix[1];
  const U = u + poly(w.A, u, v), V = v + poly(w.B, u, v);
  const xi = (w.m[0] * U + w.m[1] * V) * D2R, eta = (w.m[2] * U + w.m[3] * V) * D2R;
  const den = Math.cos(w.dec0) - eta * Math.sin(w.dec0);
  const ra = w.ra0 + Math.atan2(xi, den);
  const dec = Math.atan2(Math.sin(w.dec0) + eta * Math.cos(w.dec0), Math.hypot(xi, den));
  return [((ra / D2R) % 360 + 360) % 360, dec / D2R];
}

function sky2pix(w, raDeg, decDeg) {
  const ra = raDeg * D2R, dec = decDeg * D2R, dA = ra - w.ra0;
  const cosc = Math.sin(w.dec0) * Math.sin(dec) + Math.cos(w.dec0) * Math.cos(dec) * Math.cos(dA);
  if (cosc <= 0) return [NaN, NaN];
  const xi = Math.cos(dec) * Math.sin(dA) / cosc / D2R;
  const eta = (Math.cos(w.dec0) * Math.sin(dec) - Math.sin(w.dec0) * Math.cos(dec) * Math.cos(dA)) / cosc / D2R;
  const U = w.inv[0] * xi + w.inv[1] * eta, V = w.inv[2] * xi + w.inv[3] * eta;
  let u = U + poly(w.AP, U, V), v = V + poly(w.BP, U, V);
  // Two Newton-free refinement passes against the forward SIP, so AP/BP inconsistencies do not matter.
  for (let k = 0; k < 3 && w.A.length; k++) {
    u = U - poly(w.A, u, v);
    v = V - poly(w.B, u, v);
  }
  return [u + w.crpix[0], v + w.crpix[1]];
}

// Bilinear WAVE-TAB lookup. x, y: 1-based cutout pixels. Returns [wavelength_um, bandwidth_um].
function waveAt(cards, table, x, y) {
  const g = (k, d) => (cards.has(k) ? cards.get(k) : d);
  const px = (x - g('CRPIX1W', 0)) * g('CDELT1W', 1) + g('CRVAL1W', 0);
  const py = (y - g('CRPIX2W', 0)) * g('CDELT2W', 1) + g('CRVAL2W', 0);
  const X = table.X.values, Y = table.Y.values, V = table.VALUES.values;
  const nx = X.length;
  const loc = (arr, p) => {
    if (p <= arr[0]) return [0, 0];
    for (let i = 0; i < arr.length - 1; i++) if (p <= arr[i + 1]) return [i, (p - arr[i]) / (arr[i + 1] - arr[i] || 1)];
    return [arr.length - 2, 1];
  };
  const [i, fx] = loc(X, px), [j, fy] = loc(Y, py);
  const at = (m, a, b) => V[m + 2 * (a + nx * b)];
  const out = [0, 1].map(m => (1 - fx) * (1 - fy) * at(m, i, j) + fx * (1 - fy) * at(m, i + 1, j)
    + (1 - fx) * fy * at(m, i, j + 1) + fx * fy * at(m, i + 1, j + 1));
  return out;
}

module.exports = { celestial, pix2sky, sky2pix, waveAt };
