import { useEffect, useMemo, useState } from "react";
import type { Field, Frame } from "../contract";
import { imageUrl } from "../data/loader";
import { DifferenceImage } from "../viewer/DifferenceImage";
import { daysApart, niceDate, pairTrust, type Trust } from "./fields";

/**
 * Compare: CAN I TRUST THIS COMPARISON? Two images side by side, a verdict,
 * and three ways to look for real change (blink, slider, difference).
 */

const VERDICT: Record<Trust, { title: string; text: string }> = {
  high: {
    title: "Safe to compare",
    text: "Both images were taken in almost the same infrared colour. If something changed between them, it is probably real.",
  },
  medium: {
    title: "Compare with care",
    text: "The colours are a little different. Small brightness changes may come from colour, not from motion.",
  },
  low: {
    title: "Don't trust this comparison",
    text: "These images are in very different infrared colours. Stars change brightness with colour, so most differences here are not real motion.",
  },
};

function Pane({ field, frame, label, frames, onPick }: { field: Field; frame: Frame; label: string; frames: Frame[]; onPick: (id: string) => void }) {
  return (
    <div className="cp-col">
      <div className="glass cp-image">
        <span className="cp-tag">{label}</span>
        <img src={imageUrl(field.field_id, frame.png)} alt={`${label}: sky image taken ${niceDate(frame.obs_time_utc)}`} />
        <span className="cp-date">{niceDate(frame.obs_time_utc)}</span>
      </div>
      <label className="cp-pick">
        <span>Choose image {label}</span>
        <select value={frame.id} onChange={(e) => onPick(e.target.value)}>
          {frames.map((f) => (
            <option key={f.id} value={f.id}>
              {niceDate(f.obs_time_utc)} · {f.wavelength_um.toFixed(2)} μm
            </option>
          ))}
        </select>
      </label>
    </div>
  );
}

export function ComparePairs({ field }: { field: Field }) {
  const frames = useMemo(() => [...field.frames].sort((a, b) => a.mjd - b.mjd), [field]);
  const byId = useMemo(() => new Map(frames.map((f) => [f.id, f])), [frames]);
  const sortedPairs = useMemo(() => {
    const rank = { high: 0, medium: 1, low: 2 } as const;
    return [...field.pairs].sort((a, b) => rank[a.trust] - rank[b.trust] || b.dt_days - a.dt_days);
  }, [field]);
  const first = sortedPairs[0];
  const [aId, setA] = useState(first?.a ?? frames[0]?.id);
  const [bId, setB] = useState(first?.b ?? frames[frames.length - 1]?.id);
  const [view, setView] = useState<"blink" | "slider" | "diff">("blink");
  const [showB, setShowB] = useState(false);
  const [split, setSplit] = useState(50);
  const [blinking, setBlinking] = useState(true);

  useEffect(() => {
    setA(first?.a ?? frames[0]?.id);
    setB(first?.b ?? frames[frames.length - 1]?.id);
  }, [field.field_id]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (view !== "blink" || !blinking) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const id = window.setInterval(() => setShowB((v) => !v), 700);
    return () => window.clearInterval(id);
  }, [view, blinking]);

  const a = byId.get(aId) ?? frames[0];
  const b = byId.get(bId) ?? frames[frames.length - 1];
  if (!a || !b) return <p role="status">This field has no images to compare.</p>;
  const verdict = pairTrust(a, b, field.pairs);
  const doc = field.pairs.find((p) => (p.a === a.id && p.b === b.id) || (p.a === b.id && p.b === a.id));
  const v = VERDICT[verdict.trust];

  const rows: [string, string, string, boolean?][] = [
    ["Date", niceDate(a.obs_time_utc), niceDate(b.obs_time_utc)],
    ["Infrared colour", `${a.wavelength_um.toFixed(2)} μm`, `${b.wavelength_um.toFixed(2)} μm`, verdict.trust !== "high"],
    ["Detector", String(a.detector), String(b.detector)],
    ["Survey pass", String(a.survey_pass), String(b.survey_pass)],
    ["Bad pixels", `${(a.bad_pixel_fraction * 100).toFixed(1)}%`, `${(b.bad_pixel_fraction * 100).toFixed(1)}%`],
  ];

  return (
    <div className="compare-pairs">
      <div className={`glass cp-verdict ${verdict.trust}`} role="status">
        <div className="cp-verdict-badge">
          <small>CAN YOU COMPARE THESE?</small>
          <b>{v.title}</b>
        </div>
        <p>{v.text}</p>
        <div className="cp-verdict-nums">
          <div>
            <span>Colour difference</span>
            <b>{(verdict.dl * 100).toFixed(verdict.dl < 0.01 ? 2 : 1)}%</b>
          </div>
          <div>
            <span>Time between</span>
            <b>{Math.round(daysApart(a, b))} days</b>
          </div>
          <div>
            <span>Source</span>
            <b>{verdict.documented ? "Pipeline pair" : "Your choice"}</b>
          </div>
        </div>
      </div>

      <div className="cp-grid">
        <Pane field={field} frame={a} label="A" frames={frames} onPick={setA} />

        <div className="glass cp-merge">
          <div className="cp-tabs" role="tablist">
            {([
              ["blink", "Blink"],
              ["slider", "Slider"],
              ["diff", "Difference"],
            ] as const).map(([id, label]) => (
              <button key={id} role="tab" aria-selected={view === id} className={view === id ? "on" : ""} onClick={() => setView(id)}>
                {label}
              </button>
            ))}
          </div>
          <div className="cp-merge-view">
            {view === "blink" && (
              <>
                <img src={imageUrl(field.field_id, (showB ? b : a).png)} alt={`Image ${showB ? "B" : "A"}`} />
                <span className="cp-date">{showB ? "B" : "A"} · {niceDate((showB ? b : a).obs_time_utc)}</span>
              </>
            )}
            {view === "slider" && (
              <>
                <img src={imageUrl(field.field_id, b.png)} alt="Image B" />
                <img src={imageUrl(field.field_id, a.png)} alt="Image A" className="cp-top" style={{ clipPath: `inset(0 ${100 - split}% 0 0)` }} />
                <span className="cp-split" style={{ left: `${split}%` }} />
              </>
            )}
            {view === "diff" && (
              <div className="cp-diff">
                <DifferenceImage key={a.id + b.id} fieldId={field.field_id} a={a} b={b} path={doc?.diff_png} />
              </div>
            )}
          </div>
          {view === "blink" && (
            <button className="button secondary cp-small" onClick={() => setBlinking(!blinking)}>
              {blinking ? "Pause blinking" : "Blink"}
            </button>
          )}
          {view === "slider" && (
            <input type="range" min={0} max={100} value={split} onChange={(e) => setSplit(Number(e.target.value))} aria-label="Slider between A and B" />
          )}
          <p className="cp-hint">
            {view === "blink" && "The images switch back and forth. Anything that jumps is different between the dates."}
            {view === "slider" && "Drag to wipe from image A to image B."}
            {view === "diff" && "Bright spots show where the images differ. Dark means no change."}
          </p>
        </div>

        <Pane field={field} frame={b} label="B" frames={frames} onPick={setB} />
      </div>

      <div className="glass cp-table">
        <div className="cp-row head">
          <span />
          <b>Image A</b>
          <b>Image B</b>
        </div>
        {rows.map(([k, va, vb, warn]) => (
          <div className={`cp-row ${warn ? "warn" : ""}`} key={k}>
            <span>{k}</span>
            <b>{va}</b>
            <b>{vb}</b>
          </div>
        ))}
        <div className="cp-row links">
          <span>Archive</span>
          <a href={a.source_url} target="_blank" rel="noreferrer">Open A at IRSA ↗</a>
          <a href={b.source_url} target="_blank" rel="noreferrer">Open B at IRSA ↗</a>
        </div>
      </div>

      <div className="glass cp-pairs">
        <div className="card-heading">
          <div>
            <small>SUGGESTED PAIRS</small>
            <h3>Pairs the pipeline checked</h3>
          </div>
        </div>
        <div className="cp-pair-list">
          {sortedPairs.map((p) => {
            const pa = byId.get(p.a);
            const pb = byId.get(p.b);
            if (!pa || !pb) return null;
            const on = (p.a === a.id && p.b === b.id) || (p.a === b.id && p.b === a.id);
            return (
              <button key={p.a + p.b} className={`cp-pair ${on ? "on" : ""}`} onClick={() => { setA(p.a); setB(p.b); }}>
                <span className={`cp-dot ${p.trust}`} />
                <b>{niceDate(pa.obs_time_utc)} → {niceDate(pb.obs_time_utc)}</b>
                <small>{Math.round(p.dt_days)} days · colour diff {(p.dlambda_frac * 100).toFixed(p.dlambda_frac < 0.01 ? 2 : 1)}%</small>
                <em className={p.trust}>{p.trust === "high" ? "Safe" : p.trust === "medium" ? "Care" : "Don't trust"}</em>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
