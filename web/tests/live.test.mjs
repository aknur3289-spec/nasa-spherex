import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { livePairs, pickExposures } from '../src/live/liveData.ts';

const require = createRequire(import.meta.url);
const { parseCsv, FILE_RE } = require('../../api/_lib/irsa.js');
const { waveAt } = require('../../api/_lib/wcs.js');

const frame = (id, mjd, wl) => ({ id, mjd, wavelength_um: wl });

test('live pairs use the pipeline rules (Δλ/λ ≤ 2 % high, ≤ 5 % medium, Δt ≥ 150 d)', () => {
  const pairs = livePairs([frame('f001', 60800, 1.40), frame('f002', 61000, 1.41), frame('f003', 61000, 1.46), frame('f004', 60850, 1.40)]);
  const byKey = Object.fromEntries(pairs.map((p) => [p.a + p.b, p]));
  assert.equal(byKey.f001f002.trust, 'high');
  assert.equal(byKey.f001f003.trust, 'medium');
  assert.equal(byKey.f001f004, undefined, 'pairs closer than 150 days are excluded');
  assert.deepEqual(pairs.map((p) => p.trust), [...pairs.map((p) => p.trust)].sort((a, b) => ['high', 'medium', 'low'].indexOf(a) - ['high', 'medium', 'low'].indexOf(b)));
});

test('exposure picking keeps time order and the cap', () => {
  const all = Array.from({ length: 200 }, (_, i) => ({ file_url: 'u' + i, obs_id: 'o' + i, detector: (i % 6) + 1, mjd: 60800 + i, collection: 'spherex_dr1' }));
  const pick = pickExposures(all, 48);
  assert.equal(pick.length, 48);
  assert.ok(pick.every((e) => e.detector <= 3));
  assert.ok(pick.every((e, i) => i === 0 || e.mjd > pick[i - 1].mjd));
});

test('TAP CSV parsing and file URL guard', () => {
  const rows = parseCsv('file_url,obsid\n"https://irsa.ipac.caltech.edu/ibe/data/spherex/dr1/level2/a/b.fits",X1\n');
  assert.equal(rows[0].obsid, 'X1');
  assert.ok(FILE_RE.test(rows[0].file_url));
  assert.ok(!FILE_RE.test('https://evil.example/ibe/data/spherex/dr1/a.fits'));
});

test('WAVE-TAB lookup interpolates the SPHEREx table layout (2, X, Y)', () => {
  const cards = new Map([['CRPIX1W', 0], ['CRPIX2W', 0], ['CDELT1W', 1], ['CDELT2W', 1], ['CRVAL1W', 0], ['CRVAL2W', 0]]);
  const X = { values: [0, 10] }, Y = { values: [0, 10] };
  // wavelength = 1 + 0.01*x, bandwidth = 0.1 everywhere; index m + 2*(i + 2*j)
  const V = { values: [1.0, 0.1, 1.1, 0.1, 1.0, 0.1, 1.1, 0.1] };
  const [wl, bw] = waveAt(cards, { X, Y, VALUES: V }, 5, 5);
  assert.ok(Math.abs(wl - 1.05) < 1e-9);
  assert.ok(Math.abs(bw - 0.1) < 1e-9);
});
