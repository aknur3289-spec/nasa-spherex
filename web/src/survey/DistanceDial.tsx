import { useEffect, useMemo, useRef, useState } from "react";

/**
 * F5 — Distance Dial on real SPHEREx data (Neptune, one exposure pair).
 * Source: docs/dial_table_neptune.csv, copied to public/data/dial/neptune.csv.
 * Line 1 is a "# ref … target … truth … AU" comment; the header follows.
 */

type Row = {
  distance: number;
  ra: number;
  dec: number;
  modelPx: number;
  modelArcsec: number;
  naivePx: number;
  naiveArcsec: number;
};
type Table = { rows: Row[]; ref: string; target: string; truthAu: number | null };

const CSV_URL = "data/dial/neptune.csv";
const PX_ARCSEC = 6.15; // SPHEREx pixel scale, for the "1 px ≈ 6″" note

export function parseDialCsv(text: string): Table {
  const lines = text.split(/\r?\n/).filter((l) => l.trim() !== "");
  const comment = lines.find((l) => l.startsWith("#")) ?? "";
  const data = lines.filter((l) => !l.startsWith("#"));
  const header = data[0].split(",").map((h) => h.trim());
  const col = (name: string) => {
    const i = header.indexOf(name);
    if (i < 0) throw new Error(`Column ${name} missing in dial table`);
    return i;
  };
  const c = {
    d: col("distance_au"),
    ra: col("model_pred_ra_deg"),
    dec: col("model_pred_dec_deg"),
    mpx: col("model_miss_px"),
    mas: col("model_miss_arcsec"),
    npx: col("parallax_only_miss_px"),
    nas: col("parallax_only_miss_arcsec"),
  };
  const rows = data
    .slice(1)
    .map((l) => l.split(","))
    .map((v) => ({
      distance: Number(v[c.d]),
      ra: Number(v[c.ra]),
      dec: Number(v[c.dec]),
      modelPx: Number(v[c.mpx]),
      modelArcsec: Number(v[c.mas]),
      naivePx: Number(v[c.npx]),
      naiveArcsec: Number(v[c.nas]),
    }))
    .filter((r) => Number.isFinite(r.distance) && Number.isFinite(r.modelPx))
    .sort((a, b) => a.distance - b.distance);
  const m = comment.match(/ref\s+(\S+)\s+target\s+(\S+)\s+truth\s+([\d.]+)/);
  return { rows, ref: m?.[1] ?? "", target: m?.[2] ?? "", truthAu: m ? Number(m[3]) : null };
}

const argmin = (rows: Row[], key: "modelPx" | "naivePx") =>
  rows.reduce((best, r, i) => (r[key] < rows[best][key] ? i : best), 0);

/* ---------- chart ---------- */

const W = 640;
const H = 300;
const PAD = { l: 52, r: 16, t: 18, b: 40 };
const Y_MIN = 5; // px, log scale so the non-zero minimum stays visible
const Y_MAX = 2000;
const logFrac = (px: number) => (Math.log10(Math.min(Math.max(px, Y_MIN), Y_MAX)) - Math.log10(Y_MIN)) / (Math.log10(Y_MAX) - Math.log10(Y_MIN));

function MissChart({
  rows,
  index,
  modelMin,
  naiveMin,
  truthAu,
  showNaive,
  onPick,
}: {
  rows: Row[];
  index: number;
  modelMin: number;
  naiveMin: number;
  truthAu: number | null;
  showNaive: boolean;
  onPick: (i: number) => void;
}) {
  const d0 = rows[0].distance;
  const d1 = rows[rows.length - 1].distance;
  const x = (d: number) => PAD.l + ((d - d0) / (d1 - d0)) * (W - PAD.l - PAD.r);
  const y = (px: number) => PAD.t + (1 - logFrac(px)) * (H - PAD.t - PAD.b);
  const line = (key: "modelPx" | "naivePx") => rows.map((r) => `${x(r.distance).toFixed(1)},${y(r[key]).toFixed(1)}`).join(" ");
  const cur = rows[index];
  const ticksX = [20, 25, 30, 35, 40, 45].filter((t) => t >= d0 && t <= d1);
  const ticksY = [10, 30, 100, 300, 1000];
  const svgRef = useRef<SVGSVGElement>(null);

  const pick = (clientX: number) => {
    const box = svgRef.current?.getBoundingClientRect();
    if (!box) return;
    const d = d0 + ((((clientX - box.left) / box.width) * W - PAD.l) / (W - PAD.l - PAD.r)) * (d1 - d0);
    let best = 0;
    rows.forEach((r, i) => {
      if (Math.abs(r.distance - d) < Math.abs(rows[best].distance - d)) best = i;
    });
    onPick(best);
  };

  return (
    <svg
      ref={svgRef}
      className="dial-chart"
      viewBox={`0 0 ${W} ${H}`}
      role="img"
      aria-label={`Miss in pixels versus trial distance. Closest match at ${rows[modelMin].distance.toFixed(1)} AU.`}
      onPointerDown={(e) => pick(e.clientX)}
      onPointerMove={(e) => e.buttons === 1 && pick(e.clientX)}
    >
      {ticksY.map((t) => (
        <g key={t}>
          <line x1={PAD.l} x2={W - PAD.r} y1={y(t)} y2={y(t)} className="dial-grid" />
          <text x={PAD.l - 8} y={y(t) + 4} textAnchor="end" className="dial-tick">
            {t}
          </text>
        </g>
      ))}
      {ticksX.map((t) => (
        <text key={t} x={x(t)} y={H - PAD.b + 18} textAnchor="middle" className="dial-tick">
          {t}
        </text>
      ))}
      <text x={(PAD.l + W - PAD.r) / 2} y={H - 4} textAnchor="middle" className="dial-axis">
        Trial distance (AU)
      </text>
      <text x={14} y={(PAD.t + H - PAD.b) / 2} textAnchor="middle" className="dial-axis" transform={`rotate(-90 14 ${(PAD.t + H - PAD.b) / 2})`}>
        Miss (px, log)
      </text>

      {truthAu !== null && (
        <g>
          <line x1={x(truthAu)} x2={x(truthAu)} y1={PAD.t} y2={H - PAD.b} className="dial-truth" />
          <text x={x(truthAu) - 6} y={PAD.t + 12} textAnchor="end" className="dial-note truth">
            JPL {truthAu.toFixed(2)} AU
          </text>
        </g>
      )}

      {showNaive && <polyline points={line("naivePx")} className="dial-naive" />}
      <polyline points={line("modelPx")} className="dial-model" />

      <g>
        <circle cx={x(rows[modelMin].distance)} cy={y(rows[modelMin].modelPx)} r={5} className="dial-min" />
        <text x={x(rows[modelMin].distance) + 10} y={y(rows[modelMin].modelPx) + 16} className="dial-note">
          closest match · {rows[modelMin].distance.toFixed(1)} AU
        </text>
      </g>
      {showNaive && (
        <g>
          <circle cx={x(rows[naiveMin].distance)} cy={y(rows[naiveMin].naivePx)} r={4} className="dial-min naive" />
          <text x={x(rows[naiveMin].distance)} y={y(rows[naiveMin].naivePx) - 12} textAnchor="middle" className="dial-note naive">
            parallax only · {rows[naiveMin].distance.toFixed(1)} AU
          </text>
        </g>
      )}

      <line x1={x(cur.distance)} x2={x(cur.distance)} y1={PAD.t} y2={H - PAD.b} className="dial-cursor" />
      <circle cx={x(cur.distance)} cy={y(cur.modelPx)} r={7} className="dial-dot" />
    </svg>
  );
}


/* ---------- the "game": crosshair on a real SPHEREx stamp ---------- */

type Target = { ra_deg: number; dec_deg: number; pixel_scale_arcsec: number };
const STAMP = 64; // stamp size in pixels, Neptune near the centre
const STAMP_SCALE = 5; // on-screen pixels per image pixel

function offsetPx(row: Row, t: Target) {
  const wrap = (d: number) => ((d + 540) % 360) - 180;
  const c = Math.cos((t.dec_deg * Math.PI) / 180);
  const dxArc = wrap(row.ra - t.ra_deg) * c * 3600;
  const dyArc = (row.dec - t.dec_deg) * 3600;
  // north up, east left
  return { x: -dxArc / t.pixel_scale_arcsec, y: -dyArc / t.pixel_scale_arcsec };
}

function DialGame({
  row,
  best,
  target,
  index,
  max,
  onChange,
}: {
  row: Row;
  best: Row;
  target: Target | null;
  index: number;
  max: number;
  onChange: (i: number) => void;
}) {
  const size = STAMP * STAMP_SCALE;
  const half = size / 2;
  const off = target ? offsetPx(row, target) : { x: row.modelPx, y: 0 };
  const px = half + off.x * STAMP_SCALE;
  const py = half + off.y * STAMP_SCALE;
  const inside = px > 12 && px < size - 12 && py > 12 && py < size - 12;
  const angle = Math.atan2(py - half, px - half);
  const ex = half + Math.cos(angle) * (half - 26);
  const ey = half + Math.sin(angle) * (half - 26);
  const isBest = row.distance === best.distance;
  const state = isBest ? "best" : row.modelPx < 25 ? "close" : row.modelPx < STAMP / 2 ? "near" : "far";
  const label = {
    best: "Closest match",
    close: "Very close",
    near: "Getting closer",
    far: row.distance > best.distance ? "Too far — turn the dial down" : "Too close — turn the dial up",
  }[state];

  return (
    <div className="glass dial-game">
      <div className="card-heading">
        <div>
          <small>YOUR MISSION</small>
          <h3>Land the crosshair on Neptune</h3>
        </div>
        <span className={`chip dial-state ${state}`}>{label}</span>
      </div>
      <div className="dial-game-body">
        <div className="dial-stamp" style={{ width: size, height: size }}>
          <img src="data/dial/neptune_stamp.png" alt="Neptune in a real SPHEREx image" width={size} height={size} />
          <span className="dial-neptune" style={{ left: half, top: half }}>
            <i />
            <b>Neptune</b>
          </span>
          {inside ? (
            <span className={`dial-cross ${state}`} style={{ left: px, top: py }} aria-hidden="true" />
          ) : (
            <span className="dial-away" style={{ left: ex, top: ey, transform: `translate(-50%,-50%) rotate(${angle}rad)` }} aria-hidden="true">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round"><path d="M4 12h15M13 6l6 6-6 6" /></svg>
            </span>
          )}
          {!inside && <span className="dial-away-label">Prediction is {Math.round(row.modelPx)} px off the picture</span>}
        </div>
        <div className="dial-game-copy">
          <div className="dial-big">
            <span>Your distance — drag the dial</span>
            <b>{row.distance.toFixed(1)} AU</b>
          </div>
          <input
            className="dial-game-knob"
            type="range"
            min={0}
            max={max}
            step={1}
            value={index}
            onChange={(e) => onChange(Number(e.target.value))}
            aria-label="Trial distance"
            aria-valuetext={`${row.distance.toFixed(1)} AU`}
          />
          <div className="dial-big">
            <span>Crosshair misses by</span>
            <b>
              {row.modelPx.toFixed(1)} px <em>({row.modelArcsec.toFixed(0)}″)</em>
            </b>
          </div>
          <ol className="dial-howto">
            <li>We know where Neptune was in June 2025.</li>
            <li>Pick a distance. Our model predicts where Neptune should be in December 2025.</li>
            <li>The distance whose crosshair lands closest to Neptune is the measurement.</li>
          </ol>
          <p className="dial-caption">
            Background: Neptune in a real SPHEREx cutout (June 2025). Crosshair: the December 2025 prediction for
            your distance, drawn relative to Neptune's measured position. Even the closest match misses by about
            13 px — see why below.
          </p>
        </div>
      </div>
    </div>
  );
}

/* ---------- screen ---------- */

const FIGURES = [
  {
    src: "figures/parallax_explainer.svg",
    title: "How the dial works",
    text: "From one measured position and a trial distance we predict where the object should be six months later.",
  },
  {
    src: "figures/distance_recovery.svg",
    title: "Distance recovery",
    text: "Neptune 29.95 AU vs JPL 29.89 AU (+0.2%); Uranus 19.39 vs 19.50 AU (−0.5%).",
  },
  {
    src: "figures/astrometric_hist_all.png",
    title: "All 265 exposure pairs",
    text: "Distribution of fitted distances over 265 Neptune pairs. The headline value is their median.",
  },
  {
    src: "figures/detectability.svg",
    title: "Detectability",
    text: "Single-frame limit AB 18.4 vs the published Planet Nine estimate V = 21.9–22.7.",
  },
  {
    src: "figures/focus_curve_synthetic.svg",
    title: "Focus curve (synthetic)",
    text: "Illustration of the stacking idea on synthetic data, not a measurement.",
  },
];

export function DistanceDial() {
  const [table, setTable] = useState<Table | null>(null);
  const [error, setError] = useState("");
  const [index, setIndex] = useState(0);
  const [showNaive, setShowNaive] = useState(true);
  const [sweeping, setSweeping] = useState(false);
  const [target, setTarget] = useState<Target | null>(null);
  useEffect(() => {
    fetch("data/dial/neptune_target.json")
      .then((r) => (r.ok ? r.json() : null))
      .then(setTarget)
      .catch(() => setTarget(null));
  }, []);
  const timer = useRef<number | undefined>(undefined);

  useEffect(() => {
    const controller = new AbortController();
    fetch(CSV_URL, { signal: controller.signal })
      .then((r) => {
        if (!r.ok) throw new Error(`Dial table not found (${r.status})`);
        return r.text();
      })
      .then((t) => {
        const parsed = parseDialCsv(t);
        setTable(parsed);
        setIndex(parsed.rows.length - 1); // start far away: 45 AU
      })
      .catch((e: Error) => !controller.signal.aborted && setError(e.message));
    return () => controller.abort();
  }, []);

  const rows = table?.rows ?? [];
  const modelMin = useMemo(() => (rows.length ? argmin(rows, "modelPx") : 0), [rows]);
  const naiveMin = useMemo(() => (rows.length ? argmin(rows, "naivePx") : 0), [rows]);
  useEffect(() => () => window.clearInterval(timer.current), []);

  if (error) return <p role="alert">{error}</p>;
  if (!table || !rows.length) return <p role="status">Loading dial table…</p>;

  const cur = rows[index];
  const best = rows[modelMin];
  const step = rows.length > 1 ? rows[1].distance - rows[0].distance : 0.1;
  const atBest = index === modelMin;

  const sweep = () => {
    window.clearInterval(timer.current);
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduce) {
      setIndex(modelMin);
      return;
    }
    setSweeping(true);
    let i = rows.length - 1;
    setIndex(i);
    timer.current = window.setInterval(() => {
      i -= 2;
      if (i <= modelMin) {
        window.clearInterval(timer.current);
        setIndex(modelMin);
        setSweeping(false);
      } else setIndex(i);
    }, 30);
  };
  const stop = () => {
    window.clearInterval(timer.current);
    setSweeping(false);
  };

  return (
    <main className="content-screen dial-screen">
      <section className="detail-head">
        <div className="title-line">
          <div>
            <span className="chip success">Real SPHEREx data · one exposure pair</span>
            <h1>Distance Dial</h1>
            <p>
              Neptune · ref {table.ref || "—"} → target {table.target || "—"}. Turn the dial: for each trial distance
              we predict where Neptune should be in the later image and measure the miss.
            </p>
          </div>
          <div className="detail-actions">
            <button className="button primary" onClick={sweeping ? stop : sweep}>
              {sweeping ? "Stop" : "Sweep 45 → 20 AU"}
            </button>
            <button className="button secondary" onClick={() => { stop(); setIndex(modelMin); }}>
              Go to closest match
            </button>
            <button className={`button secondary ${showNaive ? "dial-on" : ""}`} aria-pressed={showNaive} onClick={() => setShowNaive(!showNaive)}>
              Parallax-only curve
            </button>
          </div>
        </div>
      </section>

      <DialGame row={cur} best={best} target={target} index={index} max={rows.length - 1} onChange={(i) => { stop(); setIndex(i); }} />

      <section className="data-grid">
        <div className="glass chart-card wide dial-card">
          <div className="card-heading">
            <div>
              <small>MISS VS TRIAL DISTANCE</small>
              <h3>Where does the prediction land?</h3>
            </div>
            <div className="dial-legend">
              <span><i className="lg-model" /> Orbit model</span>
              {showNaive && <span><i className="lg-naive" /> Parallax only</span>}
              <span><i className="lg-truth" /> JPL</span>
            </div>
          </div>

          <MissChart
            rows={rows}
            index={index}
            modelMin={modelMin}
            naiveMin={naiveMin}
            truthAu={table.truthAu}
            showNaive={showNaive}
            onPick={(i) => { stop(); setIndex(i); }}
          />

          <label className="dial-knob">
            <span>Trial distance</span>
            <input
              type="range"
              min={0}
              max={rows.length - 1}
              step={1}
              value={index}
              onChange={(e) => { stop(); setIndex(Number(e.target.value)); }}
              aria-valuetext={`${cur.distance.toFixed(1)} AU, miss ${cur.modelPx.toFixed(1)} pixels`}
            />
            <b>{cur.distance.toFixed(1)} AU</b>
          </label>
          <div className="dial-scale" aria-hidden="true">
            <span>{rows[0].distance.toFixed(0)} AU</span>
            <span>step {step.toFixed(1)} AU</span>
            <span>{rows[rows.length - 1].distance.toFixed(0)} AU</span>
          </div>
        </div>

        <div className="glass confidence-card dial-readout">
          <small>MISS AT {cur.distance.toFixed(1)} AU</small>
          <div className="big-score">
            {cur.modelPx.toFixed(1)}
            <sup>px</sup>
          </div>
          <h3>{atBest ? "Closest match" : cur.distance > best.distance ? "Too far" : "Too close"}</h3>
          <p>
            {atBest
              ? `This is the smallest miss in the table, at ${best.distance.toFixed(1)} AU. It is not zero: one dial step (${step.toFixed(1)} AU) moves the predicted point by about 8 px, and the orbit model is an approximation (circular orbit).`
              : `Predicted position is ${cur.modelArcsec.toFixed(0)}″ from Neptune. Move the dial toward ${best.distance.toFixed(1)} AU.`}
          </p>
          {[
            ["Orbit model", cur.modelPx, best.modelPx],
            ["Parallax only", cur.naivePx, rows[naiveMin].naivePx],
          ].map(([k, v, minV]) => {
            const pct = Math.max(2, 100 - logFrac(v as number) * 100);
            return (
              <div className="metric" key={k as string}>
                <span>
                  {k as string} miss <b>{(v as number).toFixed(1)} px</b>
                </span>
                <i>
                  <em style={{ width: `${pct}%` }} />
                </i>
                <span className="dial-sub">lowest {(minV as number).toFixed(1)} px</span>
              </div>
            );
          })}
          {[
            ["Closest match (model)", `${best.distance.toFixed(1)} AU · ${best.modelPx.toFixed(1)} px (${best.modelArcsec.toFixed(0)}″)`],
            ["Parallax-only minimum", `${rows[naiveMin].distance.toFixed(1)} AU · ${rows[naiveMin].naivePx.toFixed(1)} px`],
            ["JPL Horizons", table.truthAu !== null ? `${table.truthAu.toFixed(2)} AU` : "—"],
            ["Pixel scale", `1 px ≈ ${PX_ARCSEC}″`],
          ].map(([k, v]) => (
            <div className="parameter" key={k}>
              <span>{k}</span>
              <b>{v}</b>
            </div>
          ))}
        </div>
      </section>

      <section className="stat-grid">
        {[
          ["NEPTUNE, 265 PAIRS", "29.95 AU", "± 0.03 AU (median)"],
          ["JPL HORIZONS", "29.89 AU", "+0.2% difference"],
          ["URANUS CHECK", "19.39 AU", "vs 19.50 AU (−0.5%)"],
          ["PARALLAX ONLY", "up to 50%", "error (−23% to +50%)"],
        ].map((s) => (
          <div className="glass stat" key={s[0]}>
            <small>{s[0]}</small>
            <strong>{s[1]}</strong>
            <span>{s[2]}</span>
          </div>
        ))}
      </section>
      <p className="dial-footnote">
        The dial above uses one exposure pair at 0.1 AU steps. The headline 29.95 AU is the median of 265 pairs
        fitted on a finer grid. The method assumes a circular orbit near the ecliptic; Neptune validates the geometry,
        not the sensitivity needed for a faint Planet Nine.
      </p>

      <section className="dial-figures">
        {FIGURES.map((f) => (
          <figure className="glass dial-figure" key={f.src}>
            <a href={f.src} target="_blank" rel="noreferrer" className="dial-figure-img">
              <img src={f.src} alt={f.title} loading="lazy" />
            </a>
            <figcaption>
              <b>{f.title}</b>
              <span>{f.text}</span>
            </figcaption>
          </figure>
        ))}
      </section>
    </main>
  );
}
