'use strict';
// Turn one SPHEREx L2 cutout into a north-up, east-left image on a common grid.
const { readFits, image, tableRow } = require('./fits.js');
const { celestial, sky2pix, waveAt } = require('./wcs.js');

// Mask policy decided by Science (docs/DECISIONS.md): these bits become NaN.
const BAD_BITS = 333057605;
const D2R = Math.PI / 180;
const GRID = 99;          // output pixels per side (10′ at 6.15″/px, like our static fields)
const SCALE = 6.15 / 3600; // deg per output pixel

function gridToSky(ra0, dec0, col, row) {
  const c = (GRID - 1) / 2;
  const xi = (c - col) * SCALE * D2R;  // east is left
  const eta = (c - row) * SCALE * D2R; // north is up (row 0 at top)
  const d0 = dec0 * D2R;
  const den = Math.cos(d0) - eta * Math.sin(d0);
  const ra = ra0 * D2R + Math.atan2(xi, den);
  const dec = Math.atan2(Math.sin(d0) + eta * Math.cos(d0), Math.hypot(xi, den));
  return [ra / D2R, dec / D2R];
}

function processCutout(buf, ra0, dec0) {
  const hdus = readFits(buf);
  const find = name => {
    const h = hdus.find(x => x.name === name);
    if (!h) throw new Error('Cutout has no ' + name + ' extension');
    return h;
  };
  const imH = find('IMAGE');
  const img = image(buf, imH), flags = image(buf, find('FLAGS'));
  const zodiH = hdus.find(x => x.name === 'ZODI');
  const zodi = zodiH ? image(buf, zodiH) : null;
  const wave = tableRow(buf, find('WCS-WAVE'));
  const wcs = celestial(imH.cards);
  const { w, h } = img;

  const src = new Float32Array(w * h);
  for (let i = 0; i < w * h; i++) {
    const v = img.data[i] - (zodi ? zodi.data[i] : 0);
    src[i] = (flags.data[i] & BAD_BITS) || !Number.isFinite(v) ? NaN : v;
  }

  const out = new Float32Array(GRID * GRID);
  let bad = 0;
  for (let row = 0; row < GRID; row++) for (let col = 0; col < GRID; col++) {
    const [ra, dec] = gridToSky(ra0, dec0, col, row);
    const [x, y] = sky2pix(wcs, ra, dec);   // 1-based
    const fx = x - 1, fy = y - 1;           // 0-based
    const x0 = Math.floor(fx), y0 = Math.floor(fy);
    let sum = 0, wsum = 0;
    for (const [dx, dy] of [[0, 0], [1, 0], [0, 1], [1, 1]]) {
      const xi = x0 + dx, yi = y0 + dy;
      if (xi < 0 || yi < 0 || xi >= w || yi >= h) continue;
      const wt = (dx ? fx - x0 : 1 - (fx - x0)) * (dy ? fy - y0 : 1 - (fy - y0));
      const v = src[yi * w + xi];
      if (Number.isFinite(v) && wt > 0) { sum += wt * v; wsum += wt; }
    }
    // FITS row 0 is the bottom; our output row 0 is the top (north), handled by gridToSky.
    const val = wsum >= 0.5 ? sum / wsum : NaN;
    out[row * GRID + col] = val;
    if (!Number.isFinite(val)) bad++;
  }

  const [xc, yc] = sky2pix(wcs, ra0, dec0);
  const [wavelength, bandwidth] = waveAt(imH.cards, wave, xc, yc);
  const inside = xc >= 1 && yc >= 1 && xc <= w && yc <= h;
  const c = imH.cards;
  return {
    width: GRID, height: GRID, pixel_scale_arcsec: 6.15,
    values: out,
    wavelength_um: wavelength, bandwidth_um: bandwidth,
    center_inside: inside,
    bad_pixel_fraction: bad / (GRID * GRID),
    obs_id: String(c.get('OBSID') || ''),
    detector: Number(c.get('DETECTOR') || 0),
    mjd: Number(c.get('MJD-AVG') || c.get('MJD-OBS')),
    obs_time_utc: String(c.get('DATE-AVG') || c.get('DATE-OBS') || '') + 'Z',
    psf_fwhm_arcsec: Number(c.get('PSF_FWHM') || NaN),
  };
}

module.exports = { processCutout, BAD_BITS, GRID };
