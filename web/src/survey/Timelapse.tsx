import { useEffect, useMemo, useRef, useState, type KeyboardEvent } from "react";
import type { Coordinates } from "../contract";
import { MappedImage, type ColourMap } from "./MappedImage";

/**
 * Timelapse player: plays the observations of one sky position in time order,
 * so fixed stars stay still and a moving object drifts.
 *
 * Two looks:
 *  - "photo" (default, no `src`): the site's space backdrop with the PARALLAX cyan target
 *    gliding between epochs, a dashed motion path and fading trail markers. Labelled "Demo data".
 *  - real cutouts (every frame has `src`): the SPHEREx PNGs, upscaled with crisp pixels.
 */

export type TimelapseFrame = {
  date: string; // ISO date, e.g. "2025-04-18"
  wavelengthUm: number;
  detector: number;
  src?: string; // real PNG cutout (all frames the same size)
  maskSrc?: string;
  targetRadec?: Coordinates;
  center?: Coordinates;
  widthPx?: number;
  heightPx?: number;
  sourceUrl?: string; // original file at IRSA
  object?: [number, number]; // tracked object position in % of the image (x, y)
  exposure?: number; // small brightness difference between exposures (demo look)
};

const DEMO_FRAMES: TimelapseFrame[] = [
  { date: "2025-04-18", wavelengthUm: 1.21, detector: 2, object: [38, 47], exposure: 1 },
  { date: "2025-04-30", wavelengthUm: 1.21, detector: 2, object: [42, 45.5], exposure: 0.94 },
  { date: "2025-07-22", wavelengthUm: 1.22, detector: 2, object: [50, 42], exposure: 1.05 },
  { date: "2025-10-26", wavelengthUm: 1.21, detector: 2, object: [57, 39.5], exposure: 0.97 },
  { date: "2025-11-07", wavelengthUm: 1.22, detector: 2, object: [62, 37], exposure: 1.02 },
];

const SPEEDS = [0.5, 1, 2] as const;
const BASE_MS = 1100; // time per frame at 1×
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const shortDate = (iso: string) => {
  const [y, m, d] = iso.split("-").map(Number);
  return { day: `${d} ${MONTHS[m - 1]}`, year: String(y) };
};
const daysBetween = (a: string, b: string) => Math.round((Date.parse(b) - Date.parse(a)) / 86_400_000);
const usePrefersReducedMotion = () =>
  useMemo(
    () => typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches,
    [],
  );

export function targetPosition(frame: TimelapseFrame): [number, number] | undefined {
  if (!frame.targetRadec || !frame.center || !frame.widthPx || !frame.heightPx) return undefined;
  const dra = ((frame.targetRadec.ra_deg - frame.center.ra_deg + 540) % 360) - 180;
  const dx = dra * Math.cos(frame.center.dec_deg * Math.PI / 180) * 3600 / 6.15;
  const dy = (frame.targetRadec.dec_deg - frame.center.dec_deg) * 3600 / 6.15;
  return [50 - dx / frame.widthPx * 100, 50 - dy / frame.heightPx * 100];
}

/* ---------- icons ---------- */

function PlayIcon({ playing }: { playing: boolean }) {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true">
      {playing ? <path d="M8 5h3v14H8zM13 5h3v14h-3z" fill="currentColor" /> : <path d="M8 5.5v13l11-6.5z" fill="currentColor" />}
    </svg>
  );
}
function Chevron({ dir }: { dir: "left" | "right" }) {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d={dir === "left" ? "m15 6-6 6 6 6" : "m9 6 6 6-6 6"} />
    </svg>
  );
}

/* ---------- the picture ---------- */

function SkyView({
  frames,
  index,
  backdrop,
  trails,
  path,
  reduced,
  compact = false,
  showMasks = false,
  colourMap = "grey",
}: {
  frames: TimelapseFrame[];
  index: number;
  backdrop: string;
  trails: boolean;
  path: boolean;
  reduced: boolean;
  compact?: boolean;
  showMasks?: boolean;
  colourMap?: ColourMap;
}) {
  const cur = frames[index];
  const real = !!cur.src;
  const position = (f: TimelapseFrame) => f.object ?? targetPosition(f);
  const pts = frames.slice(0, index + 1).map(position).filter(Boolean) as [number, number][];
  const currentPosition = position(cur);

  return (
    <div className={`tl-sky ${compact ? "compact" : ""} ${reduced ? "still" : ""}`}>
      {real ? (
        compact ? (
          <MappedImage src={cur.src!} alt="" map={colourMap} className="tl-frame on" />
        ) : (
          frames.map((f, i) => (
            <MappedImage key={f.src} src={f.src!} alt="" map={colourMap} className={`tl-frame ${i === index ? "on" : ""}`} />
          ))
        )
      ) : (
        <div
          className="tl-photo"
          style={{
            backgroundImage: `url(${backdrop})`,
            filter: `brightness(${cur.exposure ?? 1})`,
          }}
        />
      )}
      {real && showMasks && cur.maskSrc && <img src={cur.maskSrc} alt="" className="tl-mask" />}
      {!compact && <div className="tl-vignette" />}
      {!compact && <div className="map-grid tl-grid-lines" />}

      {/* motion path + earlier positions */}
      {pts.length > 1 && (
        <svg className="tl-overlay" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
          <defs>
            <linearGradient id="tl-path-grad" x1="0" x2="1">
              <stop offset="0" stopColor="#ffffff" stopOpacity="0.25" />
              <stop offset="1" stopColor="#ffffff" stopOpacity="0.8" />
            </linearGradient>
          </defs>
          {path && (
            <polyline
              points={pts.map((p) => p.join(",")).join(" ")}
              className="tl-path"
              stroke="url(#tl-path-grad)"
              vectorEffect="non-scaling-stroke"
            />
          )}
        </svg>
      )}
      {trails &&
        frames.slice(0, index).map((f, i) =>
          position(f) ? (
            <span
              key={f.date}
              className="tl-ghost"
              style={{
                left: `${position(f)![0]}%`,
                top: `${position(f)![1]}%`,
                opacity: 0.35 + 0.55 * ((i + 1) / Math.max(1, index)),
              }}
            >
              {!compact && <em>{shortDate(f.date).day}</em>}
            </span>
          ) : null,
        )}

      {currentPosition && (
        <span className={`tl-target ${cur.targetRadec ? "tl-target-real" : ""}`} style={{ left: `${currentPosition[0]}%`, top: `${currentPosition[1]}%` }}>
          {!compact && (
            <>
              <i className="tl-ticks" aria-hidden="true">
                <i />
                <i />
                <i />
                <i />
              </i>
              <b>{shortDate(cur.date).day}</b>
            </>
          )}
        </span>
      )}
    </div>
  );
}

/* ---------- recording (draws the same look onto a canvas) ---------- */

async function recordClip(frames: TimelapseFrame[], backdrop: string, speed: number, name: string) {
  const W = 720;
  const c = document.createElement("canvas");
  c.width = c.height = W;
  const ctx = c.getContext("2d")!;
  const img = new Image();
  img.crossOrigin = "anonymous";
  img.src = frames[0].src ?? backdrop;
  await img.decode();
  const realImgs = frames.every((f) => f.src)
    ? await Promise.all(
        frames.map(async (f) => {
          const im = new Image();
          im.crossOrigin = "anonymous";
          im.src = f.src!;
          await im.decode();
          return im;
        }),
      )
    : null;

  const cover = (im: HTMLImageElement) => {
    const s = Math.max(W / im.naturalWidth, W / im.naturalHeight);
    const w = im.naturalWidth * s;
    const h = im.naturalHeight * s;
    ctx.drawImage(im, (W - w) / 2, (W - h) / 2, w, h);
  };
  const per = BASE_MS / speed;
  const total = per * frames.length;
  const stream = c.captureStream(30);
  const rec = new MediaRecorder(stream, { mimeType: "video/webm" });
  const chunks: Blob[] = [];
  rec.ondataavailable = (e) => chunks.push(e.data);
  const done = new Promise<void>((r) => (rec.onstop = () => r()));
  rec.start();
  const t0 = performance.now();

  await new Promise<void>((resolve) => {
    const tick = () => {
      const t = performance.now() - t0;
      const i = Math.min(frames.length - 1, Math.floor(t / per));
      const k = Math.min(1, (t - i * per) / 400);
      ctx.imageSmoothingEnabled = !realImgs;
      ctx.fillStyle = "#05060f";
      ctx.fillRect(0, 0, W, W);
      if (realImgs) cover(realImgs[i]);
      else {
        ctx.filter = `brightness(${frames[i].exposure ?? 1})`;
        cover(img);
        ctx.filter = "none";
      }
      // path + ghosts + target
      const P = (p: [number, number]) => [(p[0] / 100) * W, (p[1] / 100) * W] as const;
      const pts = frames.map((f) => f.object).filter(Boolean) as [number, number][];
      if (pts.length > 1) {
        ctx.setLineDash([8, 7]);
        ctx.strokeStyle = "rgba(139,92,246,.8)";
        ctx.lineWidth = 2;
        ctx.beginPath();
        pts.forEach((p, j) => (j ? ctx.lineTo(...P(p)) : ctx.moveTo(...P(p))));
        ctx.stroke();
        ctx.setLineDash([]);
      }
      const a = frames[Math.max(0, i - 1)].object;
      const b = frames[i].object;
      if (b) {
        for (let j = 0; j < i; j++) {
          const g = frames[j].object;
          if (!g) continue;
          const [gx, gy] = P(g);
          ctx.fillStyle = `rgba(61,214,255,${0.25 + 0.5 * ((j + 1) / i)})`;
          ctx.beginPath();
          ctx.arc(gx, gy, 5, 0, Math.PI * 2);
          ctx.fill();
        }
        const from = a && i > 0 ? P(a) : P(b);
        const to = P(b);
        const e = 1 - Math.pow(1 - k, 3);
        const x = from[0] + (to[0] - from[0]) * e;
        const y = from[1] + (to[1] - from[1]) * e;
        ctx.shadowColor = "#3dd6ff";
        ctx.shadowBlur = 18;
        ctx.strokeStyle = "#3dd6ff";
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.arc(x, y, 24, 0, Math.PI * 2);
        ctx.stroke();
        ctx.shadowColor = "#fff";
        ctx.fillStyle = "#fff";
        ctx.beginPath();
        ctx.arc(x, y, 6, 0, Math.PI * 2);
        ctx.fill();
        ctx.shadowBlur = 0;
      }
      ctx.font = "26px 'DM Mono', monospace";
      ctx.fillStyle = "rgba(5,6,15,.7)";
      ctx.fillRect(20, W - 64, 190, 44);
      ctx.fillStyle = "#fff";
      ctx.fillText(frames[i].date, 34, W - 33);
      if (t < total) requestAnimationFrame(tick);
      else resolve();
    };
    requestAnimationFrame(tick);
  });
  rec.stop();
  await done;
  const link = document.createElement("a");
  link.href = URL.createObjectURL(new Blob(chunks, { type: "video/webm" }));
  link.download = `${name}-timelapse.webm`;
  link.click();
}

/* ---------- screen ---------- */

export function Timelapse({
  frames = DEMO_FRAMES,
  title = "PX-0714",
  backdrop,
  synthetic = true,
  onBack,
  heroSrc,
  heroCaption,
}: {
  frames?: TimelapseFrame[];
  title?: string;
  synthetic?: boolean;
  backdrop: string; // the site's space image
  onBack?: () => void;
  heroSrc?: string;
  heroCaption?: string;
}) {
  const real = frames.every((f) => f.src);
  const reduced = usePrefersReducedMotion();

  const [index, setIndex] = useState(0);
  const [playing, setPlaying] = useState(!reduced);
  const [speed, setSpeed] = useState<(typeof SPEEDS)[number]>(1);
  const [trails, setTrails] = useState(true);
  const [path, setPath] = useState(true);
  const [loop, setLoop] = useState(true);
  const [recording, setRecording] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [rawPixels, setRawPixels] = useState(false);
  const [showMasks, setShowMasks] = useState(false);
  const [colourMap, setColourMap] = useState<ColourMap>("grey");
  const [showAllLog, setShowAllLog] = useState(false);
  const stageRef = useRef<HTMLElement>(null);

  // Preload images so the first play is smooth.
  useEffect(() => {
    let alive = true;
    const urls = real ? frames.map((f) => f.src!) : [backdrop];
    Promise.all(
      urls.map(
        (u) =>
          new Promise<void>((res) => {
            const im = new Image();
            im.onload = im.onerror = () => res();
            im.src = u;
          }),
      ),
    ).then(() => alive && setLoaded(true));
    return () => {
      alive = false;
    };
  }, [frames, backdrop, real]);

  // Playback clock.
  useEffect(() => {
    if (!playing || !loaded || frames.length < 2) return;
    const id = window.setTimeout(() => {
      setIndex((i) => {
        if (i + 1 < frames.length) return i + 1;
        if (loop) return 0;
        setPlaying(false);
        return i;
      });
    }, BASE_MS / speed);
    return () => window.clearTimeout(id);
  }, [playing, index, speed, loop, loaded, frames.length]);

  const go = (i: number) => {
    setPlaying(false);
    setIndex((i + frames.length) % frames.length);
  };
  const onKey = (e: KeyboardEvent) => {
    if (e.target instanceof HTMLInputElement) return;
    if (e.key === " ") {
      e.preventDefault();
      setPlaying((p) => !p);
    } else if (e.key === "ArrowRight") {
      e.preventDefault();
      go(index + 1);
    } else if (e.key === "ArrowLeft") {
      e.preventDefault();
      go(index - 1);
    }
  };
  const canRecord = typeof window !== "undefined" && "MediaRecorder" in window;
  const onRecord = async () => {
    setRecording(true);
    try {
      await recordClip(frames, backdrop, speed, title);
    } finally {
      setRecording(false);
    }
  };

  const cur = frames[index];
  const first = frames[0];
  const last = frames[frames.length - 1];
  const gapNext = index < frames.length - 1 ? daysBetween(cur.date, frames[index + 1].date) : null;
  const progress = frames.length > 1 ? (index / (frames.length - 1)) * 100 : 0;
  const point = (f: TimelapseFrame) => f.object ?? targetPosition(f);
  const hasObject = frames.some((f) => point(f));
  const prev = index > 0 ? point(frames[index - 1]) : undefined;
  const curPoint = point(cur);
  const stepShift =
    prev && curPoint ? Math.hypot(curPoint[0] - prev[0], curPoint[1] - prev[1]).toFixed(1) : null;
  const shift =
    point(first) && point(last)
      ? Math.hypot(point(last)![0] - point(first)![0], point(last)![1] - point(first)![1]).toFixed(1)
      : null;

  const scrubLabels = (() => {
    const out: { i: number; text: string }[] = [];
    const maxLabels = 6;
    const step = Math.max(1, Math.ceil(frames.length / maxLabels));
    let lastText = "";
    frames.forEach((f, i) => {
      if (i % step !== 0 && i !== frames.length - 1) return;
      const [y, m] = f.date.split("-").map(Number);
      const text = `${MONTHS[m - 1]} ${String(y).slice(2)}`;
      if (text === lastText) return;
      if (i === frames.length - 1 && out.length && out[out.length - 1].i > i - step / 2) out.pop();
      out.push({ i, text });
      lastText = text;
    });
    return out;
  })();
  const avgGap = frames.length > 1 ? Math.round(daysBetween(first.date, last.date) / (frames.length - 1)) : 0;
  const bands = new Set(frames.map((f) => f.wavelengthUm.toFixed(2)));

  return (
    <main className={`content-screen timelapse-screen ${rawPixels ? "raw" : "enhanced"}`}>
      <section className="detail-head">
        {onBack && (
          <button className="back" onClick={onBack}>
            ← {title}
          </button>
        )}
        <div className="title-line">
          <div>
            <span className={`chip ${real ? "success" : "tl-demo-chip"}`}>
              {synthetic ? "Synthetic demonstration" : "SPHEREx cutouts · IRSA"}
            </span>
            <h1>{title === "Neptune moving against fixed stars" ? title : "Timelapse"}</h1>
            <p>
              {title} · {frames.length} observations · {shortDate(first.date).day} {shortDate(first.date).year} –{" "}
              {shortDate(last.date).day} {shortDate(last.date).year}
            </p>
            {heroSrc && <div className="tl-hero"><img src={heroSrc} alt="Three-band SPHEREx composite" /><span>{heroCaption}</span></div>}
          </div>
          <div className="detail-actions">
            {!real && (
              <>
                <button className={`button secondary ${trails ? "tl-on" : ""}`} onClick={() => setTrails(!trails)} aria-pressed={trails}>
                  Trails
                </button>
                <button className={`button secondary ${path ? "tl-on" : ""}`} onClick={() => setPath(!path)} aria-pressed={path}>
                  Path
                </button>
              </>
            )}
            {real && (
              <button className={`button secondary ${rawPixels ? "tl-on" : ""}`} onClick={() => setRawPixels(!rawPixels)} aria-pressed={rawPixels}>
                Raw pixels
              </button>
            )}
            {real && frames.some(f => f.maskSrc) && (
              <button className={`button secondary ${showMasks ? "tl-on" : ""}`} onClick={() => setShowMasks(!showMasks)} aria-pressed={showMasks}>
                Show masked pixels
              </button>
            )}
            {real && <button className="button secondary" onClick={() => setColourMap(m => m === "grey" ? "inferno" : "grey")}>Colour map: {colourMap === "grey" ? "Grey" : "Inferno"}</button>}
            <button className={`button secondary ${loop ? "tl-on" : ""}`} onClick={() => setLoop(!loop)} aria-pressed={loop}>
              Loop
            </button>
            {canRecord && (
              <button className="button secondary" onClick={onRecord} disabled={recording || !loaded}>
                {recording ? "Recording…" : "Export clip"}
              </button>
            )}
          </div>
        </div>
      </section>

      <section className="data-grid">
        <div className="glass chart-card wide tl-player">
          <div className="card-heading">
            <div>
              <small>SKY VIEW</small>
              <h3>
                {shortDate(cur.date).day} {shortDate(cur.date).year}
              </h3>
            </div>
            <span className="chip">
              Epoch {index + 1} / {frames.length}
            </span>
          </div>

          <div
            className={`tl-view ${rawPixels ? "raw" : "enhanced"}`}
            tabIndex={0}
            onKeyDown={onKey}
            aria-label="Timelapse image. Space plays or pauses, arrow keys step between observations."
          >
            {!loaded && <div className="tl-skeleton">Loading {frames.length} observations…</div>}
            <SkyView frames={frames} index={index} backdrop={backdrop} trails={trails} path={path} reduced={reduced} showMasks={showMasks} colourMap={colourMap} />
          </div>
          {real && frames.some(f => f.maskSrc) && <p className="mask-caption">Masked pixels are filled for display; analysis uses the masked data.</p>}

          <div className="tl-bar">
            <button className="tl-step" onClick={() => go(index - 1)} aria-label="Previous observation">
              <Chevron dir="left" />
            </button>
            <button className="tl-play" onClick={() => setPlaying((p) => !p)} aria-label={playing ? "Pause" : "Play"}>
              <PlayIcon playing={playing} />
            </button>
            <button className="tl-step" onClick={() => go(index + 1)} aria-label="Next observation">
              <Chevron dir="right" />
            </button>
            <div className="tl-scrub">
              <div className="tl-scrub-now" style={{ left: `${progress}%` }}>
                {shortDate(cur.date).day} {shortDate(cur.date).year}
              </div>
              <div className="tl-scrub-ticks" aria-hidden="true">
                {frames.map((f, i) => (
                  <i
                    key={f.date + i}
                    className={i === index ? "on" : i < index ? "past" : ""}
                    style={{ left: `${frames.length > 1 ? (i / (frames.length - 1)) * 100 : 50}%` }}
                  />
                ))}
              </div>
              <input
                type="range"
                min={0}
                max={frames.length - 1}
                value={index}
                style={{ ["--p" as string]: `${progress}%` }}
                onChange={(e) => go(Number(e.target.value))}
                aria-label="Observation date"
                aria-valuetext={cur.date}
              />
              <div className="tl-scrub-labels" aria-hidden="true">
                {scrubLabels.map((l) => (
                  <span key={l.i} style={{ left: `${frames.length > 1 ? (l.i / (frames.length - 1)) * 100 : 50}%` }}>
                    {l.text}
                  </span>
                ))}
              </div>
            </div>
            <div className="tl-speed" role="group" aria-label="Speed">
              {SPEEDS.map((sp) => (
                <button key={sp} className={sp === speed ? "active" : ""} onClick={() => setSpeed(sp)} aria-pressed={sp === speed}>
                  {sp}×
                </button>
              ))}
            </div>
          </div>
        </div>

        <div className="glass confidence-card tl-now-card">
          <small>THIS OBSERVATION</small>
          {hasObject ? (
            <>
              <div className="big-score tl-big" key={cur.date}>
                {stepShift ?? "0.0"}
                <sup>%</sup>
              </div>
              <h3>{stepShift === null ? "First image" : "Shift from previous"}</h3>
              <p>
                Stars line up between images taken in the same band. The circled source is the only one that changes
                position.
              </p>
            </>
          ) : (
            <>
              <div className="big-score tl-big" key={cur.date}>
                {cur.wavelengthUm.toFixed(2)}
                <sup>μm</sup>
              </div>
              <h3>Infrared colour of this image</h3>
              <p>
                SPHEREx takes each picture in a slightly different infrared colour. Stars can look brighter or fainter
                from one image to the next because of colour, not motion. Compare images of the same colour to find
                things that really move.
              </p>
            </>
          )}
          <div className="metric">
            <span>
              Through sequence <b>{Math.round(progress)}%</b>
            </span>
            <i>
              <em style={{ width: `${progress}%` }} />
            </i>
          </div>
          {[
            ["Date", cur.date],
            ["Wavelength", `${cur.wavelengthUm.toFixed(2)} μm`],
            ["Detector", String(cur.detector)],
            ["Gap to next", gapNext === null ? "—" : `${gapNext} days`],
          ].map(([k, v]) => (
            <div className="parameter" key={k}>
              <span>{k}</span>
              <b>{v}</b>
            </div>
          ))}
          <a
            className="button secondary tl-irsa"
            href={cur.sourceUrl ?? "https://irsa.ipac.caltech.edu/Missions/spherex.html"}
            target="_blank"
            rel="noreferrer"
          >
            {cur.sourceUrl ? "Open source file at IRSA ↗" : "About SPHEREx at IRSA ↗"}
          </a>
        </div>
      </section>

      <section className="stat-grid">
        {[
          ["OBSERVATIONS", String(frames.length), `${daysBetween(first.date, last.date)} days`],
          hasObject ? ["NET SHIFT", `${shift ?? "—"}%`, "of frame"] : ["DETECTORS", String(new Set(frames.map((f) => f.detector)).size), "SPHEREx cameras used"],
          ["BAND", bands.size === 1 ? `${[...bands][0]} μm` : `${Math.min(...frames.map((f) => f.wavelengthUm)).toFixed(1)}–${Math.max(...frames.map((f) => f.wavelengthUm)).toFixed(1)}`, bands.size === 1 ? "μm · same band" : `μm · ${bands.size} colours`],
          ["CADENCE", `${avgGap} d`, "average gap"],
        ].map((x) => (
          <div className="glass stat" key={x[0]}>
            <small>{x[0]}</small>
            <strong>{x[1]}</strong>
            <span>{x[2]}</span>
          </div>
        ))}
      </section>

      <section className="glass parameters tl-log">
        <div className="card-heading">
          <div>
            <small>OBSERVATION LOG</small>
            <h3>All epochs</h3>
          </div>
          {hasObject && <div className="tl-legend">
            <span>
              <i className="l-now" /> Now
            </span>
            <span>
              <i className="l-past" /> Earlier
            </span>
            <span>
              <i className="l-path" /> Path
            </span>
          </div>}
        </div>
        <div className="tl-log-head" aria-hidden="true">
          <span />
          <span>Date</span>
          <span>Wavelength</span>
          <span>Detector</span>
          <span>Gap to next</span>
          <span />
        </div>
        {frames.map((f, i) => ({ f, i })).filter(({ i }) => showAllLog || i < 8 || i === index).map(({ f, i }) => (
          <button
            key={f.date + i}
            className={`tl-log-row ${i === index ? "selected" : ""}`}
            onClick={() => go(i)}
            aria-pressed={i === index}
          >
            <div className="tl-log-thumb">
              <SkyView frames={frames} index={i} backdrop={backdrop} trails={false} path={false} reduced compact colourMap={colourMap} />
            </div>
            <b>
              {shortDate(f.date).day} {shortDate(f.date).year}
            </b>
            <span>{f.wavelengthUm.toFixed(2)} μm</span>
            <span>{f.detector}</span>
            <span>{i < frames.length - 1 ? `${daysBetween(f.date, frames[i + 1].date)} d` : "—"}</span>
            <span>{i === index ? <em className="chip success">Showing</em> : null}</span>
          </button>
        ))}
        {frames.length > 8 && (
          <button className="text-link tl-log-more" onClick={() => setShowAllLog(!showAllLog)}>
            {showAllLog ? "Show fewer" : `Show all ${frames.length} observations`}
          </button>
        )}
      </section>
    </main>
  );
}
