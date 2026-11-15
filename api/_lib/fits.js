'use strict';
// Minimal FITS reader for SPHEREx L2 cutouts: headers, 2-D images (BITPIX -32/32) and
// the one-row WCS-WAVE binary table. Big-endian per the FITS standard.

const BLOCK = 2880;

function parseHeader(buf, start) {
  const cards = new Map();
  let pos = start;
  for (;;) {
    if (pos + 80 > buf.length) throw new Error('FITS header truncated');
    const card = buf.toString('latin1', pos, pos + 80);
    pos += 80;
    const key = card.slice(0, 8).trim();
    if (key === 'END') break;
    if (card[8] !== '=' || key === '' || key === 'COMMENT' || key === 'HISTORY') continue;
    let rest = card.slice(10);
    let value;
    const t = rest.trimStart();
    if (t.startsWith("'")) {
      let s = '';
      let i = rest.indexOf("'") + 1;
      while (i < rest.length) {
        if (rest[i] === "'") {
          if (rest[i + 1] === "'") { s += "'"; i += 2; continue; }
          break;
        }
        s += rest[i++];
      }
      value = s.trimEnd();
    } else {
      const raw = t.split('/')[0].trim();
      if (raw === 'T') value = true;
      else if (raw === 'F') value = false;
      else {
        const n = Number(raw.replace(/D/g, 'E'));
        value = Number.isFinite(n) ? n : raw;
      }
    }
    cards.set(key, value);
  }
  const end = Math.ceil(pos / BLOCK) * BLOCK;
  return { cards, dataStart: end };
}

function readFits(buf) {
  const hdus = [];
  let pos = 0;
  while (pos + BLOCK <= buf.length) {
    const { cards, dataStart } = parseHeader(buf, pos);
    const bitpix = cards.get('BITPIX');
    const naxis = cards.get('NAXIS') || 0;
    let n = naxis ? 1 : 0;
    for (let i = 1; i <= naxis; i++) n *= cards.get('NAXIS' + i);
    const bytes = (Math.abs(bitpix) / 8) * (cards.get('GCOUNT') || 1) * (n + (cards.get('PCOUNT') || 0));
    hdus.push({ name: String(cards.get('EXTNAME') || (hdus.length ? '' : 'PRIMARY')).trim(), cards, dataStart, bytes });
    pos = dataStart + Math.ceil(bytes / BLOCK) * BLOCK;
    if (bytes === 0 && hdus.length > 1 && pos >= buf.length) break;
  }
  return hdus;
}

function image(buf, hdu) {
  const w = hdu.cards.get('NAXIS1'), h = hdu.cards.get('NAXIS2'), bp = hdu.cards.get('BITPIX');
  const out = bp === -32 ? new Float32Array(w * h) : bp === 32 ? new Int32Array(w * h) : null;
  if (!out) throw new Error('Unsupported BITPIX ' + bp);
  const s = hdu.dataStart;
  for (let i = 0; i < w * h; i++) out[i] = bp === -32 ? buf.readFloatBE(s + 4 * i) : buf.readInt32BE(s + 4 * i);
  return { w, h, data: out };
}

// Read every column of row 0 of a binary table. Supports J (int32), E (float32), D (float64).
function tableRow(buf, hdu) {
  const nf = hdu.cards.get('TFIELDS');
  let off = hdu.dataStart;
  const cols = {};
  for (let i = 1; i <= nf; i++) {
    const form = String(hdu.cards.get('TFORM' + i)).trim();
    const m = /^(\d*)([JED])$/.exec(form);
    if (!m) throw new Error('Unsupported TFORM ' + form);
    const count = m[1] ? Number(m[1]) : 1;
    const size = { J: 4, E: 4, D: 8 }[m[2]];
    const arr = new Float64Array(count);
    for (let k = 0; k < count; k++) {
      const p = off + k * size;
      arr[k] = m[2] === 'J' ? buf.readInt32BE(p) : m[2] === 'E' ? buf.readFloatBE(p) : buf.readDoubleBE(p);
    }
    cols[String(hdu.cards.get('TTYPE' + i)).trim()] = { values: arr, dim: hdu.cards.get('TDIM' + i) };
    off += count * size;
  }
  return cols;
}

module.exports = { readFits, image, tableRow };
