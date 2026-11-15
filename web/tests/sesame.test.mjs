import assert from 'node:assert/strict';
import test from 'node:test';
import { parseSesamePosition } from '../src/survey/sesame.ts';

const fixture = `#=A M101\n%J 210.80227 +54.34895\n%I M101\n`;

test('reads the position line from a Sesame response', () => {
  assert.deepEqual(parseSesamePosition(fixture), { ra: 210.80227, dec: 54.34895 });
  assert.deepEqual(parseSesamePosition('%J 359.64779 -1.63079\n'), { ra: 359.64779, dec: -1.63079 });
  assert.equal(parseSesamePosition('#=A Unknown\n'), null);
  assert.equal(parseSesamePosition('%J NaN +54.34895\n'), null);
  assert.equal(parseSesamePosition('%J 400 +54.34895\n'), null);
});
