'use strict';
// GET /api/sky-frame?url=<SPHEREx L2 file>&ra=&dec=
// Downloads a cutout from IRSA, masks bad pixels (Science's BAD_BITS), subtracts zodiacal light,
// reprojects to a north-up 99×99 grid at 6.15″/px and returns the floats plus the wavelength
// at the target pixel (WAVE-TAB lookup). No values are invented: masked pixels stay NaN.
const { fetchCutout } = require('./_lib/irsa.js');
const { processCutout } = require('./_lib/frame.js');
const { coords, send, query } = require('./_lib/http.js');

module.exports = async (req, res) => {
  const q = query(req);
  const c = coords(q);
  if (!c || !q.url) return send(res, 400, { error: 'url, ra and dec are required' });
  const [ra, dec] = c.map(v => Math.round(v * 1e5) / 1e5);
  let source;
  try {
    const { buf, url } = await fetchCutout(q.url, ra, dec, 0.24);
    source = url;
    const f = processCutout(buf, ra, dec);
    const values = Buffer.from(f.values.buffer, f.values.byteOffset, f.values.byteLength).toString('base64');
    send(res, 200, { ...f, values, encoding: 'float32-le-base64', source_url: url, file_url: q.url },
      'public, s-maxage=31536000, immutable');
  } catch (e) {
    const msg = String(e.message || e);
    send(res, /Not a SPHEREx/.test(msg) ? 400 : 503, { error: msg, source_url: source, retry: !/Not a SPHEREx/.test(msg) });
  }
};
