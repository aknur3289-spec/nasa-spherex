import assert from 'node:assert/strict';
import test from 'node:test';
import { hipsUrls } from '../src/survey/hips.ts';

test('HiPS tries both direct CDS hosts before the site proxy', () => {
  assert.deepEqual(hipsUrls('D2', 'https://example.org'), [
    'https://alasky.cds.unistra.fr/SPHEREx/D2',
    'https://alaskybis.cds.unistra.fr/SPHEREx/D2',
    'https://example.org/hips/SPHEREx/D2',
  ]);
});
