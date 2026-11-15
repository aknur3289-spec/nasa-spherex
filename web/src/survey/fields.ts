import type { FieldSummary, Frame, Pair } from "../contract";

export const FRIENDLY: Record<string, { name: string; short: string; text: string }> = {
  ecl: {
    name: "Along the planets' path",
    short: "Ecliptic field",
    text: "A patch of the ecliptic, the band of sky where the Sun, Moon and planets travel. The best place to look for things that move.",
  },
  nep: {
    name: "North Ecliptic Pole",
    short: "NEP",
    text: "SPHEREx passes over this spot more often than anywhere else, so it has the most repeat images.",
  },
  m101: {
    name: "Pinwheel Galaxy (M101)",
    short: "M101",
    text: "A large spiral galaxy. Nothing here should move, so it is a good check that the images line up.",
  },
  "neptune-track": {
    name: "Neptune moving against fixed stars",
    short: "Neptune track",
    text: "Watch known Neptune move across a fixed patch of sky in real SPHEREx images.",
  },
};

export const friendly = (item?: { field_id: string; title: string } | FieldSummary) =>
  item ? FRIENDLY[item.field_id] ?? { name: item.title, short: item.title, text: "" } : { name: "Sky Explorer", short: "", text: "" };

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
export const niceDate = (iso: string) => {
  const [y, m, d] = iso.slice(0, 10).split("-").map(Number);
  return `${d} ${MONTHS[m - 1]} ${y}`;
};

export const fmtRa = (deg: number) => {
  const h = ((deg % 360) + 360) % 360 / 15;
  const hh = Math.floor(h);
  const mm = Math.floor((h - hh) * 60);
  const ss = ((h - hh) * 60 - mm) * 60;
  return `${String(hh).padStart(2, "0")}h ${String(mm).padStart(2, "0")}m ${ss.toFixed(0).padStart(2, "0")}s`;
};
export const fmtDec = (deg: number) => {
  const s = deg < 0 ? "−" : "+";
  const a = Math.abs(deg);
  const d = Math.floor(a);
  const m = Math.floor((a - d) * 60);
  return `${s}${String(d).padStart(2, "0")}° ${String(m).padStart(2, "0")}′`;
};

export type Trust = "high" | "medium" | "low";

/** Relative wavelength difference between two frames. */
export const dLambda = (a: Frame, b: Frame) =>
  Math.abs(a.wavelength_um - b.wavelength_um) / ((a.wavelength_um + b.wavelength_um) / 2);

/**
 * Trust for any two frames. Documented pairs keep the pipeline's verdict.
 * For other pairs we use the same idea: the closer the wavelengths, the safer the comparison.
 */
export function pairTrust(a: Frame, b: Frame, pairs: Pair[]): { trust: Trust; documented: boolean; dl: number } {
  const doc = pairs.find((p) => (p.a === a.id && p.b === b.id) || (p.a === b.id && p.b === a.id));
  const dl = doc?.dlambda_frac ?? dLambda(a, b);
  if (doc) return { trust: doc.trust, documented: true, dl };
  return { trust: dl <= 0.02 ? "high" : dl <= 0.1 ? "medium" : "low", documented: false, dl };
}

export const daysApart = (a: Frame, b: Frame) => Math.abs(b.mjd - a.mjd);
