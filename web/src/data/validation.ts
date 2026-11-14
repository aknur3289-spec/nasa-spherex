import type { Field, FieldSummary } from '../contract.ts';

export class FieldError extends Error {}
const nonempty = (v: unknown): v is string => typeof v === 'string' && !!v.trim();
export const safeId = (v: unknown): v is string => nonempty(v) && /^[a-z0-9]+(?:[-_][a-z0-9]+)*$/.test(v);
export const safeAsset = (v: unknown): v is string => nonempty(v) && /^(?:[\w-]+\/)*[\w-]+\.(?:png|fits)$/i.test(v);
const finite = (v: unknown): v is number => typeof v === 'number' && Number.isFinite(v);
const positive = (v: unknown) => finite(v) && v > 0;
const natural = (v: unknown) => finite(v) && v >= 0 && Number.isInteger(v);
const utc = (v: unknown) => nonempty(v) && /^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,3})?Z$/.test(v) &&
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
    const { field_id, title, thumbnail, kind } = object(item);
    requireValue(safeId(field_id) && !ids.has(field_id) && nonempty(title) &&
      safeAsset(thumbnail) && /\.png$/i.test(thumbnail) && (kind === 'static' || kind === 'dial'), 'Invalid field summary.');
    ids.add(field_id);
  }
  return value as FieldSummary[];
}

export function validateField(value: unknown, id: string): Field {
  const f = object(value);
  requireValue(f.schema_version === '1.0', 'Unsupported field schema version.');
  requireValue(safeId(id) && f.field_id === id && nonempty(f.title) && nonempty(f.description) &&
    (f.kind === 'static' || f.kind === 'dial') && center(f.center) && positive(f.size_arcmin) &&
    positive(f.pixel_scale_arcsec), 'Invalid field metadata.');
  const p = object(f.provenance);
  requireValue(typeof p.synthetic === 'boolean' && typeof p.cached === 'boolean' &&
    [p.mission, p.archive, p.doi, p.pipeline_commit].every(nonempty) && utc(p.downloaded_utc) &&
    Array.isArray(p.collections) && p.collections.length && p.collections.every(nonempty), 'Invalid provenance.');
  requireValue(Array.isArray(f.frames) && Array.isArray(f.pairs), 'Invalid frame or pair list.');
  const ids = new Set<string>();
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
    ids.add(frame.id);
  }
  const has = (key: unknown) => typeof key === 'string' && ids.has(key);
  for (const item of f.pairs) {
    const { a, b, dt_days, dlambda_frac, trust } = object(item);
    requireValue(has(a) && has(b) && a !== b && finite(dt_days) && dt_days >= 0 &&
      finite(dlambda_frac) && dlambda_frac >= 0, 'Invalid pair or frame reference.');
    requireValue(trust === (dlambda_frac <= .02 ? 'high' : dlambda_frac <= .05 ? 'medium' : 'low'), 'Invalid pair trust.');
  }
  if (f.kind === 'dial' || f.dial !== undefined) {
    const d = object(f.dial);
    const truth = object(d.truth);
    requireValue(has(d.reference_frame) && nonempty(d.model) && positive(d.search_radius_px) &&
      positive(d.peak_distance_au) && positive(truth.distance_au) && nonempty(truth.source) &&
      safeId(d.negative_control_field) && Array.isArray(d.steps) && d.steps.length, 'Invalid dial metadata.');
    for (const item of d.steps) {
      const s = object(item);
      requireValue(has(s.frame) && positive(s.distance_au) && center(s.pred) && finite(s.snr) &&
        finite(s.offset_px) && s.offset_px >= 0, 'Invalid dial step.');
    }
  }
  return value as Field;
}
