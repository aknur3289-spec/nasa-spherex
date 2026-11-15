import assert from 'node:assert/strict';
import test from 'node:test';
import { parseSesamePosition, resolveSesameName } from '../src/survey/sesame.ts';

const fixture = `#=A M101\n%J 210.80227 +54.34895\n%I M101\n`;

test('reads the position line from a Sesame response', () => {
  assert.deepEqual(parseSesamePosition(fixture), { ra: 210.80227, dec: 54.34895 });
  assert.deepEqual(parseSesamePosition('%J 359.64779 -1.63079\n'), { ra: 359.64779, dec: -1.63079 });
  assert.equal(parseSesamePosition('#=A Unknown\n'), null);
  assert.equal(parseSesamePosition('%J NaN +54.34895\n'), null);
  assert.equal(parseSesamePosition('%J 400 +54.34895\n'), null);
});

test('uses the local names without a network request', async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = () => { throw new Error('unexpected fetch'); };
  try {
    assert.deepEqual(await resolveSesameName('m 101'), { ra: 210.802, dec: 54.349 });
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('tries direct CDS, CfA, then proxy and stops at the first valid result', async () => {
  const originalFetch = globalThis.fetch;
  const urls = [];
  globalThis.fetch = async (url, options) => {
    urls.push(url);
    assert.ok(options.signal instanceof AbortSignal);
    if (urls.length === 1) return { ok: false };
    if (urls.length === 2) return { ok: true, text: async () => '#=A Missing\n' };
    return { ok: true, text: async () => '%J 12.5 -3.25\n' };
  };
  try {
    assert.deepEqual(await resolveSesameName('Unknown Star'), { ra: 12.5, dec: -3.25 });
    assert.deepEqual(urls, [
      'https://cds.unistra.fr/cgi-bin/nph-sesame/-oI/A?Unknown%20Star',
      'https://vizier.cfa.harvard.edu/viz-bin/nph-sesame/-oI/A?Unknown%20Star',
      '/sesame/-oI/A?Unknown%20Star',
    ]);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('stops after the first successful direct resolver', async () => {
  const originalFetch = globalThis.fetch;
  const urls = [];
  globalThis.fetch = async (url) => {
    urls.push(url);
    return { ok: true, text: async () => '%J 15.75 +2.5\n' };
  };
  try {
    assert.deepEqual(await resolveSesameName('another target'), { ra: 15.75, dec: 2.5 });
    assert.deepEqual(urls, ['https://cds.unistra.fr/cgi-bin/nph-sesame/-oI/A?another%20target']);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('reports failure only after every resolver fails', async () => {
  const originalFetch = globalThis.fetch;
  let attempts = 0;
  globalThis.fetch = async () => { attempts += 1; throw new Error('blocked'); };
  try {
    await assert.rejects(resolveSesameName('unlisted target'));
    assert.equal(attempts, 3);
  } finally {
    globalThis.fetch = originalFetch;
  }
});
