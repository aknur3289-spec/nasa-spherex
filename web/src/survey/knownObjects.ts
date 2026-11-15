import type { RaDec } from "./skyCoords";

// SIMBAD ICRS positions at J2000, rounded to 0.001 degree. Field centres come
// from the published SPHEREx field manifests. These are lookup targets, not detections.
type KnownObject = RaDec & { names: readonly string[] };

export const KNOWN_OBJECTS: readonly KnownObject[] = [
  { names: ["M101", "Pinwheel Galaxy", "M101 field"], ra: 210.802, dec: 54.349 },
  { names: ["M31", "Andromeda", "Andromeda Galaxy"], ra: 10.685, dec: 41.269 },
  { names: ["M42", "Orion Nebula", "Great Orion Nebula"], ra: 83.820, dec: -5.388 },
  { names: ["M45", "Pleiades", "Seven Sisters"], ra: 56.601, dec: 24.114 },
  { names: ["M1", "Crab Nebula"], ra: 83.633, dec: 22.018 },
  { names: ["M51", "Whirlpool Galaxy"], ra: 202.470, dec: 47.195 },
  { names: ["M81", "Bode's Galaxy"], ra: 148.888, dec: 69.065 },
  { names: ["M82", "Cigar Galaxy"], ra: 148.968, dec: 69.680 },
  { names: ["M104", "Sombrero Galaxy"], ra: 189.998, dec: -11.623 },
  { names: ["Vega"], ra: 279.235, dec: 38.784 },
  { names: ["Sirius"], ra: 101.287, dec: -16.716 },
  { names: ["Betelgeuse"], ra: 88.793, dec: 7.407 },
  { names: ["Rigel"], ra: 78.634, dec: -8.202 },
  { names: ["Polaris", "North Star"], ra: 37.955, dec: 89.264 },
  { names: ["Arcturus"], ra: 213.915, dec: 19.182 },
  { names: ["Antares"], ra: 247.352, dec: -26.432 },
  { names: ["Aldebaran"], ra: 68.980, dec: 16.509 },
  { names: ["Deneb"], ra: 310.358, dec: 45.280 },
  { names: ["Altair"], ra: 297.696, dec: 8.868 },
  { names: ["Capella"], ra: 79.172, dec: 45.998 },
  { names: ["Sgr A*", "Sgr A", "Galactic Center", "Galactic Centre"], ra: 266.417, dec: -29.008 },
  { names: ["LMC", "Large Magellanic Cloud"], ra: 80.894, dec: -69.756 },
  { names: ["SMC", "Small Magellanic Cloud"], ra: 13.158, dec: -72.800 },
  { names: ["Eta Carinae", "Eta Car"], ra: 161.265, dec: -59.684 },
  { names: ["Omega Centauri", "NGC 5139"], ra: 201.697, dec: -47.479 },
  { names: ["NEP", "North Ecliptic Pole", "NEP field"], ra: 270.000, dec: 66.561 },
  { names: ["ECL", "Ecliptic field", "Ecliptic test field", "Along the planets' path"], ra: 27.911, dec: 11.472 },
  { names: ["M33", "Triangulum Galaxy"], ra: 23.462, dec: 30.660 },
  { names: ["M13", "Hercules Cluster"], ra: 250.423, dec: 36.461 },
  { names: ["M57", "Ring Nebula"], ra: 283.396, dec: 33.029 },
];

const key = (name: string) => name.toLowerCase().replace(/\s+/g, "");
const aliases = new Map(KNOWN_OBJECTS.flatMap((object) =>
  object.names.map((name) => [key(name), { ra: object.ra, dec: object.dec }] as const),
));

export function resolveKnownObject(name: string): RaDec | null {
  return aliases.get(key(name.trim())) ?? null;
}
