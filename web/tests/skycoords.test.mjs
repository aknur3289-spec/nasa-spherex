import assert from 'node:assert/strict';
import test from 'node:test';
import { parseCoords, insideSquare, separationDeg } from '../src/survey/skyCoords.ts';

const close = (a, b, eps = 1e-3) => assert.ok(Math.abs(a - b) < eps, `${a} vs ${b}`);
test('parses degrees and sexagesimal coordinates', () => {
  let c = parseCoords('210.80 54.35'); close(c.ra, 210.8); close(c.dec, 54.35);
  c = parseCoords('210.80, +54.35'); close(c.ra, 210.8);
  c = parseCoords('14h03m13s +54°20′'); close(c.ra, 210.8042); close(c.dec, 54.3333);
  c = parseCoords('14:03:13 +54:20:00'); close(c.ra, 210.8042);
  c = parseCoords('00h00m10s −01°30′00″'); close(c.dec, -1.5);
  assert.equal(parseCoords('M101'), null);
  assert.equal(parseCoords('400 10'), null);
  assert.equal(parseCoords('10 95'), null);
});
test('field membership and separation', () => {
  const m101 = { ra: 210.802, dec: 54.349 };
  assert.ok(insideSquare({ ra: 210.80, dec: 54.35 }, m101, 10));
  assert.ok(!insideSquare({ ra: 211.2, dec: 54.35 }, m101, 10));
  assert.ok(insideSquare({ ra: 359.99, dec: 0 }, { ra: 0.02, dec: 0 }, 10));
  close(separationDeg({ ra: 0, dec: 0 }, { ra: 1, dec: 0 }), 1);
});
