import { useEffect, useMemo, useRef, useState } from "react";
import type { Field } from "../contract";
import { Timelapse } from "../survey/Timelapse";
import { ComparePairs } from "../survey/ComparePairs";
import { fmtDec, fmtRa } from "../survey/fields";
import { buildField, fetchFrame, listExposures, pairChange, pickExposures, renderPng, sameColourGroup, type Exposure, type LiveFrame } from "./liveData";

type Rendered = LiveFrame & { src: string; lo: number; hi: number };
type Phase = "search" | "frames" | "done" | "error";

/**
 * Live mode: any point on the sky. The server asks IRSA for every SPHEREx exposure covering the
 * point, downloads real L2 cutouts, masks and reprojects them; the browser renders them and builds
 * honest pairs with the same rules as our offline fields.
 */
export function LiveField({ ra, dec, label, backdrop, onBack }: {
  ra: number; dec: number; label: string; backdrop: string; onBack: () => void;
}) {
  const [phase, setPhase] = useState<Phase>("search");
  const [error, setError] = useState("");
  const [total, setTotal] = useState(0);
  const [chosen, setChosen] = useState<Exposure[]>([]);
  const [frames, setFrames] = useState<Rendered[]>([]);
  const [failed, setFailed] = useState(0);
  const [field, setField] = useState<Field>();
  const [tab, setTab] = useState<"timelapse" | "compare">("timelapse");
  const framesRef = useRef<Rendered[]>([]);

  useEffect(() => {
    const ctl = new AbortController();
    framesRef.current = [];
    setFrames([]); setFailed(0); setField(undefined); setError(""); setPhase("search");
    (async () => {
      try {
        const all = await listExposures(ra, dec, ctl.signal);
        setTotal(all.length);
        if (!all.length) { setPhase("error"); setError("IRSA has no SPHEREx images covering this point yet."); return; }
        const pick = pickExposures(all);
        setChosen(pick);
        setPhase("frames");
        let next = 0;
        const worker = async () => {
          while (next < pick.length && !ctl.signal.aborted) {
            const e = pick[next++];
            try {
              const f = await fetchFrame(e, ra, dec, ctl.signal);
              if (!f.center_inside || f.bad_pixel_fraction > 0.6) { setFailed((n) => n + 1); continue; }
              const r = { ...f, ...renderPng(f) };
              framesRef.current = [...framesRef.current, r];
              setFrames(framesRef.current);
            } catch {
              if (!ctl.signal.aborted) setFailed((n) => n + 1);
            }
          }
        };
        await Promise.all(Array.from({ length: 6 }, worker));
        if (ctl.signal.aborted) return;
        if (framesRef.current.length < 2) { setPhase("error"); setError("IRSA did not return enough usable images right now. Try again in a minute."); return; }
        setField(buildField(ra, dec, label, framesRef.current));
        setPhase("done");
      } catch (e) {
        if (!ctl.signal.aborted) { setPhase("error"); setError((e as Error).message); }
      }
    })();
    return () => ctl.abort();
  }, [ra, dec, label]);

  const showNow = () => setField(buildField(ra, dec, label, framesRef.current));
  const [allColours, setAllColours] = useState(false);
  const colour = useMemo(() => field ? sameColourGroup(field.frames) : undefined, [field]);
  const timeline = useMemo(() => {
    if (!field) return [];
    const use = !allColours && colour && colour.group.length >= 4 ? colour.group : field.frames;
    return [...use].sort((a, b) => a.mjd - b.mjd).map((f) => ({
      date: f.obs_time_utc.slice(0, 10), wavelengthUm: f.wavelength_um, detector: f.detector, src: f.png, sourceUrl: f.source_url,
      // "Your point" marker at the image centre.
      targetRadec: { ra_deg: ra, dec_deg: dec }, center: { ra_deg: ra, dec_deg: dec }, widthPx: f.width_px, heightPx: f.height_px,
    }));
  }, [field, allColours, colour, ra, dec]);
  const honest = field?.pairs.filter((p) => p.trust === "high").length ?? 0;
  // Change verdict from the real data of every honest pair.
  const verdict = useMemo(() => {
    if (!field) return undefined;
    const byId = new Map(field.frames.map((f, i) => [f.id, i]));
    const sorted = [...framesRef.current].sort((a, b) => a.mjd - b.mjd);
    const results = field.pairs.filter((p) => p.trust === "high").map((p) => {
      const fa = sorted[byId.get(p.a)!], fb = sorted[byId.get(p.b)!];
      return fa && fb ? { ...p, ...pairChange(fa, fb) } : undefined;
    }).filter(Boolean) as { a: string; b: string; spots: number; peakSigma: number }[];
    const changed = results.filter((r) => r.spots > 0);
    return { tested: results.length, changed: changed.length, maxSpots: Math.max(0, ...changed.map((r) => r.spots)) };
  }, [field]);
  const done = frames.length + failed;

  return (
    <main className="content-screen survey-observations enhanced">
      <div className="obs-head">
        <div>
          <small>LIVE FROM NASA/IPAC IRSA · REAL SPHEREx DATA</small>
          <h1>{label}</h1>
          <p>RA {fmtRa(ra)} · Dec {fmtDec(dec)} · 10′ around this point, north up, 6.15″ per pixel.</p>
        </div>
        <button className="button secondary" onClick={onBack}>← Back to the sky map</button>
      </div>

      {phase !== "done" && !field && <div className="glass live-progress" role="status" aria-live="polite">
        {phase === "search" && <p>Asking IRSA which SPHEREx exposures cover this point…</p>}
        {phase === "frames" && <>
          <p>SPHEREx imaged this point <b>{total}</b> times. Downloading and processing <b>{chosen.length}</b> real images spread over the mission: <b>{done}</b> / {chosen.length}
            {failed > 0 && <> ({failed} skipped: point on a detector edge or IRSA busy)</>}.</p>
          <div className="live-bar"><i style={{ width: `${(100 * done) / Math.max(1, chosen.length)}%` }} /></div>
          {frames.length >= 8 && <button className="button secondary" onClick={showNow}>Show the {frames.length} images loaded so far</button>}
        </>}
        {phase === "error" && <p role="alert">{error}</p>}
      </div>}

      {field && <>
        <div className="glass live-summary">
          <span><b>{field.frames.length}</b> real images</span>
          <span><b>{honest}</b> honest pairs (same colour within 2%, ≥ 150 days apart)</span>
          <span>{niceSpan(field)}</span>
          <div className="live-tabs" role="tablist">
            <button role="tab" aria-selected={tab === "timelapse"} className={tab === "timelapse" ? "active" : ""} onClick={() => setTab("timelapse")}>Timelapse</button>
            <button role="tab" aria-selected={tab === "compare"} className={tab === "compare" ? "active" : ""} onClick={() => setTab("compare")}>Compare two dates</button>
          </div>
        </div>
        {verdict && <div className={`glass live-verdict ${verdict.tested === 0 ? "none" : verdict.changed ? "changed" : "same"}`}>
          <small>DID ANYTHING CHANGE HERE?</small>
          {verdict.tested === 0
            ? <p><b>Cannot tell yet.</b> None of the loaded images form a fair pair (same infrared colour, at least 150 days apart), so any difference could just be colour. Try another point or load again.</p>
            : verdict.changed === 0
              ? <p><b>No — everything stayed put.</b> We compared {verdict.tested} fair pairs pixel by pixel: no spot changed by more than 6× the noise. That is what stars, nebulae and galaxies should do.</p>
              : <p><b>Something changed in {verdict.changed} of {verdict.tested} fair pairs</b> (up to {verdict.maxSpots} pixels above 6× the noise). It could be a Solar System object passing through, a variable star, or an image artefact — look for it with Compare → Changes only.</p>}
        </div>}
        <div className="glass look-box control">
          <small>WHAT TO EXPECT HERE</small>
          <p>Stars, nebulae and galaxies do not move in a year, so in a fair (green) pair nothing should jump — that is what an honest comparison looks like.
            If an unfair (red) pair looks different, that is SPHEREx's changing infrared colour, not motion. Moving objects (planets, asteroids, comets) are only found
            near the ecliptic; Neptune is the example we measured.</p>
        </div>
        {tab === "timelapse" && colour && colour.group.length >= 4 && <p className="live-colour">
          {allColours
            ? <>Showing all {field.frames.length} images in every infrared colour — brightness jumps here are colour, not motion. <button onClick={() => setAllColours(false)}>Show one colour only</button></>
            : <>Showing the {colour.group.length} images taken in the same infrared colour ({colour.centerUm.toFixed(2)} µm ± 2%), so only real changes would blink. The ring marks your point. <button onClick={() => setAllColours(true)}>Show all {field.frames.length} images</button></>}
        </p>}
        {tab === "timelapse"
          ? <Timelapse key={"t" + field.frames.length + (allColours ? "a" : "c")} frames={timeline} synthetic={false} title={label} backdrop={backdrop} onBack={onBack} />
          : <ComparePairs key={"c" + field.frames.length} field={field} />}
        <p className="live-note">Masked pixels are filled from their neighbours for display only; honesty labels use the wavelength SPHEREx measured at this exact pixel. Each image links to its source file at IRSA.</p>
      </>}
    </main>
  );
}

function niceSpan(f: Field) {
  const t = f.frames.map((x) => x.obs_time_utc.slice(0, 10)).sort();
  return `${t[0]} → ${t[t.length - 1]}`;
}
