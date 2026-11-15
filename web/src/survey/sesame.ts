import type { RaDec } from "./skyCoords";
import { resolveKnownObject } from "./knownObjects.ts";

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
  const known = resolveKnownObject(name);
  if (known) return known;
  const query = encodeURIComponent(name.trim());
  const sources = [
    `https://cds.unistra.fr/cgi-bin/nph-sesame/-oI/A?${query}`,
    `https://vizier.cfa.harvard.edu/viz-bin/nph-sesame/-oI/A?${query}`,
    `/sesame/-oI/A?${query}`,
  ];
  for (const url of sources) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 6000);
    try {
      const response = await fetch(url, { signal: controller.signal });
      if (!response.ok) continue;
      const position = parseSesamePosition(await response.text());
      if (position) return position;
    } catch {
      // Try the next independent resolver.
    } finally {
      clearTimeout(timeout);
    }
  }
  throw new Error("Name not found by any Sesame resolver");
}
