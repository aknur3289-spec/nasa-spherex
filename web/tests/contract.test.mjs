import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import { FieldError, validateField } from '../src/data/validation.ts';
import { loadField, imageUrl } from '../src/data/loader.ts';

const fixture = JSON.parse(readFileSync(new URL('../public/data/fixture-static/field.json', import.meta.url)));
test('validates fixture-static provenance and the static fixture', () => {
  assert.equal(validateField(fixture, 'fixture-static').provenance.synthetic, true);
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
  assert.equal(validateField(field, 'fixture-static').dial.steps.length, 1);
  field.dial.steps[0].frame = 'missing';
  assert.throws(() => validateField(field, 'fixture-static'), FieldError);
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
    assert.throws(() => validateField(field, 'fixture-static'), FieldError);
  }
  assert.throws(() => imageUrl('fixture-static', '%2e%2e/a.png'), FieldError);
});
test('reports invalid IDs, missing files and malformed JSON', async t => {
  const fetch = t.mock.method(globalThis, 'fetch', async () => new Response('', { status: 404 }));
  await assert.rejects(loadField('../fixture-static'), /Invalid field ID/);
  assert.equal(fetch.mock.callCount(), 0);
  await assert.rejects(loadField('fixture-static'), /HTTP 404/);
  fetch.mock.mockImplementation(async () => new Response('invalid JSON'));
  await assert.rejects(loadField('fixture-static'), /invalid JSON/);
});

test('validates the published dial fixture and its logarithmic distance grid', () => {
  const fixture = JSON.parse(readFileSync(new URL('../public/data/fixture-dial/field.json', import.meta.url)));
  const field = validateField(fixture, 'fixture-dial');
  assert.equal(field.provenance.synthetic, true);
  assert.equal(field.dial.steps.length, 12);
  assert.equal(field.dial.peak_distance_au, 30);
  for (const [i, step] of field.dial.steps.entries()) {
    assert.ok(Math.abs(step.distance_au - 15 * (1000 / 15) ** (i / 11)) < 1e-6);
  }
});

test('loads a v1.1 field, its difference PNG and timeline, and rejects inconsistent sidecars', async t => {
  const png = readFileSync(new URL('../public/data/fixture-static/epoch-1.png', import.meta.url));
  const field = structuredClone(fixture);
  field.schema_version = '1.1';
  for (const frame of field.frames) Object.assign(frame, { width_px: 512, height_px: 512 });
  field.pairs[0].diff_png = 'diff/pair.png';
  const timeline = field.frames.map(frame => ({
    frame_id: frame.id, obs_time_utc: frame.obs_time_utc, mjd: frame.mjd,
  }));
  let timelineResponse = timeline;
  let image = png;
  t.mock.method(globalThis, 'fetch', async url => {
    if (url.endsWith('/field.json')) return Response.json(field);
    if (url.endsWith('/timeline.json')) return timelineResponse ? Response.json(timelineResponse) : new Response(null, { status: 404 });
    if (url.endsWith('/diff/pair.png')) return new Response(image);
    throw new Error('Unexpected URL ' + url);
  });
  const result = await loadField(field.field_id);
  assert.equal(result.schema_version, '1.1');
  assert.equal(result.pairs[0].diff_png, 'diff/pair.png');
  assert.deepEqual(result.timeline, timeline);

  image = Buffer.from(png);
  image.writeUInt32BE(511, 16);
  await assert.rejects(loadField(field.field_id), /Inconsistent difference PNG dimensions/);
  image = png;

  timelineResponse = [{ ...timeline[0], frame_id: 'unknown' }, ...timeline.slice(1)];
  await assert.rejects(loadField(field.field_id), /Unknown or duplicate timeline frame_id/);
  timelineResponse = undefined;
  field.frames.reverse();
  assert.deepEqual((await loadField(field.field_id)).timeline, timeline);

  field.frames[0].width_px = 511;
  assert.throws(() => validateField(field, field.field_id), /Inconsistent field frame dimensions/);
  delete field.frames[0].width_px;
  assert.throws(() => validateField(field, field.field_id), /Invalid frame dimensions/);
});
