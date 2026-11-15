import assert from 'node:assert/strict';
import test from 'node:test';
import { KNOWN_OBJECTS, resolveKnownObject } from '../src/survey/knownObjects.ts';

test('known objects use rounded J2000 coordinates and case/space-insensitive aliases', () => {
  assert.equal(KNOWN_OBJECTS.length, 30);
  assert.deepEqual(resolveKnownObject(' M 101 '), { ra: 210.802, dec: 54.349 });
  assert.deepEqual(resolveKnownObject('pLeIaDeS'), resolveKnownObject('M45'));
  assert.deepEqual(resolveKnownObject('Andromeda Galaxy'), resolveKnownObject('m 31'));
  assert.deepEqual(resolveKnownObject('orionnebula'), resolveKnownObject('M42'));
  assert.deepEqual(resolveKnownObject('Crab Nebula'), resolveKnownObject('M1'));
  assert.deepEqual(resolveKnownObject('Galactic Center'), resolveKnownObject('Sgr A*'));
  assert.deepEqual(resolveKnownObject('north   ecliptic pole'), resolveKnownObject('NEP'));
  assert.deepEqual(resolveKnownObject('Ecliptic Field'), { ra: 27.911, dec: 11.472 });
  assert.equal(resolveKnownObject('unknown object'), null);
  for (const object of KNOWN_OBJECTS) {
    assert.ok(object.ra >= 0 && object.ra < 360 && Math.abs(object.dec) <= 90);
    assert.equal(object.ra, Number(object.ra.toFixed(3)));
    assert.equal(object.dec, Number(object.dec.toFixed(3)));
  }
});
