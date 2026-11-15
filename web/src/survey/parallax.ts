/**
 * Parallax physics, computed live in the browser.
 *
 * 1. `sky2d`: a toy Solar System in the ecliptic plane (Earth and the object on circular orbits)
 *    used by the simulator and the game. Same geometry SPHEREx uses: the object starts at
 *    quadrature (90° from the Sun as seen from Earth).
 * 2. `predictRaDec`: the circular-orbit model used on real SPHEREx detections (port of
 *    `predict()` in poc/blind_mover.py). Earth positions come precomputed in the data file.
 */

export const PX_ARCSEC = 6.15; // SPHEREx pixel
export const YEAR_DAYS = 365.25;
const RAD2ARCSEC = 206264.806;

export type Vec2 = { x: number; y: number };
export type Sky2D = {
  earth0: Vec2;
  earth1: Vec2;
  obj0: Vec2;
  obj1: Vec2;
  /** apparent shift on the sky between the two images, arcsec (positive = eastward) */
  shiftArcsec: number;
  /** shift if the object stood still (parallax only), arcsec */
  parallaxArcsec: number;
  /** orbital-motion part = shift − parallax, arcsec */
  orbitalArcsec: number;
};

const wrap = (a: number) => Math.atan2(Math.sin(a), Math.cos(a));
const lon = (from: Vec2, to: Vec2) => Math.atan2(to.y - from.y, to.x - from.x);

/** Object at heliocentric distance d (AU), observed twice, `days` apart. */
export function sky2d(d: number, days: number, orbitalMotion = true): Sky2D {
  const r = Math.max(d, 1.0001);
  const earth0 = { x: 1, y: 0 };
  const thE = (2 * Math.PI * days) / YEAR_DAYS;
  const earth1 = { x: Math.cos(thE), y: Math.sin(thE) };
  const s = Math.sqrt(r * r - 1); // object at quadrature: perpendicular to the Sun line seen from Earth
  const obj0 = { x: 1, y: s };
  const th0 = Math.atan2(obj0.y, obj0.x);
  const n = (2 * Math.PI) / (YEAR_DAYS * Math.pow(r, 1.5));
  const th1 = th0 + (orbitalMotion ? n * days : 0);
  const obj1 = { x: r * Math.cos(th1), y: r * Math.sin(th1) };
  const still = { x: obj0.x, y: obj0.y };
  const shift = wrap(lon(earth1, obj1) - lon(earth0, obj0)) * RAD2ARCSEC;
  const parallax = wrap(lon(earth1, still) - lon(earth0, obj0)) * RAD2ARCSEC;
  return { earth0, earth1, obj0, obj1, shiftArcsec: shift, parallaxArcsec: parallax, orbitalArcsec: shift - parallax };
}

/** Log-scale slider helpers. */
export const logToValue = (t: number, lo: number, hi: number) => lo * Math.pow(hi / lo, t);
export const valueToLog = (v: number, lo: number, hi: number) => Math.log(v / lo) / Math.log(hi / lo);

/* ------------------------------------------------------------- real-data model */

type V3 = [number, number, number];
const dot = (a: V3, b: V3) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
const cross = (a: V3, b: V3): V3 => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
const scale = (a: V3, k: number): V3 => [a[0] * k, a[1] * k, a[2] * k];
const add = (a: V3, b: V3): V3 => [a[0] + b[0], a[1] + b[1], a[2] + b[2]];
const norm = (a: V3) => Math.sqrt(dot(a, a));
const unit = (raDeg: number, decDeg: number): V3 => {
  const ra = (raDeg * Math.PI) / 180, de = (decDeg * Math.PI) / 180;
  return [Math.cos(de) * Math.cos(ra), Math.cos(de) * Math.sin(ra), Math.sin(de)];
};

export type Anchor = { ra_deg: number; dec_deg: number; mjd: number; earth_helio_au: V3 };
export type Target = { mjd: number; earth_helio_au: V3 };

/** Predicted (ra, dec) in degrees at each target time for a circular orbit of radius r (AU). */
export function predictRaDec(anchor: Anchor, targets: Target[], r: number, tiltDeg: number, gm: number, oblDeg: number) {
  const eps = (oblDeg * Math.PI) / 180;
  const zEcl: V3 = [0, -Math.sin(eps), Math.cos(eps)];
  const E0 = anchor.earth_helio_au;
  const u = unit(anchor.ra_deg, anchor.dec_deg);
  const b = dot(u, E0);
  const disc = b * b - (dot(E0, E0) - r * r);
  if (disc < 0) return null;
  const P0 = add(E0, scale(u, -b + Math.sqrt(disc)));
  const p = scale(P0, 1 / norm(P0));
  let k = add(zEcl, scale(p, -dot(zEcl, p)));
  k = scale(k, 1 / norm(k));
  const a = (tiltDeg * Math.PI) / 180;
  k = add(scale(k, Math.cos(a)), scale(cross(p, k), Math.sin(a)));
  const n = Math.sqrt(gm / (r * r * r));
  const kxP = cross(k, P0);
  return targets.map((t) => {
    const th = n * (t.mjd - anchor.mjd);
    const P = add(scale(P0, Math.cos(th)), scale(kxP, Math.sin(th)));
    const g = add(P, scale(t.earth_helio_au, -1));
    const gn = norm(g);
    const ra = ((Math.atan2(g[1], g[0]) * 180) / Math.PI + 360) % 360;
    const dec = (Math.asin(g[2] / gn) * 180) / Math.PI;
    return { ra, dec };
  });
}

/** Angular separation in arcsec (small-angle safe haversine). */
export function sepArcsec(ra1: number, de1: number, ra2: number, de2: number) {
  const r = Math.PI / 180;
  const s =
    Math.sin(((de2 - de1) * r) / 2) ** 2 +
    Math.cos(de1 * r) * Math.cos(de2 * r) * Math.sin(((ra2 - ra1) * r) / 2) ** 2;
  return 2 * Math.asin(Math.min(1, Math.sqrt(s))) * RAD2ARCSEC;
}

/** Tangent-plane offsets (arcsec) of a point from a centre; x grows to the east. */
export function offsetArcsec(ra: number, dec: number, ra0: number, dec0: number) {
  const r = Math.PI / 180;
  let dra = ra - ra0;
  if (dra > 180) dra -= 360;
  if (dra < -180) dra += 360;
  return { x: dra * Math.cos(dec0 * r) * 3600, y: (dec - dec0) * 3600 };
}
