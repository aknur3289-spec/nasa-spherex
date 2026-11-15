import type { RaDec } from "./skyCoords";

export function parseSesamePosition(text: string): RaDec | null {
  const line = text.split(/\r?\n/).find((part) => /^%J\s/.test(part));
  if (!line) return null;
  const match = /^%J\s+([+-]?\d+(?:\.\d+)?)\s+([+-]?\d+(?:\.\d+)?)(?:\s|$)/.exec(line);
  if (!match) return null;
  const ra = Number(match[1]);
  const dec = Number(match[2]);
  return Number.isFinite(ra) && Number.isFinite(dec) && ra >= 0 && ra < 360 && Math.abs(dec) <= 90
    ? { ra, dec }
    : null;
}

export async function resolveSesameName(name: string): Promise<RaDec> {
  const response = await fetch(`/sesame/-oI/A?${encodeURIComponent(name)}`);
  if (!response.ok) throw new Error("Sesame request failed");
  const position = parseSesamePosition(await response.text());
  if (!position) throw new Error("Sesame position missing");
  return position;
}
