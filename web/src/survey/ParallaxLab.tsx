import { useEffect, useMemo, useRef, useState } from "react";
import {
  PX_ARCSEC,
  logToValue,
  offsetArcsec,
  predictRaDec,
  sepArcsec,
  sky2d,
  valueToLog,
  type Anchor,
  type Target,
  type Vec2,
} from "./parallax";
import "./lab.css";

/* ------------------------------------------------------------------ helpers */

const D_MIN = 1.5;
const D_MAX = 1000;
const HALF_YEAR = 182.6;
/** Our injection test: one SPHEREx image recovers 50 % of point sources ~500× fainter than Neptune's peak. */
const ONE_IMAGE_LIMIT = 1 / 500;
const NEPTUNE_AU = 30;

const fmt = (v: number, digits = 1) =>
  Math.abs(v) >= 100 ? Math.round(v).toLocaleString("en") : v.toFixed(digits);
const fmtArc = (arcsec: number) => {
  const a = Math.abs(arcsec);
  if (a >= 3600) return `${fmt(a / 3600, 2)}°`;
  if (a >= 60) return `${fmt(a / 60, 1)}′`;
  return `${fmt(a, 1)}″`;
};
const nice = (v: number) => {
  const p = Math.pow(10, Math.floor(Math.log10(v)));
  return [1, 2, 5, 10].map((m) => m * p).find((x) => x >= v) ?? 10 * p;
};

function rng(seed: number) {
  let s = seed >>> 0;
  return () => ((s = (s * 1664525 + 1013904223) >>> 0) / 2 ** 32);
}
const STARS = (() => {
  const r = rng(42);
  return Array.from({ length: 70 }, () => ({ x: r(), y: r(), m: r() }));
})();

function DistanceSlider({
  value,
  onChange,
  min = D_MIN,
  max = D_MAX,
  label = "Distance from the Sun",
}: {
  value: number;
  onChange: (v: number) => void;
  min?: number;
  max?: number;
  label?: string;
}) {
  return (
    <label className="lab-slider">
      <span>{label}</span>
      <input
        type="range"
        min={0}
        max={1000}
        value={Math.round(valueToLog(value, min, max) * 1000)}
        onChange={(e) => onChange(logToValue(Number(e.target.value) / 1000, min, max))}
        aria-valuetext={`${fmt(value)} AU`}
      />
      <b>{fmt(value)} AU</b>
    </label>
  );
}

/* --------------------------------------------------------- 1. top-down view */

const C = 180;
const R_EARTH = 44;
const R_RING = 170;
const rDisp = (d: number) => R_EARTH + 14 + (R_RING - R_EARTH - 34) * Math.min(1, Math.log10(d) / 3);

function toDisp(p: Vec2, d?: number): Vec2 {
  const len = Math.hypot(p.x, p.y);
  const r = d === undefined ? R_EARTH * len : rDisp(d);
  return { x: C + (p.x / len) * r, y: C - (p.y / len) * r };
}
function rayToRing(from: Vec2, through: Vec2): Vec2 {
  const dx = through.x - from.x, dy = through.y - from.y;
  const fx = from.x - C, fy = from.y - C;
  const a = dx * dx + dy * dy, b = 2 * (fx * dx + fy * dy), c = fx * fx + fy * fy - R_RING * R_RING;
  const t = (-b + Math.sqrt(b * b - 4 * a * c)) / (2 * a);
  return { x: from.x + dx * t, y: from.y + dy * t };
}

function TopView({ d, days, orbit }: { d: number; days: number; orbit: boolean }) {
  const s = sky2d(d, days, orbit);
  const e0 = toDisp(s.earth0), e1 = toDisp(s.earth1);
  const o0 = toDisp(s.obj0, d), o1 = toDisp(s.obj1, d);
  const h0 = rayToRing(e0, o0), h1 = rayToRing(e1, o1);
  return (
    <svg viewBox="0 0 360 360" className="lab-top" role="img"
      aria-label={`Top view: Earth moves around the Sun between two images; lines of sight to the object hit the background stars at different places.`}>
      <circle cx={C} cy={C} r={R_RING} className="lab-ring" />
      <text x={C} y={C - R_RING - 2} className="lab-ringtext" textAnchor="middle">background stars (very far)</text>
      <circle cx={C} cy={C} r={R_EARTH} className="lab-orbit" />
      <circle cx={C} cy={C} r={rDisp(d)} className="lab-orbit obj" />
      <line x1={e0.x} y1={e0.y} x2={h0.x} y2={h0.y} className="lab-ray r0" />
      <line x1={e1.x} y1={e1.y} x2={h1.x} y2={h1.y} className="lab-ray r1" />
      <circle cx={C} cy={C} r={9} className="lab-sun" />
      <circle cx={e0.x} cy={e0.y} r={6} className="lab-earth e0" />
      <circle cx={e1.x} cy={e1.y} r={6} className="lab-earth e1" />
      <circle cx={o0.x} cy={o0.y} r={5} className="lab-obj o0" />
      <circle cx={o1.x} cy={o1.y} r={5} className="lab-obj o1" />
      <circle cx={h0.x} cy={h0.y} r={4} className="lab-hit h0" />
      <circle cx={h1.x} cy={h1.y} r={4} className="lab-hit h1" />
      {[[e0, "Earth, image 1"], [e1, "Earth, image 2"]].map(([e, t], i) => {
        const p = e as Vec2;
        const ux = (p.x - C) / R_EARTH, uy = (p.y - C) / R_EARTH;
        return <text key={i} x={C + ux * (R_EARTH + 26)} y={C + uy * (R_EARTH + 26) + 4 + (i ? 12 : 0)} textAnchor={ux < -0.3 ? "end" : ux > 0.3 ? "start" : "middle"} className="lab-label">{t as string}</text>;
      })}
      <text x={C} y={C + 24} textAnchor="middle" className="lab-label dim">Sun</text>
      <text x={8} y={352} className="lab-note">Distances compressed to fit. Angles and numbers are computed exactly.</text>
    </svg>
  );
}

/* --------------------------------------------------------- 2. sky view */

function SkyView({
  shift,
  predicted,
  blinkFrame,
  widthArcsec,
  labels = ["image 1", "image 2"],
  observedNoiseless = true,
}: {
  shift: number;
  predicted?: number;
  blinkFrame: 0 | 1 | null;
  widthArcsec: number;
  labels?: [string, string];
  observedNoiseless?: boolean;
}) {
  const Wpx = 360, Hpx = 190;
  const k = (Wpx - 40) / widthArcsec;
  const x1 = Wpx / 2 + (shift / 2) * k; // east to the left: image 1 on the right when it moves east
  const x2 = x1 - shift * k;
  const y = Hpx / 2;
  const xp = predicted === undefined ? undefined : x1 - predicted * k;
  const off = xp !== undefined && (xp < 8 || xp > Wpx - 8);
  const barPx = nice(widthArcsec / 4 / PX_ARCSEC);
  const barW = barPx * PX_ARCSEC * k;
  return (
    <svg viewBox={`0 0 ${Wpx} ${Hpx}`} className="lab-sky" role="img"
      aria-label={`Sky view: the object shifts ${fmtArc(shift)} between the two images.`}>
      <rect width={Wpx} height={Hpx} className="lab-skybg" />
      {STARS.map((s, i) => (
        <circle key={i} cx={s.x * Wpx} cy={s.y * Hpx} r={0.6 + s.m * 1.6} className="lab-star" opacity={0.35 + s.m * 0.6} />
      ))}
      {blinkFrame === null && (
        <line x1={x1} y1={y} x2={x2} y2={y} className="lab-arrow" markerEnd="url(#lab-head)" />
      )}
      <defs>
        <marker id="lab-head" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto">
          <path d="M0,0 L10,5 L0,10 z" className="lab-headfill" />
        </marker>
      </defs>
      {(blinkFrame === null || blinkFrame === 0) && <circle cx={x1} cy={y} r={5.5} className="lab-dot d0" />}
      {(blinkFrame === null || blinkFrame === 1) && <circle cx={x2} cy={y} r={5.5} className="lab-dot d1" />}
      {blinkFrame === null && (
        <>
          <text x={x1} y={y - 12} textAnchor="middle" className="lab-label">{labels[0]}</text>
          <text x={x2} y={y + 22} textAnchor="middle" className="lab-label">{labels[1]}</text>
        </>
      )}
      {xp !== undefined && !off && <circle cx={xp} cy={y} r={11} className="lab-pred" />}
      {xp !== undefined && off && (
        <text x={xp < 8 ? 10 : Wpx - 10} y={y + 44} textAnchor={xp < 8 ? "start" : "end"} className="lab-label warn">
          {xp < 8 ? "◀" : ""} your prediction is off-screen {xp > Wpx - 8 ? "▶" : ""}
        </text>
      )}
      <line x1={12} x2={12 + barW} y1={Hpx - 12} y2={Hpx - 12} className="lab-bar" />
      <text x={12} y={Hpx - 18} className="lab-note">{barPx} SPHEREx px = {fmtArc(barPx * PX_ARCSEC)}</text>
      <text x={Wpx - 10} y={14} textAnchor="end" className="lab-note">E ←  sky  → W {observedNoiseless ? "" : " · with measurement noise"}</text>
    </svg>
  );
}

function useBlink(on: boolean) {
  const [f, setF] = useState<0 | 1>(0);
  useEffect(() => {
    if (!on) return;
    const t = window.setInterval(() => setF((x) => (x ? 0 : 1)), 650);
    return () => window.clearInterval(t);
  }, [on]);
  return on ? f : null;
}

/* --------------------------------------------------------- simulator */

const PRESETS: [string, number][] = [
  ["Mars", 1.52],
  ["Jupiter", 5.2],
  ["Neptune", 30.1],
  ["Pluto", 39.5],
  ["Planet Nine?", 500],
];

function Simulator() {
  const [d, setD] = useState(30.1);
  const [months, setMonths] = useState(6);
  const [orbit, setOrbit] = useState(true);
  const [blink, setBlink] = useState(false);
  const frame = useBlink(blink);
  const days = (months / 12) * 365.25;
  const s = sky2d(d, days, orbit);
  const width = Math.max(90, Math.abs(s.shiftArcsec) * 1.5);
  const bright = Math.pow(NEPTUNE_AU / d, 4); // same size and albedo as Neptune; reflected light ~ 1/(r² Δ²)
  const ratio = ONE_IMAGE_LIMIT / bright;
  const frames = ratio <= 1 ? 1 : Math.ceil(ratio * ratio); // stacking N images improves depth by √N

  return (
    <section className="glass lab-card">
      <div className="lab-head">
        <small>1 · SIMULATOR</small>
        <h2>Why does a distant object shift on the sky?</h2>
        <p>
          SPHEREx photographs the same patch of sky every six months. In between, Earth travels to the other side of
          the Sun, so we look at the object from a different place: it shifts against the far-away stars. Nearer objects
          shift more. <b>Measure the shift and you know the distance.</b> Everything here is computed live.
        </p>
      </div>
      <div className="lab-grid">
        <TopView d={d} days={days} orbit={orbit} />
        <div className="lab-right">
          <SkyView shift={s.shiftArcsec} blinkFrame={frame} widthArcsec={width} />
          <div className="lab-controls">
            <DistanceSlider value={d} onChange={setD} />
            <div className="lab-presets">
              {PRESETS.map(([n, v]) => (
                <button key={n} className={`lab-chip ${Math.abs(d - v) / v < 0.01 ? "on" : ""}`} onClick={() => setD(v)}>{n}</button>
              ))}
            </div>
            <label className="lab-slider">
              <span>Time between images</span>
              <input type="range" min={1} max={12} value={months} onChange={(e) => setMonths(Number(e.target.value))} />
              <b>{months} mo</b>
            </label>
            <div className="lab-toggles">
              <label><input type="checkbox" checked={orbit} onChange={(e) => setOrbit(e.target.checked)} /> object also moves along its own orbit</label>
              <label><input type="checkbox" checked={blink} onChange={(e) => setBlink(e.target.checked)} /> blink the two images</label>
            </div>
          </div>
        </div>
      </div>
      <div className="lab-readout">
        <div><small>SHIFT ON THE SKY</small><b>{fmtArc(s.shiftArcsec)}</b><span>{fmt(Math.abs(s.shiftArcsec) / PX_ARCSEC)} SPHEREx pixels</span></div>
        <div><small>FROM EARTH'S MOTION</small><b>{fmtArc(s.parallaxArcsec)}</b><span>parallax</span></div>
        <div><small>FROM ITS OWN ORBIT</small><b>{fmtArc(s.orbitalArcsec)}</b><span>{!orbit ? "switched off" : Math.sign(s.orbitalArcsec) === Math.sign(s.parallaxArcsec) ? "same direction · ignoring it biases the distance" : "opposite direction · ignoring it biases the distance"}</span></div>
        <div className={ratio <= 1 ? "ok" : "warn"}>
          <small>CAN ONE SPHEREx IMAGE SEE IT?</small>
          <b>{ratio <= 1 ? "Yes" : "No"}</b>
          <span>{ratio <= 1 ? "if it is as big and bright as Neptune" : `need ~${frames.toLocaleString("en")} images stacked (Neptune-sized)`}</span>
        </div>
      </div>
      <p className="lab-foot">
        Geometry is not the hard part: even at 1,000 AU the shift is dozens of pixels. Brightness is. Reflected sunlight
        fades as 1/distance⁴, and our injection test shows one SPHEREx image finds sources down to about 1/500 of Neptune's
        brightness. Beyond ~140 AU a Neptune-sized planet needs many images added along its path (Shift &amp; Stack).
      </p>
    </section>
  );
}

/* --------------------------------------------------------- game */

type Round = { truth: number; observed: number };
const NOISE_PX = 0.3;

function newRound(): Round {
  const truth = logToValue(Math.random(), 3, 800);
  const g = Math.sqrt(-2 * Math.log(Math.random() || 1e-9)) * Math.cos(2 * Math.PI * Math.random());
  return { truth, observed: sky2d(truth, HALF_YEAR).shiftArcsec + g * NOISE_PX * PX_ARCSEC };
}

function Game() {
  const [round, setRound] = useState<Round>(() => newRound());
  const [guess, setGuess] = useState(60);
  const [done, setDone] = useState(false);
  const [history, setHistory] = useState<{ truth: number; guess: number }[]>([]);
  const pred = sky2d(guess, HALF_YEAR).shiftArcsec;
  const missPx = Math.abs(pred - round.observed) / PX_ARCSEC;
  const width = Math.max(90, Math.abs(round.observed) * 1.8);
  const err = (100 * (guess - round.truth)) / round.truth;
  const lock = () => {
    setDone(true);
    setHistory((h) => [{ truth: round.truth, guess }, ...h].slice(0, 5));
  };
  const next = () => {
    setRound(newRound());
    setGuess(60);
    setDone(false);
  };
  return (
    <section className="glass lab-card">
      <div className="lab-head">
        <small>2 · GAME</small>
        <h2>Find the hidden planet</h2>
        <p>
          We hid a planet somewhere between 3 and 800 AU and took two images six months apart (white dots, with real-size
          measurement noise). Turn the dial: the ring shows where a planet at your distance would appear in image 2.
          Make the ring land on the dot, then lock it in.
        </p>
      </div>
      <div className="lab-gamesky"><SkyView shift={round.observed} predicted={pred} blinkFrame={null} widthArcsec={width} labels={["image 1", "image 2 (observed)"]} observedNoiseless={false} /></div>
      <div className="lab-controls">
        <DistanceSlider value={guess} onChange={(v) => !done && setGuess(v)} min={2} max={1000} label="Your distance" />
      </div>
      <div className="lab-game-row">
        <div className="lab-miss">
          <small>MISS</small>
          <b className={missPx < 1 ? "good" : ""}>{fmt(missPx)} px</b>
          <span>{missPx < 1 ? "Within one pixel — lock it in" : Math.abs(pred) > Math.abs(round.observed) ? "Too close: the ring overshoots" : "Too far: the ring falls short"}</span>
        </div>
        {!done ? (
          <button className="button primary" onClick={lock}>Lock in {fmt(guess)} AU</button>
        ) : (
          <div className="lab-reveal">
            <b>Hidden planet: {fmt(round.truth)} AU</b>
            <span>Your answer {fmt(guess)} AU · error {err > 0 ? "+" : ""}{err.toFixed(1)}%</span>
            <button className="button secondary" onClick={next}>Hide another planet</button>
          </div>
        )}
      </div>
      {history.length > 0 && (
        <p className="lab-foot">
          Your last rounds: {history.map((h) => `${fmt(h.guess)} vs ${fmt(h.truth)} AU`).join(" · ")}. The farther the
          planet, the smaller the shift, so the same pixel of noise means a bigger percentage error.
        </p>
      )}
    </section>
  );
}

/* --------------------------------------------------------- real data */

type Blind = {
  anchor: Anchor;
  tilt_deg: number;
  gm_sun_au3_day2: number;
  obliquity_deg: number;
  june: { ra_deg: number; dec_deg: number; mjd: number }[];
  december: (Target & { ra_deg: number; dec_deg: number; z: number })[];
  fit: { r_au: number; boot_std_au: number; rms_miss_arcsec: number };
  horizons: { r_au: number };
  detection: Record<string, { differences: number; neptune_found: number; strongest: number }>;
  mask_ablation: Record<string, { neptune_found: number; differences: number }>;
  injection: { peak_sigma: number; recovered: number }[];
  tracks: { window: number; label: string }[];
};

function rmsMiss(b: Blind, r: number) {
  const p = predictRaDec(b.anchor, b.december, r, b.tilt_deg, b.gm_sun_au3_day2, b.obliquity_deg);
  if (!p) return Infinity;
  const s = p.map((q, i) => sepArcsec(q.ra, q.dec, b.december[i].ra_deg, b.december[i].dec_deg) ** 2);
  return Math.sqrt(s.reduce((a, x) => a + x, 0) / s.length);
}

function RealData() {
  const [b, setB] = useState<Blind | null>(null);
  const [err, setErr] = useState("");
  const [r, setR] = useState(45);
  const [reveal, setReveal] = useState(false);
  useEffect(() => {
    const c = new AbortController();
    fetch("data/blind/neptune_blind.json", { signal: c.signal })
      .then((x) => (x.ok ? x.json() : Promise.reject(new Error(`blind test data missing (${x.status})`))))
      .then(setB)
      .catch((e: Error) => !c.signal.aborted && setErr(e.message));
    return () => c.abort();
  }, []);
  const curve = useMemo(() => {
    if (!b) return [];
    return Array.from({ length: 240 }, (_, i) => {
      const rr = logToValue(i / 239, 10, 100);
      return { r: rr, miss: rmsMiss(b, rr) / PX_ARCSEC };
    });
  }, [b]);
  if (err) return <section className="glass lab-card"><p role="alert">{err}</p></section>;
  if (!b) return <section className="glass lab-card"><p role="status">Loading the Neptune blind test…</p></section>;

  const pred = predictRaDec(b.anchor, b.december, r, b.tilt_deg, b.gm_sun_au3_day2, b.obliquity_deg) ?? [];
  const missPx = rmsMiss(b, r) / PX_ARCSEC;
  const best = curve.reduce((a, c) => (c.miss < a.miss ? c : a), curve[0]);
  const ra0 = b.december.reduce((a, x) => a + x.ra_deg, 0) / b.december.length;
  const de0 = b.december.reduce((a, x) => a + x.dec_deg, 0) / b.december.length;
  const det = b.december.map((x) => offsetArcsec(x.ra_deg, x.dec_deg, ra0, de0));
  const half = Math.max(70, ...det.map((p) => Math.max(Math.abs(p.x), Math.abs(p.y)) * 1.5));
  const S = 300, k = (S / 2 - 16) / half;
  const toX = (x: number) => S / 2 - x * k; // east left
  const toY = (y: number) => S / 2 - y * k;
  const pp = pred.map((q) => offsetArcsec(q.ra, q.dec, ra0, de0));
  const inside = pp.filter((p) => Math.abs(p.x) < half && Math.abs(p.y) < half);
  const mid = pp[Math.floor(pp.length / 2)];
  const found = Object.values(b.detection).reduce((a, x) => a + x.neptune_found, 0);
  const diffs = Object.values(b.detection).reduce((a, x) => a + x.differences, 0);
  const rejected = b.tracks.filter((t) => t.label !== "mover").length;

  // miss curve
  const CW = 300, CH = 150, pl = 34, pb = 22;
  const cx = (rr: number) => pl + valueToLog(rr, 10, 100) * (CW - pl - 6);
  const lmax = Math.log10(5000), lmin = Math.log10(0.5);
  const cy = (m: number) => 6 + (1 - (Math.log10(Math.min(Math.max(m, 0.5), 5000)) - lmin) / (lmax - lmin)) * (CH - pb - 6);
  const path = curve.map((c, i) => `${i ? "L" : "M"}${cx(c.r).toFixed(1)},${cy(c.miss).toFixed(1)}`).join("");

  return (
    <section className="glass lab-card">
      <div className="lab-head">
        <small>3 · REAL SPHEREx DATA · NEPTUNE BLIND TEST</small>
        <h2>Now do it with real NASA images</h2>
        <p>
          Our detector searched real SPHEREx images from June and December 2025 <b>without being told where Neptune is</b>.
          It found one object that moves, in {found} of {diffs} image differences, and rejected {rejected} fake tracks
          (fixed stars, optical ghosts, glare). Below: the orange dots are where it saw the object in December. The rings
          are where a planet seen in June would be in December, for your distance — computed with the same formula as
          our pipeline.
        </p>
      </div>
      <div className="lab-grid">
        <svg viewBox={`0 0 ${S} ${S}`} className="lab-real" role="img" aria-label={`December detections and predicted positions for ${fmt(r)} AU`}>
          <rect width={S} height={S} className="lab-skybg" />
          {[-1, 1].map((sgn) => <line key={sgn} x1={S / 2 + sgn * 60 * k} x2={S / 2 + sgn * 60 * k} y1={0} y2={S} className="lab-gridline" />)}
          {det.map((p, i) => <circle key={i} cx={toX(p.x)} cy={toY(p.y)} r={3.2} className="lab-det" />)}
          {inside.length > 1 && <polyline points={inside.map((p) => `${toX(p.x)},${toY(p.y)}`).join(" ")} className="lab-predline" />}
          {inside.map((p, i) => <circle key={i} cx={toX(p.x)} cy={toY(p.y)} r={6} className="lab-pred small" />)}
          {inside.length === 0 && mid && (() => {
            const ang = Math.atan2(-(mid.y), -(mid.x)) ;
            const ex = S / 2 + Math.cos(ang) * (S / 2 - 26), ey = S / 2 - Math.sin(ang) * (S / 2 - 26);
            return (
              <g>
                <line x1={S / 2} y1={S / 2} x2={ex} y2={ey} className="lab-arrow warn" markerEnd="url(#lab-head2)" />
                <defs><marker id="lab-head2" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0,0 L10,5 L0,10 z" className="lab-headfill warn" /></marker></defs>
                <text x={S / 2} y={S - 12} textAnchor="middle" className="lab-label warn">prediction is {fmtArc(missPx * PX_ARCSEC)} away, off this view</text>
              </g>
            );
          })()}
          <text x={8} y={14} className="lab-note">December 2025 · window {fmtArc(2 * half)} wide · grid 1′</text>
        </svg>
        <div className="lab-right">
          <div className="lab-controls">
            <DistanceSlider value={r} onChange={setR} min={10} max={100} label="Trial distance" />
          </div>
          <div className="lab-miss">
            <small>AVERAGE MISS ON THE DECEMBER DETECTIONS</small>
            <b className={missPx < 3 ? "good" : ""}>{fmt(missPx)} px</b>
            <span>{missPx < 3 ? "The rings sit on the dots: this is the distance." : r > best.r ? "Too far — move the dial left" : "Too close — move the dial right"}</span>
          </div>
          <svg viewBox={`0 0 ${CW} ${CH}`} className="lab-curve" role="img" aria-label="Miss versus trial distance">
            <path d={path} className="lab-curveline" />
            {[10, 20, 30, 50, 100].map((t) => <text key={t} x={cx(t)} y={CH - 6} textAnchor={t === 100 ? "end" : "middle"} className="lab-note">{t === 100 ? "100 AU" : t}</text>)}
            {[1, 10, 100, 1000].map((t) => <text key={t} x={pl - 4} y={cy(t) + 3} textAnchor="end" className="lab-note">{t}</text>)}
            <circle cx={cx(r)} cy={cy(missPx)} r={4.5} className="lab-curvedot" />
            {reveal && <line x1={cx(b.horizons.r_au)} x2={cx(b.horizons.r_au)} y1={4} y2={CH - pb} className="lab-truth" />}
            <text x={pl + 2} y={12} className="lab-note">miss (px)</text>
          </svg>
          {!reveal ? (
            <button className="button secondary" onClick={() => setReveal(true)}>Reveal the NASA JPL answer</button>
          ) : (
            <div className="lab-reveal">
              <b>Our blind result {b.fit.r_au.toFixed(2)} AU · JPL Horizons {b.horizons.r_au.toFixed(2)} AU</b>
              <span>Difference {(b.fit.r_au - b.horizons.r_au).toFixed(2)} AU ({((100 * (b.fit.r_au - b.horizons.r_au)) / b.horizons.r_au).toFixed(2)}%). JPL was used only to grade, never to find or fit.</span>
            </div>
          )}
        </div>
      </div>
      <div className="lab-readout">
        <div><small>FOUND WITHOUT JPL</small><b>{found}/{diffs}</b><span>image differences</span></div>
        <div><small>BLIND DISTANCE</small><b>{b.fit.r_au.toFixed(2)} AU</b><span>± {b.fit.boot_std_au.toFixed(2)} (statistical)</span></div>
        <div><small>FAKE TRACKS REJECTED</small><b>{rejected}</b><span>static stars, ghosts, glare</span></div>
        <div><small>SPHEREx FLAG FINDING</small><b>+{b.mask_ablation.mover_mask.neptune_found - b.mask_ablation.standard_mask.neptune_found}</b><span>detections kept by not masking OUTLIER/TRANSIENT</span></div>
      </div>
      <p className="lab-foot">
        Honest limits: the image cutouts were downloaded around Neptune, so the search area was chosen with prior
        knowledge even though the algorithm never uses it. Neptune's orbit is nearly circular, which suits the model.
        Details: docs/BLIND_TEST.md in the repository.
      </p>
    </section>
  );
}

/* --------------------------------------------------------- page */

export function ParallaxLab({ onOpenDial }: { onOpenDial?: () => void }) {
  const top = useRef<HTMLDivElement>(null);
  return (
    <main className="content-screen lab-screen" ref={top}>
      <section className="section-title">
        <small>PARALLAX LAB</small>
        <h1>Measure a planet’s distance from two pictures.</h1>
        <p>
          Three steps: see why distant objects shift, find a hidden planet yourself, then repeat it on real SPHEREx data
          where our pipeline found Neptune on its own.
        </p>
      </section>
      <Simulator />
      <Game />
      <RealData />
      {onOpenDial && (
        <p className="lab-foot center">
          Want the science team's single-pair version with 1,007 Neptune pairs?{" "}
          <button className="text-link" onClick={onOpenDial}>Open the original Distance Dial →</button>
        </p>
      )}
    </main>
  );
}
