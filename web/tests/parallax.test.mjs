import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import { predictRaDec, sepArcsec, sky2d } from "../src/survey/parallax.ts";

const blind = JSON.parse(fs.readFileSync(new URL("../public/data/blind/neptune_blind.json", import.meta.url)));
const rms = (r) => {
  const p = predictRaDec(blind.anchor, blind.december, r, blind.tilt_deg, blind.gm_sun_au3_day2, blind.obliquity_deg);
  const s = p.map((q, i) => sepArcsec(q.ra, q.dec, blind.december[i].ra_deg, blind.december[i].dec_deg) ** 2);
  return Math.sqrt(s.reduce((a, x) => a + x, 0) / s.length);
};

test("browser orbit model reproduces the Python blind fit", () => {
  assert.ok(Math.abs(rms(blind.fit.r_au) - blind.fit.rms_miss_arcsec) < 0.05);
  let best = [0, Infinity];
  for (let r = 20; r < 45; r += 0.01) { const m = rms(r); if (m < best[1]) best = [r, m]; }
  assert.ok(Math.abs(best[0] - blind.fit.r_au) < 0.05, `browser minimum ${best[0]}`);
});

test("toy sky: farther objects shift less, orbital motion matters", () => {
  const near = Math.abs(sky2d(30, 182.6).shiftArcsec), far = Math.abs(sky2d(500, 182.6).shiftArcsec);
  assert.ok(near > far * 5);
  const s = sky2d(30, 182.6);
  assert.ok(Math.abs(s.orbitalArcsec) > 0.1 * Math.abs(s.parallaxArcsec));
  assert.equal(sky2d(30, 182.6, false).orbitalArcsec, 0);
});
