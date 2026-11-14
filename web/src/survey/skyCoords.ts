/** Coordinate helpers for the whole-sky search. Pure functions, unit-tested. */

export type RaDec = { ra: number; dec: number };

const num = (s: string) => Number(s.replace("−", "-"));

/**
 * Parse "210.80 54.35", "210.80, +54.35", "14h03m13s +54°20′", "14:03:13 +54:20:00"
 * or "14 03 13 +54 20 00". Returns null for anything else (e.g. an object name).
 */
export function parseCoords(input: string): RaDec | null {
  const s = input.trim().replace(/−/g, "-").replace(/[’']/g, "′").replace(/["”]/g, "″");
  if (!s) return null;

  const deg = /^([+-]?\d+(?:\.\d+)?)\s*[,\s]\s*([+-]?\d+(?:\.\d+)?)$/.exec(s);
  if (deg) {
    const ra = num(deg[1]);
    const dec = num(deg[2]);
    return ra >= 0 && ra < 360 && Math.abs(dec) <= 90 ? { ra, dec } : null;
  }

  const sex =
    /^(\d{1,2})\s*[h:\s]\s*(\d{1,2})\s*[m:\s]\s*(\d{1,2}(?:\.\d+)?)\s*s?\s*,?\s*([+-]?)\s*(\d{1,2})\s*[°d:\s]\s*(\d{1,2})\s*[′m:\s]?\s*(?:(\d{1,2}(?:\.\d+)?)\s*[″s]?)?$/.exec(
      s,
    );
  if (sex) {
    const [h, m, sec] = [num(sex[1]), num(sex[2]), num(sex[3])];
    const [d, dm, ds] = [num(sex[5]), num(sex[6]), sex[7] ? num(sex[7]) : 0];
    if (h > 23 || m > 59 || sec >= 60 || d > 90 || dm > 59 || ds >= 60) return null;
    const ra = (h + m / 60 + sec / 3600) * 15;
    const dec = (sex[4] === "-" ? -1 : 1) * (d + dm / 60 + ds / 3600);
    return Math.abs(dec) <= 90 ? { ra, dec } : null;
  }
  return null;
}

const rad = Math.PI / 180;

/** Great-circle separation in degrees. */
export function separationDeg(a: RaDec, b: RaDec): number {
  const s =
    Math.sin(((b.dec - a.dec) * rad) / 2) ** 2 +
    Math.cos(a.dec * rad) * Math.cos(b.dec * rad) * Math.sin(((b.ra - a.ra) * rad) / 2) ** 2;
  return (2 * Math.asin(Math.min(1, Math.sqrt(s)))) / rad;
}

/** Is the point inside a square field of `sizeArcmin` centred on `center` (tangent-plane approximation)? */
export function insideSquare(p: RaDec, center: RaDec, sizeArcmin: number): boolean {
  const half = sizeArcmin / 120;
  let dra = p.ra - center.ra;
  dra = ((dra + 540) % 360) - 180;
  return Math.abs(dra * Math.cos(center.dec * rad)) <= half && Math.abs(p.dec - center.dec) <= half;
}

/** Corners of an RA/Dec-aligned square, for drawing the footprint. */
export function squareCorners(center: RaDec, sizeArcmin: number): [number, number][] {
  const half = sizeArcmin / 120;
  const dra = half / Math.max(0.01, Math.cos(center.dec * rad));
  return [
    [center.ra - dra, center.dec - half],
    [center.ra + dra, center.dec - half],
    [center.ra + dra, center.dec + half],
    [center.ra - dra, center.dec + half],
  ].map(([r, d]) => [((r % 360) + 360) % 360, d] as [number, number]);
}

export function formatSep(deg: number): string {
  if (deg < 1 / 60) return `${(deg * 3600).toFixed(0)}″`;
  if (deg < 1) return `${(deg * 60).toFixed(1)}′`;
  return `${deg.toFixed(deg < 10 ? 1 : 0)}°`;
}
