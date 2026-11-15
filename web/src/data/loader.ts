import type { Field, TimelineEntry } from '../contract.ts';
import { FieldError, safeId, safeAsset, validateDifferencePng, validateField, validateIndex, validateMaskPng, validateTimeline } from './validation.ts';

export { FieldError };
const root = () => (import.meta.env?.BASE_URL ?? '/') + 'data/';
export function imageUrl(id: string, path: string) {
  if (!safeId(id) || !safeAsset(path)) throw new FieldError('Invalid image path.');
  return root() + id + '/' + path;
}
async function request(url: string, signal?: AbortSignal, optional = false) {
  let response: Response;
  try {
    response = await fetch(url, { signal });
  } catch {
    throw new FieldError('Static data could not be reached.');
  }
  if (optional && response.status === 404) return undefined;
  if (!response.ok) throw new FieldError('Static data request failed (HTTP ' + response.status + ').');
  return response;
}
async function json(response: Response) {
  try {
    return await response.json() as unknown;
  } catch {
    throw new FieldError('The data file contains invalid JSON.');
  }
}
export async function loadIndex(signal?: AbortSignal) {
  return validateIndex(await json((await request(root() + 'index.json', signal))!));
}
export async function loadField(id: string, signal?: AbortSignal): Promise<Field & { timeline?: TimelineEntry[] }> {
  if (!safeId(id)) throw new FieldError('Invalid field ID.');
  const field = validateField(await json((await request(root() + id + '/field.json', signal))!), id);
  const masks = field.frames.filter(frame => frame.mask_png);
  await Promise.all(masks.map(async frame => {
    const path = frame.mask_png!;
    const response = (await request(imageUrl(id, path), signal))!;
    validateMaskPng(await response.arrayBuffer(), frame.width_px, frame.height_px, path);
  }));
  if (field.color_png) {
    const response = (await request(imageUrl(id, field.color_png), signal))!;
    const first = field.frames[0];
    validateMaskPng(await response.arrayBuffer(), first?.width_px, first?.height_px, field.color_png);
  }
  if (field.schema_version === '1.0') return field;
  const differences = new Set(field.pairs.flatMap(pair => pair.diff_png ? [pair.diff_png] : []));
  const [timeline] = await Promise.all([
    loadTimeline(field, signal),
    ...Array.from(differences, async path => {
      const response = (await request(imageUrl(id, path), signal))!;
      validateDifferencePng(await response.arrayBuffer(), field, path);
    }),
  ]);
  return { ...field, timeline };
}

export async function loadTimeline(field: Field, signal?: AbortSignal): Promise<TimelineEntry[]> {
  if (field.schema_version === '1.1') {
    const response = await request(root() + field.field_id + '/timeline.json', signal, true);
    if (response) return validateTimeline(await json(response), field);
  }
  return field.frames.map(frame => ({ frame_id: frame.id, obs_time_utc: frame.obs_time_utc, mjd: frame.mjd }))
    .sort((a, b) => Date.parse(a.obs_time_utc) - Date.parse(b.obs_time_utc));
}

export async function fieldExists(id: string, signal?: AbortSignal): Promise<boolean | undefined> {
  if (!safeId(id)) return false;
  try {
    const response = await fetch(root() + id + '/field.json', { method: 'HEAD', signal });
    if (response.status === 404 || response.status === 410) return false;
    if (response.ok && response.headers.get('content-type')?.includes('text/html')) return false;
    return response.ok ? true : undefined;
  } catch {
    return undefined;
  }
}
