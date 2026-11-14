import type { Field, FieldSummary, TimelineEntry } from '../contract.ts';

export class FieldError extends Error {}
const nonempty = (v: unknown): v is string => typeof v === 'string' && !!v.trim();
export const safeId = (v: unknown): v is string => nonempty(v) && /^[a-z0-9]+(?:[-_][a-z0-9]+)*$/.test(v);
export const safeAsset = (v: unknown): v is string => nonempty(v) && /^(?:[\w-]+\/)*[\w-]+\.(?:png|fits)$/i.test(v);
const finite = (v: unknown): v is number => typeof v === 'number' && Number.isFinite(v);
const positive = (v: unknown) => finite(v) && v > 0;
const natural = (v: unknown) => finite(v) && v >= 0 && Number.isInteger(v);
const pixelSize = (v: unknown) => natural(v) && Number(v) > 0 && Number(v) <= 0x7fffffff;
// ISO-8601 UTC; Python writes microseconds (6 digits), JS writes milliseconds (3).
const utc = (v: unknown) => nonempty(v) && /^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,9})?Z$/.test(v) &&
  Number.isFinite(Date.parse(v)) && new Date(v).toISOString().slice(0, 19) === v.slice(0, 19);

function requireValue(ok: unknown, message: string): asserts ok {
  if (!ok) throw new FieldError(message);
}
function object(v: unknown): Record<string, unknown> {
  requireValue(v && typeof v === 'object' && !Array.isArray(v), 'Expected a JSON object.');
  return v as Record<string, unknown>;
}
function center(value: unknown) {
  const { ra_deg: ra, dec_deg: dec } = object(value);
  return finite(ra) && ra >= 0 && ra < 360 && finite(dec) && Math.abs(dec) <= 90;
}
function source(value: unknown, synthetic: boolean) {
  if (!nonempty(value)) return false;
  try {
    const url = new URL(value);
    return url.protocol === 'https:' && !url.username && !url.password &&
      (synthetic ? url.hostname === 'example.invalid' : url.hostname !== 'example.invalid');
  } catch {
    return false;
  }
}

export function validateIndex(value: unknown): FieldSummary[] {
  requireValue(Array.isArray(value), 'Invalid field index.');
  const ids = new Set<string>();
  for (const item of value) {
    const { field_id, title, thumbnail, kind, thumbnail_px, n_frames, date_range, status, synthetic } = object(item);
    requireValue(safeId(field_id) && !ids.has(field_id) && nonempty(title) &&
      safeAsset(thumbnail) && /\.png$/i.test(thumbnail) && (kind === 'static' || kind === 'dial'), 'Invalid field summary.');
    if (thumbnail_px !== undefined) {
      const { width, height } = object(thumbnail_px);
      requireValue(pixelSize(width) && pixelSize(height), 'Invalid thumbnail dimensions.');
    }
    if (date_range !== undefined) {
      const { start_utc, end_utc } = object(date_range);
      requireValue(utc(start_utc) && utc(end_utc) && Date.parse(String(start_utc)) <= Date.parse(String(end_utc)), 'Invalid date range.');
    }
    requireValue((n_frames === undefined || natural(n_frames)) &&
      (status === undefined || status === 'ready' || status === 'pending') &&
      (synthetic === undefined || typeof synthetic === 'boolean'), 'Invalid optional field summary metadata.');
    ids.add(field_id);
  }
  return value as FieldSummary[];
}

export function validateField(value: unknown, id: string): Field {
  const f = object(value);
  requireValue(f.schema_version === '1.0' || f.schema_version === '1.1', 'Unsupported field schema version.');
  requireValue(safeId(id) && f.field_id === id && nonempty(f.title) && nonempty(f.description) &&
    (f.kind === 'static' || f.kind === 'dial') && center(f.center) && positive(f.size_arcmin) &&
    positive(f.pixel_scale_arcsec), 'Invalid field metadata.');
  const p = object(f.provenance);
  requireValue(typeof p.synthetic === 'boolean' && typeof p.cached === 'boolean' &&
    [p.mission, p.archive, p.doi, p.pipeline_commit].every(nonempty) && utc(p.downloaded_utc) &&
    Array.isArray(p.collections) && p.collections.length && p.collections.every(nonempty), 'Invalid provenance.');
  requireValue(Array.isArray(f.frames) && Array.isArray(f.pairs), 'Invalid frame or pair list.');
  const ids = new Set<string>();
  let dimensions: string | undefined;
  for (const item of f.frames) {
    const frame = object(item);
    const stretch = object(frame.stretch);
    requireValue(safeId(frame.id) && !ids.has(frame.id) && safeAsset(frame.png) && /\.png$/i.test(frame.png) &&
      (frame.fits === undefined || (safeAsset(frame.fits) && /\.fits$/i.test(frame.fits))) &&
      utc(frame.obs_time_utc) && finite(frame.mjd) && natural(frame.survey_pass) && natural(frame.detector) &&
      (frame.band === undefined || nonempty(frame.band)) && positive(frame.wavelength_um) && center(frame.center) &&
      finite(frame.bad_pixel_fraction) && frame.bad_pixel_fraction >= 0 && frame.bad_pixel_fraction <= 1 &&
      stretch.kind === 'asinh' && finite(stretch.lo) && finite(stretch.hi) && stretch.lo < stretch.hi &&
      nonempty(stretch.unit) && source(frame.source_url, p.synthetic) && nonempty(frame.obs_id) &&
      nonempty(frame.processing_version), 'Invalid observation frame.');
    if (f.schema_version === '1.1') {
      const { width_px, height_px } = frame;
      requireValue(pixelSize(width_px) && pixelSize(height_px), 'Invalid frame dimensions.');
      const size = width_px + 'x' + height_px;
      // Dial crops come from different detectors and may differ by a pixel; only static fields feed difference images.
      requireValue(f.kind === 'dial' || dimensions === undefined || dimensions === size, 'Inconsistent field frame dimensions.');
      dimensions = size;
    }
    ids.add(frame.id);
  }
  const has = (key: unknown) => typeof key === 'string' && ids.has(key);
  for (const item of f.pairs) {
    const { a, b, dt_days, dlambda_frac, trust, diff_png } = object(item);
    requireValue(has(a) && has(b) && a !== b && finite(dt_days) && dt_days >= 0 &&
      finite(dlambda_frac) && dlambda_frac >= 0, 'Invalid pair or frame reference.');
    if (f.schema_version === '1.1' && diff_png !== undefined) {
      requireValue(safeAsset(diff_png) && /\.png$/i.test(diff_png), 'Invalid difference PNG path.');
    }
    requireValue(trust === (dlambda_frac <= .02 ? 'high' : dlambda_frac <= .05 ? 'medium' : 'low'), 'Invalid pair trust.');
  }
  if (f.kind === 'dial' || f.dial !== undefined) {
    const d = object(f.dial);
    const truth = object(d.truth);
    requireValue(has(d.reference_frame) && nonempty(d.model) && positive(d.search_radius_px) &&
      positive(d.peak_distance_au) && positive(truth.distance_au) && nonempty(truth.source) &&
      (d.negative_control_field === undefined || d.negative_control_field === null || safeId(d.negative_control_field)) && Array.isArray(d.steps) && d.steps.length, 'Invalid dial metadata.');
    requireValue((d.ref_obs_id === undefined || nonempty(d.ref_obs_id)) &&
      (d.target_obs_id === undefined || nonempty(d.target_obs_id)) &&
      (d.truth_au === undefined || positive(d.truth_au)) &&
      (d.measured_au === undefined || positive(d.measured_au)) &&
      (d.note === undefined || nonempty(d.note)), 'Invalid optional dial metadata.');
    let inFrame = 0;
    for (const item of d.steps) {
      const s = object(item);
      requireValue(s.outside_frame === undefined || typeof s.outside_frame === 'boolean', 'Invalid dial step outside_frame flag.');
      requireValue(positive(s.distance_au) && center(s.pred), 'Invalid dial step.');
      if (s.outside_frame === true) {
        // The predicted point is off every detector: no frame, signal or offset can exist.
        requireValue(s.frame === null && s.snr === null && s.offset_px === null, 'Outside-frame dial step must have null frame, snr and offset_px.');
      } else {
        requireValue(has(s.frame) && finite(s.snr) && finite(s.offset_px) && s.offset_px >= 0, 'Invalid dial step.');
        inFrame++;
      }
    }
    requireValue(inFrame > 0, 'Dial needs at least one step inside a frame.');
  }
  return value as Field;
}

export function validateTimeline(value: unknown, field: Field): TimelineEntry[] {
  requireValue(Array.isArray(value), 'Invalid timeline.');
  const frames = new Map(field.frames.map(frame => [frame.id, frame]));
  const seen = new Set<string>();
  let previous = -Infinity;
  for (const item of value) {
    const { frame_id, obs_time_utc, mjd } = object(item);
    const frame = typeof frame_id === 'string' ? frames.get(frame_id) : undefined;
    requireValue(frame && !seen.has(frame.id), 'Unknown or duplicate timeline frame_id.');
    requireValue(utc(obs_time_utc) && finite(mjd) &&
      Date.parse(String(obs_time_utc)) === Date.parse(frame.obs_time_utc) && mjd === frame.mjd,
      'Timeline metadata does not match frame.');
    const time = Date.parse(frame.obs_time_utc);
    requireValue(time >= previous, 'Timeline is not sorted by observation time.');
    previous = time;
    seen.add(frame.id);
  }
  requireValue(seen.size === frames.size, 'Timeline must list every frame.');
  return value as TimelineEntry[];
}

export function validateDifferencePng(bytes: ArrayBuffer, field: Extract<Field, { schema_version: '1.1' }>, path: string) {
  const view = new DataView(bytes);
  requireValue(view.byteLength >= 33 && view.getUint32(0) === 0x89504e47 &&
    view.getUint32(4) === 0x0d0a1a0a && view.getUint32(8) === 13 &&
    view.getUint32(12) === 0x49484452, 'Invalid difference PNG header: ' + path);
  const frame = field.frames[0];
  requireValue(frame && view.getUint32(16) === frame.width_px &&
    view.getUint32(20) === frame.height_px, 'Inconsistent difference PNG dimensions: ' + path);
}
