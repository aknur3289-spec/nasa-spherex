import { useEffect, useMemo, useRef, useState } from "react";
import type { Field } from "../contract";
import { Timelapse } from "../survey/Timelapse";
import { buildField, fetchFrame, renderPng, type Exposure, type LiveFrame } from "./liveData";

type TrackExposure = Exposure & { ra: number; dec: number; delta_au: number };
type Rendered = LiveFrame & { src: string; lo: number; hi: number; delta_au: number };
const MAX = 40;

/**
 * Follow a known moving object: JPL Horizons gives its position at every SPHEREx exposure time,
 * and each real SPHEREx image is cut around that position. The object stays in the ring and the
 * fixed stars stream past — its motion against the sky.
 */
export function TrackField({ name, backdrop, onBack }: { name: string; backdrop: string; onBack: () => void }) {
  const [phase, setPhase] = useState<"search" | "frames" | "done" | "error">("search");
  const [error, setError] = useState("");
  const [target, setTarget] = useState(name);
  const [chosen, setChosen] = useState<TrackExposure[]>([]);
  const [total, setTotal] = useState(0);
  const [frames, setFrames] = useState<Rendered[]>([]);
  const [failed, setFailed] = useState(0);
  const [field, setField] = useState<Field>();
  const [attempt, setAttempt] = useState(0);
  const ref = useRef<Rendered[]>([]);

  useEffect(() => {
    const ctl = new AbortController();
    ref.current = [];
    setFrames([]); setFailed(0); setField(undefined); setError(""); setPhase("search");
    (async () => {
      try {
        // Saved snapshot for preset objects (real frames saved from IRSA; works when IRSA is down).
        try {
          const sr = await fetch(`/data/live/track-${encodeURIComponent(name.toLowerCase())}.json`, { signal: ctl.signal });
          if (sr.ok && (sr.headers.get("content-type") ?? "").includes("json")) {
            const snap = await sr.json();
            if (Array.isArray(snap.frames) && snap.frames.length >= 2) {
              setTarget(snap.target || name);
              setTotal(snap.total);
              ref.current = snap.frames.map((f: LiveFrame & { delta_au: number }) => ({ ...f, ...renderPng(f) }));
              setFrames(ref.current);
              setField(buildField(snap.frames[0].obj_ra ?? 0, snap.frames[0].obj_dec ?? 0, snap.target || name, ref.current));
              setPhase("done");
              return;
            }
          }
        } catch { /* fall through to the live path */ }
        const r = await fetch(`/api/track?name=${encodeURIComponent(name)}`, { signal: ctl.signal });
        const body = await r.json().catch(() => ({}));
        if (!r.ok) throw new Error(body.error || `HTTP ${r.status}`);
        setTarget(body.target || name);
        const all = (body.exposures ?? []) as TrackExposure[];
        setTotal(all.length);
        if (!all.length) { setPhase("error"); setError(body.note || "SPHEREx has no images of this object in its first two sky surveys."); return; }
        const pick = all.length <= MAX ? all : Array.from({ length: MAX }, (_, i) => all[Math.floor((i * all.length) / MAX)]);
        setChosen(pick);
        setPhase("frames");
        let next = 0;
        await Promise.all(Array.from({ length: 6 }, async () => {
          while (next < pick.length && !ctl.signal.aborted) {
            const e = pick[next++];
            try {
              const f = await fetchFrame(e, e.ra, e.dec, ctl.signal);
              if (!f.center_inside || f.bad_pixel_fraction > 0.6) { setFailed((n) => n + 1); continue; }
              ref.current = [...ref.current, { ...f, ...renderPng(f), delta_au: e.delta_au }];
              setFrames(ref.current);
            } catch { if (!ctl.signal.aborted) setFailed((n) => n + 1); }
          }
        }));
        if (ctl.signal.aborted) return;
        if (ref.current.length < 2) { setPhase("error"); setError("IRSA did not return enough usable images right now."); return; }
        setField(buildField(pick[0].ra, pick[0].dec, body.target || name, ref.current));
        setPhase("done");
      } catch (e) {
        if (!ctl.signal.aborted) { setPhase("error"); setError((e as Error).message); }
      }
    })();
    return () => ctl.abort();
  }, [name, attempt]);

  const timeline = useMemo(() => field ? [...field.frames].sort((a, b) => a.mjd - b.mjd).map((f) => ({
    date: f.obs_time_utc.slice(0, 10), wavelengthUm: f.wavelength_um, detector: f.detector, src: f.png, sourceUrl: f.source_url,
    targetRadec: field.center, center: field.center, widthPx: f.width_px, heightPx: f.height_px,
  })) : [], [field]);
  const dist = useMemo(() => {
    const d = frames.map((f) => f.delta_au).filter(Number.isFinite);
    return d.length ? [Math.min(...d), Math.max(...d)] : undefined;
  }, [frames]);
  const done = frames.length + failed;

  return (
    <main className="content-screen survey-observations enhanced">
      <div className="obs-head">
        <div>
          <small>FOLLOW A MOVING OBJECT · NASA JPL + REAL SPHEREx DATA</small>
          <h1>{target}</h1>
          <p>Each real SPHEREx image is cut around the object's position from NASA JPL Horizons at that moment.</p>
        </div>
        <button className="button secondary" onClick={onBack}>← Back</button>
      </div>
      {!field && <div className="glass live-progress" role="status" aria-live="polite">
        {phase === "search" && <p>Asking NASA JPL where {name} was, and IRSA which SPHEREx images caught it…</p>}
        {phase === "frames" && <>
          <p>SPHEREx caught {target} in <b>{total}</b> images. Downloading <b>{chosen.length}</b> of them: <b>{done}</b> / {chosen.length}
            {failed > 0 && <> ({failed} skipped)</>}.</p>
          <div className="live-bar"><i style={{ width: `${(100 * done) / Math.max(1, chosen.length)}%` }} /></div>
          {frames.length >= 6 && <button className="button secondary" onClick={() => setField(buildField(chosen[0].ra, chosen[0].dec, target, ref.current))}>Show the {frames.length} images loaded so far</button>}
        </>}
        {phase === "error" && <>
          <p role="alert">{error}</p>
          <p><button className="button secondary" onClick={() => setAttempt((n) => n + 1)}>Try again</button></p>
        </>}
      </div>}
      {field && <>
        <div className="glass look-box">
          <small>WHAT TO LOOK AT</small>
          <p><b>The green ring is {target}.</b> It stays in the middle because every image is centred on where NASA JPL says it was;
            the stars stream past instead — that is the object moving across the sky.
            {dist && <> Its distance from Earth during these images: {dist[0].toFixed(2)}–{dist[1].toFixed(2)} AU (JPL).</>}
            {" "}Very bright planets (Mars, Jupiter, Saturn) saturate SPHEREx's detectors, so they may appear as a masked blob.</p>
        </div>
        <Timelapse key={"tr" + field.frames.length} frames={timeline} synthetic={false} title={target} backdrop={backdrop} onBack={onBack} />
        <p className="live-note">{field.frames.length} real SPHEREx images, {field.frames[0]?.obs_time_utc.slice(0, 10)} → {field.frames[field.frames.length - 1]?.obs_time_utc.slice(0, 10)}. Positions: NASA JPL Horizons (geocentric). Images: NASA/IPAC IRSA.</p>
      </>}
    </main>
  );
}
