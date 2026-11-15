'use strict';
// JPL Horizons ephemeris (geocentric; SPHEREx is in low Earth orbit, a few arcseconds of parallax at most).
const API = 'https://ssd.jpl.nasa.gov/api/horizons.api';

// Common names → Horizons COMMAND. Small bodies use "<number>;" so Horizons does not ask to disambiguate.
const NAMES = {
  mercury: '199', venus: '299', mars: '499', jupiter: '599', saturn: '699', uranus: '799', neptune: '899', pluto: '999',
  ceres: '1;', pallas: '2;', juno: '3;', vesta: '4;', astraea: '5;', hebe: '6;', iris: '7;', flora: '8;', metis: '9;', hygiea: '10;',
  eros: '433;', psyche: '16;', eunomia: '15;', europa: '52;', davida: '511;', interamnia: '704;',
};

function command(name) {
  const key = String(name).trim().toLowerCase();
  if (NAMES[key]) return NAMES[key];
  if (/^\d+$/.test(key)) return `${key};`;            // asteroid number
  return `${String(name).trim()};`;                    // small-body name/designation
}

function parseCsv(result) {
  const lines = result.split('\n');
  const soe = lines.findIndex((l) => l.startsWith('$$SOE'));
  const eoe = lines.findIndex((l) => l.startsWith('$$EOE'));
  if (soe < 0 || eoe < 0) {
    const msg = (result.match(/(No matches found|Multiple major-bodies match|Matching small-bodies|Cannot find)[^\n]*/) || [])[0];
    throw new Error(msg || 'Horizons returned no ephemeris');
  }
  const header = lines.slice(0, soe).reverse().find((l) => l.includes('R.A.') || l.includes('Date__'));
  const cols = header.split(',').map((c) => c.trim());
  const idx = (re) => cols.findIndex((c) => re.test(c));
  const iRa = idx(/^R\.A\./), iDec = idx(/^DEC/), iDelta = idx(/^delta$/), iSot = idx(/^S-O-T$/), iDate = idx(/^Date/);
  const rows = [];
  for (const line of lines.slice(soe + 1, eoe)) {
    const f = line.split(',').map((x) => x.trim());
    const ra = Number(f[iRa]), dec = Number(f[iDec]);
    if (!Number.isFinite(ra) || !Number.isFinite(dec)) continue;
    rows.push({ date: f[iDate], ra, dec, delta_au: Number(f[iDelta]), elong_deg: iSot >= 0 ? Number(f[iSot]) : NaN });
  }
  const target = (result.match(/Target body name:\s*([^{(\n]+)/) || [])[1];
  return { rows, target: target ? target.trim() : undefined };
}

async function ephemeris(name, start, stop, step) {
  const q = new URLSearchParams({
    format: 'json', COMMAND: `'${command(name)}'`, EPHEM_TYPE: 'OBSERVER', CENTER: "'500@399'",
    START_TIME: `'${start}'`, STOP_TIME: `'${stop}'`, STEP_SIZE: `'${step}'`, QUANTITIES: "'1,20,23'",
    ANG_FORMAT: 'DEG', CSV_FORMAT: 'YES', OBJ_DATA: 'NO', MAKE_EPHEM: 'YES',
  });
  const r = await fetch(`${API}?${q}`, { signal: AbortSignal.timeout(25000) });
  if (!r.ok) throw new Error('JPL Horizons HTTP ' + r.status);
  const j = await r.json();
  if (j.error) throw new Error('JPL Horizons: ' + j.error);
  return parseCsv(j.result || '');
}

// Calendar date "2025-Jun-16 00:00" → MJD.
const MON = { Jan: 0, Feb: 1, Mar: 2, Apr: 3, May: 4, Jun: 5, Jul: 6, Aug: 7, Sep: 8, Oct: 9, Nov: 10, Dec: 11 };
function dateToMjd(s) {
  const m = /(\d{4})-(\w{3})-(\d{2})(?:\s+(\d{2}):(\d{2}))?/.exec(s);
  if (!m) return NaN;
  const t = Date.UTC(+m[1], MON[m[2]], +m[3], +(m[4] || 0), +(m[5] || 0));
  return t / 86400000 + 40587;
}

module.exports = { ephemeris, parseCsv, dateToMjd, command };
