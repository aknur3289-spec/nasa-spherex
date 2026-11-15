import { useState } from "react";
import { parseCoords } from "./skyCoords";
import { resolveSesameName } from "./sesame";

export function openLivePoint(ra: number, dec: number, name: string) {
  const q = new URLSearchParams({ ra: ra.toFixed(5), dec: dec.toFixed(5), name });
  location.hash = "/live?" + q.toString();
}

const PRESETS = ["Orion Nebula", "Pleiades", "M31", "M101", "Crab Nebula"];

/** The main way in: any coordinates or object name → real SPHEREx images of that point, live from IRSA. */
export function AnyPoint({ compact = false }: { compact?: boolean }) {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");

  const go = async (value: string) => {
    const q = value.trim();
    if (!q) return;
    setBusy(true);
    setMsg("");
    try {
      const c = parseCoords(q);
      if (c) return openLivePoint(c.ra, c.dec, q);
      const r = await resolveSesameName(q);
      openLivePoint(r.ra, r.dec, q);
    } catch {
      setMsg("Name not found. Try coordinates, e.g. 83.82 -5.39 or 05h35m17s -05°23′.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className={`glass any-point ${compact ? "compact" : ""}`}>
      <div className="any-point-head">
        <small>ANY POINT IN THE SKY</small>
        <b>Type coordinates or a name — we load SPHEREx's real images of that spot from NASA's archive and compare them over time.</b>
      </div>
      <form className="any-point-form" role="search" onSubmit={(e) => { e.preventDefault(); go(text); }}>
        <input value={text} onChange={(e) => setText(e.target.value)} placeholder="e.g. 83.82 -5.39   or   Orion Nebula" aria-label="Coordinates or object name" />
        <button className="button primary" type="submit" disabled={busy}>{busy ? "Finding…" : "Load real images"}</button>
      </form>
      <div className="any-point-presets">
        <span>Try:</span>
        {PRESETS.map((p) => <button key={p} type="button" onClick={() => go(p)}>{p}</button>)}
      </div>
      {msg && <p className="any-point-msg" role="alert">{msg}</p>}
      {!compact && <p className="any-point-note">Takes about a minute: every image is downloaded and processed on demand. Stars and galaxies do not move — only Solar System objects do.</p>}
    </div>
  );
}
