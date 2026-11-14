import { FieldError, safeId, safeAsset, validateField, validateIndex } from './validation.ts';

export { FieldError };
const root = () => (import.meta.env?.BASE_URL ?? '/') + 'data/';
export function imageUrl(id: string, path: string) {
  if (!safeId(id) || !safeAsset(path)) throw new FieldError('Invalid image path.');
  return root() + id + '/' + path;
}
async function read(url: string, signal?: AbortSignal) {
  let response: Response;
  try {
    response = await fetch(url, { signal });
  } catch {
    throw new FieldError('Static data could not be reached.');
  }
  if (!response.ok) throw new FieldError('Static data request failed (HTTP ' + response.status + ').');
  try {
    return await response.json() as unknown;
  } catch {
    throw new FieldError('The data file contains invalid JSON.');
  }
}
export async function loadIndex(signal?: AbortSignal) {
  return validateIndex(await read(root() + 'index.json', signal));
}
export async function loadField(id: string, signal?: AbortSignal) {
  if (!safeId(id)) throw new FieldError('Invalid field ID.');
  return validateField(await read(root() + id + '/field.json', signal), id);
}
