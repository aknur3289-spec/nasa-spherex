'use strict';
function coords(q) {
  const ra = Number(q.ra), dec = Number(q.dec);
  if (!Number.isFinite(ra) || !Number.isFinite(dec) || dec < -90 || dec > 90) return null;
  return [((ra % 360) + 360) % 360, dec];
}
function send(res, status, body, cache) {
  res.statusCode = status;
  res.setHeader('Content-Type', 'application/json; charset=utf-8');
  res.setHeader('Cache-Control', cache || 'no-store');
  res.end(JSON.stringify(body));
}
function query(req) {
  return Object.fromEntries(new URL(req.url, 'http://x').searchParams);
}
module.exports = { coords, send, query };
