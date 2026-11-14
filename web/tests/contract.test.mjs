import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import { FieldError, validateField } from '../src/data/validation.ts';
import { loadField, imageUrl } from '../src/data/loader.ts';

const fixture = JSON.parse(readFileSync(new URL('../public/data/demo/field.json', import.meta.url)));
test('validates demo provenance and the static fixture', () => {
  assert.equal(validateField(fixture, 'demo').provenance.synthetic, true);
});
test('validates dial metadata and rejects missing frame references', () => {
  const field = structuredClone(fixture);
  field.kind = 'dial';
  field.dial = {
    reference_frame: 'epoch-1', model: 'synthetic', search_radius_px: 8,
    steps: [{ distance_au: 500, frame: 'epoch-2', pred: field.center, snr: 4, offset_px: 1 }],
    peak_distance_au: 500, truth: { distance_au: 500, source: 'synthetic' },
    negative_control_field: 'control',
  };
  assert.equal(validateField(field, 'demo').dial.steps.length, 1);
  field.dial.steps[0].frame = 'missing';
  assert.throws(() => validateField(field, 'demo'), FieldError);
});
test('rejects invalid versions, missing metadata, URLs, paths and pair data', () => {
  const mutations = [
    field => field.schema_version = '2.0',
    field => delete field.provenance,
    field => delete field.frames[0].source_url,
    field => { field.provenance.synthetic = false; field.frames[0].source_url = 'http://example.invalid'; },
    field => field.frames[0].png = '../outside.png',
    field => field.pairs[0].b = 'missing',
    field => field.pairs[0].trust = 'low',
  ];
  for (const mutate of mutations) {
    const field = structuredClone(fixture);
    mutate(field);
    assert.throws(() => validateField(field, 'demo'), FieldError);
  }
  assert.throws(() => imageUrl('demo', '%2e%2e/a.png'), FieldError);
});
test('reports invalid IDs, missing files and malformed JSON', async t => {
  const fetch = t.mock.method(globalThis, 'fetch', async () => new Response('', { status: 404 }));
  await assert.rejects(loadField('../demo'), /Invalid field ID/);
  assert.equal(fetch.mock.callCount(), 0);
  await assert.rejects(loadField('demo'), /HTTP 404/);
  fetch.mock.mockImplementation(async () => new Response('invalid JSON'));
  await assert.rejects(loadField('demo'), /invalid JSON/);
});
