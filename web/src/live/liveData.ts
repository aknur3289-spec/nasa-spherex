import type { Field, Frame, Pair } from "../contract";

/** One exposure listed by /api/sky-frames. */
export type Exposure = { file_url: string; obs_id: string; detector: number; mjd: number; collection: string };
/** One processed frame returned by /api/sky-frame. */
export type LiveFrame = {
  width: number; height: number; values: string; encoding: string;
  wavelength_um: number; bandwidth_um: number; bad_pixel_fraction: number; center_inside: boolean;
  obs_id: string; detector: number; mjd: number; obs_time_utc: string; source_url: string; file_url: string;
};

export const MAX_FRAMES = 48;
const HONEST_DL = 0.02, MEDIUM_DL = 0.05, MIN_DT = 150;

export async function listExposures(ra: number, dec: number, signal?: AbortSignal): Promise<Exposure[]> {
  const r = await fetch(`/api/sky-frames?ra=${ra}&dec=${dec}`, { signal });
  const body = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(body.error || `IRSA search failed (HTTP ${r.status})`);
  return body.exposures as Exposure[];
}

/** Short-wave detectors (sharper), spread evenly in time so pairs span months. */
export function pickExposures(all: Exposure[], max = MAX_FRAMES): Exposure[] {
  const swir = all.filter((e) => e.detector <= 3);
  const pool = swir.length >= 12 ? swir : all;
  if (pool.length <= max) return pool;
  const step = pool.length / max;
  return Array.from({ length: max }, (_, i) => pool[Math.floor(i * step)]);
}

export async function fetchFrame(e: Exposure, ra: number, dec: number, signal?: AbortSignal): Promise<LiveFrame> {
  const url = `/api/sky-frame?ra=${ra}&dec=${dec}&url=${encodeURIComponent(e.file_url)}`;
  let last: unknown;
  for (let i = 0; i < 2; i++) {
    try {
      const r = await fetch(url, { signal });
      const body = await r.json();
      if (r.ok) return body as LiveFrame;
      last = new Error(body.error || `HTTP ${r.status}`);
    } catch (err) {
      if (signal?.aborted) throw err;
      last = err;
    }
  }
  throw last;
}

export function decode(f: LiveFrame): Float32Array {
  const bin = atob(f.values);
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  return new Float32Array(bytes.buffer);
}

const percentile = (sorted: Float32Array, p: number) => sorted[Math.min(sorted.length - 1, Math.max(0, Math.round(p * (sorted.length - 1))))];

/**
 * Display rendering only: masked pixels are filled from their neighbours so the picture is readable
 * (the mask is reported separately as bad_pixel_fraction); asinh stretch per frame.
 */
export function renderPng(f: LiveFrame): { src: string; lo: number; hi: number } {
  const { width: w, height: h } = f;
  const v = decode(f).slice();
  for (let pass = 0; pass < 10; pass++) {
    let missing = 0;
    const next = v.slice();
    for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
      const i = y * w + x;
      if (Number.isFinite(v[i])) continue;
      let s = 0, n = 0;
      for (let dy = -1; dy <= 1; dy++) for (let dx = -1; dx <= 1; dx++) {
        const xx = x + dx, yy = y + dy;
        if (xx < 0 || yy < 0 || xx >= w || yy >= h) continue;
        const u = v[yy * w + xx];
        if (Number.isFinite(u)) { s += u; n++; }
      }
      if (n >= 2) next[i] = s / n; else missing++;
    }
    v.set(next);
    if (!missing) break;
  }
  const finite = v.filter(Number.isFinite).sort();
  const lo = finite.length ? percentile(finite, 0.02) : 0;
  const hi = finite.length ? percentile(finite, 0.997) : 1;
  const canvas = document.createElement("canvas");
  canvas.width = w; canvas.height = h;
  const ctx = canvas.getContext("2d")!;
  const img = ctx.createImageData(w, h);
  const k = 8, norm = Math.asinh(k);
  for (let i = 0; i < w * h; i++) {
    const t = Number.isFinite(v[i]) ? Math.min(1, Math.max(0, (v[i] - lo) / (hi - lo || 1))) : 0;
    const g = Math.round((Math.asinh(t * k) / norm) * 255);
    img.data[4 * i] = img.data[4 * i + 1] = img.data[4 * i + 2] = g;
    img.data[4 * i + 3] = 255;
  }
  ctx.putImageData(img, 0, 0);
  return { src: canvas.toDataURL("image/png"), lo, hi };
}

/** Same rules as the offline pipeline: honest = Δλ/λ ≤ 2 % and Δt ≥ 150 days. */
export function livePairs(frames: Frame[]): Pair[] {
  const all: Pair[] = [];
  for (let i = 0; i < frames.length; i++) for (let j = i + 1; j < frames.length; j++) {
    const a = frames[i], b = frames[j];
    const dt = Math.abs(b.mjd - a.mjd);
    if (dt < MIN_DT) continue;
    const dl = Math.abs(a.wavelength_um - b.wavelength_um) / ((a.wavelength_um + b.wavelength_um) / 2);
    const trust = dl <= HONEST_DL ? "high" : dl <= MEDIUM_DL ? "medium" : "low";
    const [x, y] = a.mjd <= b.mjd ? [a, b] : [b, a];
    all.push({ a: x.id, b: y.id, dlambda_frac: dl, dt_days: dt, trust });
  }
  const used = new Set<string>();
  const pick = (t: Pair["trust"], n: number, order: (p: Pair, q: Pair) => number) =>
    all.filter((p) => p.trust === t).sort(order).filter((p) => {
      if (used.has(p.a + p.b)) return false;
      used.add(p.a + p.b);
      return true;
    }).slice(0, n);
  return [
    ...pick("high", 12, (p, q) => p.dlambda_frac - q.dlambda_frac || q.dt_days - p.dt_days),
    ...pick("medium", 6, (p, q) => p.dlambda_frac - q.dlambda_frac),
    ...pick("low", 6, (p, q) => q.dlambda_frac - p.dlambda_frac),
  ];
}

export function buildField(ra: number, dec: number, label: string, frames: (LiveFrame & { src: string; lo: number; hi: number })[]): Field {
  const sorted = [...frames].sort((a, b) => a.mjd - b.mjd);
  const out = sorted.map((f, i) => ({
    id: `f${String(i + 1).padStart(3, "0")}`,
    png: f.src,
    width_px: f.width, height_px: f.height,
    obs_time_utc: f.obs_time_utc, mjd: f.mjd, survey_pass: 1, detector: f.detector,
    band: `SPHEREx-D${f.detector}`, wavelength_um: f.wavelength_um,
    center: { ra_deg: ra, dec_deg: dec }, bad_pixel_fraction: f.bad_pixel_fraction,
    stretch: { kind: "asinh" as const, lo: f.lo, hi: f.hi, unit: "MJy/sr" },
    source_url: f.source_url, obs_id: f.obs_id, processing_version: "",
  }));
  return {
    schema_version: "1.1",
    field_id: "live",
    kind: "static",
    title: label,
    description: "Live from NASA/IPAC IRSA: SPHEREx L2 cutouts at this position, masked with Science's BAD_BITS, zodiacal light subtracted, reprojected north-up at 6.15″/px.",
    center: { ra_deg: ra, dec_deg: dec },
    size_arcmin: 10, pixel_scale_arcsec: 6.15,
    frames: out,
    pairs: livePairs(out),
    provenance: {
      mission: "SPHEREx", archive: "NASA/IPAC IRSA", collections: ["spherex_dr1", "spherex_qr3"],
      doi: "IRSA SPHEREx", downloaded_utc: new Date().toISOString(), pipeline_commit: "live", cached: false, synthetic: false,
    },
  };
}
