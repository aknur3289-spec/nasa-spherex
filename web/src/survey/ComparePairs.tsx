import { useEffect, useMemo, useRef, useState } from "react";
import type React from "react";
import type { Field, Frame } from "../contract";
import { imageUrl } from "../data/loader";
import { DifferenceImage } from "../viewer/DifferenceImage";
import { NormImg } from "./NormImg";
import { daysApart, niceDate, pairTrust, type Trust } from "./fields";
import { MappedImage, type ColourMap } from "./MappedImage";

/**
 * Compare — "Did anything move?"
 * A guided three-step page: 1) pick two dates, 2) look for a change in one big
 * viewer, 3) read a plain-language check of whether the comparison is fair.
 */

type View = "flip" | "swipe" | "diff";

const VIEWS: { id: View; label: string; hint: string }[] = [
  { id: "flip", label: "Flip", hint: "The two dates swap every second. Stars stay still; anything that jumps has changed." },
  { id: "swipe", label: "Swipe", hint: "Drag the handle across the picture to wipe from the first date to the second." },
  { id: "diff", label: "Changes only", hint: "Whatever stayed the same fades out. Spots that stand out are what changed between the dates." },
];

const VERDICT: Record<Trust, { title: string; text: string }> = {
  high: { title: "Fair comparison", text: "If you see something move here, it is probably real." },
  medium: { title: "Use with care", text: "Small brightness changes may come from the colour difference, not from motion." },
  low: { title: "Not a fair comparison", text: "Most differences here come from the colour, not from anything moving. Pick a green pair instead." },
};

const pct = (x: number) => `${(x * 100).toFixed(x < 0.01 ? 2 : 1)}%`;

function Check({ ok, title, detail }: { ok: "yes" | "warn" | "no"; title: string; detail: string }) {
  return (
    <li className={`cq-check ${ok}`}>
      <i aria-hidden>{ok === "yes" ? "✓" : ok === "warn" ? "!" : "✕"}</i>
      <div>
        <b>{title}</b>
        <span>{detail}</span>
      </div>
    </li>
  );
}

export function ComparePairs({ field }: { field: Field }) {
  const frames = useMemo(() => [...field.frames].sort((a, b) => a.mjd - b.mjd), [field]);
  const byId = useMemo(() => new Map(frames.map((f) => [f.id, f])), [frames]);
  const pairs = useMemo(() => {
    const rank = { high: 0, medium: 1, low: 2 } as const;
    return [...field.pairs]
      .filter((p) => byId.has(p.a) && byId.has(p.b))
      .sort((a, b) => rank[a.trust] - rank[b.trust] || b.dt_days - a.dt_days);
  }, [field, byId]);
  const good = pairs.filter((p) => p.trust !== "low");
  const risky = pairs.filter((p) => p.trust === "low");

  const first = pairs[0];
  const [aId, setA] = useState(first?.a ?? frames[0]?.id);
  const [bId, setB] = useState(first?.b ?? frames[frames.length - 1]?.id);
  const [view, setView] = useState<View>("flip");
  const [showB, setShowB] = useState(false);
  const [playing, setPlaying] = useState(true);
  const [split, setSplit] = useState(50);
  const dragRef = useRef(false);
  const swipeTo = (e: React.PointerEvent<HTMLDivElement>) => {
    const r = e.currentTarget.getBoundingClientRect();
    setSplit(Math.max(0, Math.min(100, ((e.clientX - r.left) / r.width) * 100)));
  };
  const [showRisky, setShowRisky] = useState(false);
  const [showDetails, setShowDetails] = useState(false);
  const [showMasks, setShowMasks] = useState(false);
  const [colourMap, setColourMap] = useState<ColourMap>("grey");

  useEffect(() => {
    setA(first?.a ?? frames[0]?.id);
    setB(first?.b ?? frames[frames.length - 1]?.id);
  }, [field.field_id]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (view !== "flip" || !playing) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const id = window.setInterval(() => setShowB((v) => !v), 900);
    return () => window.clearInterval(id);
  }, [view, playing]);

  const a0 = byId.get(aId) ?? frames[0];
  const b0 = byId.get(bId) ?? frames[frames.length - 1];
  if (!a0 || !b0) return <p role="status">This field has no images to compare.</p>;
  // Always show the earlier date first.
  const [a, b] = a0.mjd <= b0.mjd ? [a0, b0] : [b0, a0];
  const verdict = pairTrust(a, b, field.pairs);
  const doc = field.pairs.find((p) => (p.a === a.id && p.b === b.id) || (p.a === b.id && p.b === a.id));
  const v = VERDICT[verdict.trust];
  const days = Math.round(daysApart(a, b));
  const bad = Math.max(a.bad_pixel_fraction, b.bad_pixel_fraction);
  const current = view === "flip" ? (showB ? "b" : "a") : null;
  const hint = VIEWS.find((x) => x.id === view)!.hint;

  const pick = (pa: string, pb: string) => {
    setA(pa);
    setB(pb);
    setShowB(false);
  };

  const PairButton = ({ p }: { p: (typeof pairs)[number] }) => {
    const pa = byId.get(p.a)!;
    const pb = byId.get(p.b)!;
    const [x, y] = pa.mjd <= pb.mjd ? [pa, pb] : [pb, pa];
    const on = (p.a === a.id && p.b === b.id) || (p.a === b.id && p.b === a.id);
    return (
      <button className={`cq-pair ${p.trust} ${on ? "on" : ""}`} onClick={() => pick(p.a, p.b)} aria-pressed={on}>
        <span className="cq-pair-thumbs" aria-hidden>
          <MappedImage src={imageUrl(field.field_id, x.png)} alt="" map={colourMap} />
          <MappedImage src={imageUrl(field.field_id, y.png)} alt="" map={colourMap} />
        </span>
        <span className="cq-pair-text">
          <b>{niceDate(x.obs_time_utc)}</b>
          <b>→ {niceDate(y.obs_time_utc)}</b>
          <small>{Math.round(p.dt_days)} days apart</small>
        </span>
        <i className={`cq-dot ${p.trust}`} aria-label={p.trust === "high" ? "fair" : p.trust === "medium" ? "use with care" : "not fair"} />
      </button>
    );
  };

  return (
    <div className="compare-quest">
      {good.length === 0 && (
        <div className="glass cq-nofair" role="note">
          <b>No fair pairs in this field.</b> All its images were taken too close in time or in different infrared colours,
          so differences here mostly come from colour, not motion. Use Timelapse for this field, or pick M101, NEP or the
          Ecliptic field to compare fair pairs.
        </div>
      )}
      <div className="glass cq-intro">
        <div>
          <small>COMPARE TWO DATES</small>
          <h2>Did anything move?</h2>
          <p>
            SPHEREx photographs the same patch of sky again months later. Stars stay put. A nearby planet, asteroid or comet
            shifts. Put two dates on top of each other and look for the dot that moved.
          </p>
        </div>
        <ol className="cq-steps" aria-label="How it works">
          <li><b>1</b>Pick two dates</li>
          <li><b>2</b>Look for a change</li>
          <li><b>3</b>Check it is fair</li>
        </ol>
      </div>

      <div className="cq-grid">
        {/* STEP 1 */}
        <aside className="glass cq-panel cq-pick">
          <h3><b>1</b>Pick two dates</h3>
          <p className="cq-sub">Green pairs were taken in the same infrared colour, so they are fair to compare.</p>
          <div className="cq-pair-list">
            {good.map((p) => <PairButton key={p.a + p.b} p={p} />)}
          </div>
          {risky.length > 0 && (
            <>
              <button className="cq-link" onClick={() => setShowRisky(!showRisky)} aria-expanded={showRisky}>
                {showRisky ? "Hide" : "Show"} {risky.length} unfair pairs (different colours)
              </button>
              {showRisky && <div className="cq-pair-list">{risky.map((p) => <PairButton key={p.a + p.b} p={p} />)}</div>}
            </>
          )}
        </aside>

        {/* STEP 2 */}
        <section className="glass cq-panel cq-look">
          <div className="cq-look-head">
            <h3><b>2</b>Look for a change</h3>
            <div className="cq-seg" role="tablist" aria-label="How to compare">
              {VIEWS.map((x) => (
                <button key={x.id} role="tab" aria-selected={view === x.id} className={view === x.id ? "on" : ""} onClick={() => setView(x.id)}>
                  {x.label}
                </button>
              ))}
            </div>
          </div>

          <div className="cq-dates">
            <span className={`cq-date a ${current === "a" ? "on" : ""}`}><i>A</i>{niceDate(a.obs_time_utc)}</span>
            <span className="cq-gap">{days} days later</span>
            <span className={`cq-date b ${current === "b" ? "on" : ""}`}><i>B</i>{niceDate(b.obs_time_utc)}</span>
          </div>

          <div className="cq-stage"
            onPointerDown={(e) => { if (view !== "swipe") return; e.preventDefault(); dragRef.current = true; e.currentTarget.setPointerCapture?.(e.pointerId); swipeTo(e); }}
            onPointerMove={(e) => { if (view === "swipe" && dragRef.current) swipeTo(e); }}
            onPointerUp={() => { dragRef.current = false; }}
            onPointerCancel={() => { dragRef.current = false; }}
            style={view === "swipe" ? { cursor: "ew-resize", touchAction: "none" } : undefined}>
            {view === "flip" && (
              <>
                <MappedImage src={imageUrl(field.field_id, a.png)} alt={`Sky on ${niceDate(a.obs_time_utc)}`} map={colourMap} style={{ opacity: showB ? 0 : 1 }} />
                <MappedImage src={imageUrl(field.field_id, b.png)} alt={`Sky on ${niceDate(b.obs_time_utc)}`} map={colourMap} className="cq-top" style={{ opacity: showB ? 1 : 0 }} />
                {showMasks && (showB ? b : a).mask_png && <img className="cq-mask" src={imageUrl(field.field_id, (showB ? b : a).mask_png!)} alt="" />}
                <span className={`cq-badge ${showB ? "b" : "a"}`}>{showB ? "B" : "A"} · {niceDate((showB ? b : a).obs_time_utc)}</span>
              </>
            )}
            {view === "swipe" && (
              <>
                <MappedImage src={imageUrl(field.field_id, b.png)} alt={`Sky on ${niceDate(b.obs_time_utc)}`} map={colourMap} />
                <MappedImage src={imageUrl(field.field_id, a.png)} alt={`Sky on ${niceDate(a.obs_time_utc)}`} map={colourMap} className="cq-top" style={{ clipPath: `inset(0 ${100 - split}% 0 0)` }} />
                {showMasks && b.mask_png && <img className="cq-mask" src={imageUrl(field.field_id, b.mask_png)} alt="" />}
                {showMasks && a.mask_png && <img className="cq-mask" src={imageUrl(field.field_id, a.mask_png)} alt="" style={{ clipPath: `inset(0 ${100 - split}% 0 0)` }} />}
                <span className="cq-split" style={{ left: `${split}%` }}><i>⟷</i></span>
                <span className="cq-badge a corner-l">A</span>
                <span className="cq-badge b corner-r">B</span>
                <input className="cq-swipe sr-only-range" type="range" min={0} max={100} value={split} onChange={(e) => setSplit(Number(e.target.value))} aria-label="Swipe between date A and date B" />
              </>
            )}
            {view === "diff" && (
              <div className="cq-diff">
                <DifferenceImage key={a.id + b.id} fieldId={field.field_id} a={a} b={b} path={doc?.diff_png} />
                {showMasks && a.mask_png && <img className="cq-mask" src={imageUrl(field.field_id, a.mask_png)} alt="" />}
                {showMasks && b.mask_png && <img className="cq-mask" src={imageUrl(field.field_id, b.mask_png)} alt="" />}
              </div>
            )}
          </div>

          <div className="cq-under">
            <p>{hint}</p>
            {view === "flip" && (
              <button className="button secondary cq-play" onClick={() => setPlaying(!playing)}>
                {playing ? "❚❚ Pause" : "▶ Play"}
              </button>
            )}
            {view === "flip" && !playing && (
              <button className="button secondary cq-play" onClick={() => setShowB(!showB)}>Show {showB ? "A" : "B"}</button>
            )}
          </div>
          {(a.mask_png || b.mask_png) && <>
            <button className={`button secondary ${showMasks ? "tl-on" : ""}`} onClick={() => setShowMasks(!showMasks)} aria-pressed={showMasks}>Show masked pixels</button>
            <p className="mask-caption">Masked pixels are filled for display; analysis uses the masked data.</p>
          </>}
          <button className="button secondary" onClick={() => setColourMap(m => m === "grey" ? "inferno" : "grey")}>Colour map: {colourMap === "grey" ? "Grey" : "Inferno"}</button>
          <p className="mask-caption">One pixel = 6.15″ — SPHEREx maps the whole sky in 102 infrared colours, it is built for spectra, not sharp portraits.</p>
          <p className="cq-legend">
            <i className="sq" /> Black squares are masked detector pixels, not objects. <i className="dot" /> Each white dot is a star or galaxy.
          </p>
        </section>

        {/* STEP 3 */}
        <aside className={`glass cq-panel cq-check-panel ${verdict.trust}`}>
          <h3><b>3</b>Is it fair?</h3>
          <div className="cq-verdict" role="status">
            <strong>{v.title}</strong>
            <p>{v.text}</p>
          </div>
          <ul className="cq-checks">
            <Check
              ok={verdict.trust === "high" ? "yes" : verdict.trust === "medium" ? "warn" : "no"}
              title="Same infrared colour"
              detail={`${a.wavelength_um.toFixed(2)} μm vs ${b.wavelength_um.toFixed(2)} μm, ${pct(verdict.dl)} apart`}
            />
            <Check
              ok={days >= 7 ? "yes" : "warn"}
              title="Enough time to move"
              detail={days >= 7 ? `${days} days: a planet would shift visibly` : `Only ${days} days: slow objects barely move`}
            />
            <Check
              ok={bad < 0.1 ? "yes" : "warn"}
              title="Few masked pixels"
              detail={`${pct(a.bad_pixel_fraction)} and ${pct(b.bad_pixel_fraction)} of the picture`}
            />
          </ul>
          <div className="cq-tip">
            <b>What to look for</b>
            <span>A dot that is in A but sits a little to the side in B. If every dot stays still, nothing nearby moved here.</span>
          </div>
        </aside>
      </div>

      <div className="glass cq-details">
        <button className="cq-details-toggle" onClick={() => setShowDetails(!showDetails)} aria-expanded={showDetails}>
          <span>
            <b>Details for researchers</b>
            <small>Choose any two images, detector, survey pass, archive links</small>
          </span>
          <i aria-hidden>{showDetails ? "−" : "+"}</i>
        </button>
        {showDetails && (
          <div className="cq-details-body">
            <div className="cq-selects">
              {([["A", a, (id: string) => pick(id, b.id)], ["B", b, (id: string) => pick(a.id, id)]] as const).map(([label, f, on]) => (
                <label key={label}>
                  <span>Image {label}</span>
                  <select value={f.id} onChange={(e) => on(e.target.value)}>
                    {frames.map((x) => (
                      <option key={x.id} value={x.id}>{niceDate(x.obs_time_utc)} · {x.wavelength_um.toFixed(2)} μm</option>
                    ))}
                  </select>
                </label>
              ))}
            </div>
            <table className="cq-table">
              <thead>
                <tr><th /><th>A</th><th>B</th></tr>
              </thead>
              <tbody>
                <tr><td>Date (UTC)</td><td>{a.obs_time_utc.slice(0, 16).replace("T", " ")}</td><td>{b.obs_time_utc.slice(0, 16).replace("T", " ")}</td></tr>
                <tr><td>Wavelength</td><td>{a.wavelength_um.toFixed(3)} μm</td><td>{b.wavelength_um.toFixed(3)} μm</td></tr>
                <tr><td>Detector</td><td>{a.detector}</td><td>{b.detector}</td></tr>
                <tr><td>Survey pass</td><td>{a.survey_pass}</td><td>{b.survey_pass}</td></tr>
                <tr><td>Masked pixels</td><td>{pct(a.bad_pixel_fraction)}</td><td>{pct(b.bad_pixel_fraction)}</td></tr>
                <tr><td>Pair source</td><td colSpan={2}>{verdict.documented ? "Checked by the pipeline" : "Your own choice (not checked by the pipeline)"}</td></tr>
                <tr><td>Archive</td><td><a href={a.source_url} target="_blank" rel="noreferrer">IRSA ↗</a></td><td><a href={b.source_url} target="_blank" rel="noreferrer">IRSA ↗</a></td></tr>
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
