import { useEffect, useMemo, useState } from "react";
import type { Field, FieldSummary } from "../contract";
import { imageUrl, loadField } from "../data/loader";
import { fmtDec, fmtRa, friendly, niceDate } from "./fields";
import { SkySearch } from "./SkySearch";

/**
 * Sky Explorer: WHERE the data is. An all-sky map with every real field,
 * filters that work on the real frames, and a results list.
 * Opening a field goes to Timelapse (watch it) or Compare (check two images).
 */

type Go = (screen: "timelapse" | "compare" | "dial", id?: string) => void;

const BANDS = [
  { id: "all", label: "All colours", range: [0, 99] },
  { id: "b1", label: "0.75–1.1 μm", range: [0.75, 1.1] },
  { id: "b2", label: "1.1–2.4 μm", range: [1.1, 2.4] },
  { id: "b3", label: "2.4–3.8 μm", range: [2.4, 3.8] },
  { id: "b4", label: "3.8–5.0 μm", range: [3.8, 5.01] },
] as const;

const W = 1000;
const H = 500;
const EPS = (23.4393 * Math.PI) / 180;
// Map centred on RA 300° so the fields sit away from the edges; RA grows to the left as on a sky chart.
const CENTER_RA = 300;
const px = (ra: number, dec: number) => ({
  x: ((((CENTER_RA + 180 - ra) % 360) + 360) % 360 / 360) * W,
  y: ((90 - dec) / 180) * H,
});

const ecliptic = (() => {
  const pts: { x: number; y: number }[] = [];
  for (let l = 0; l <= 360; l += 2) {
    const L = (l * Math.PI) / 180;
    const ra = ((Math.atan2(Math.sin(L) * Math.cos(EPS), Math.cos(L)) * 180) / Math.PI + 360) % 360;
    const dec = (Math.asin(Math.sin(EPS) * Math.sin(L)) * 180) / Math.PI;
    pts.push(px(ra, dec));
  }
  // split where RA wraps
  const segs: string[] = [];
  let cur: string[] = [];
  pts.forEach((p, i) => {
    if (i && Math.abs(p.x - pts[i - 1].x) > W / 2) {
      segs.push(cur.join(" "));
      cur = [];
    }
    cur.push(`${p.x.toFixed(1)},${p.y.toFixed(1)}`);
  });
  segs.push(cur.join(" "));
  return segs;
})();

const NEPTUNE = { ra: 359.64, dec: -1.62 };

export function SkyExplorer({ catalog, go }: { catalog: FieldSummary[]; go: Go }) {
  const [fields, setFields] = useState<Record<string, Field>>({});
  const [band, setBand] = useState<(typeof BANDS)[number]["id"]>("all");
  const [year, setYear] = useState<"all" | "2025" | "2026">("all");
  const [onlyTrusted, setOnlyTrusted] = useState(false);
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<string>();
  const [zoom, setZoom] = useState(1);
  const [layers, setLayers] = useState({ ecliptic: true, grid: true });

  useEffect(() => {
    const controller = new AbortController();
    catalog.forEach((item) =>
      loadField(item.field_id, controller.signal)
        .then((f) => setFields((prev) => ({ ...prev, [f.field_id]: f })))
        .catch(() => undefined),
    );
    return () => controller.abort();
  }, [catalog]);

  const results = useMemo(() => {
    const [lo, hi] = BANDS.find((b) => b.id === band)!.range;
    return catalog
      .map((item) => {
        const f = fields[item.field_id];
        const frames = (f?.frames ?? []).filter(
          (fr) => fr.wavelength_um >= lo && fr.wavelength_um < hi && (year === "all" || fr.obs_time_utc.startsWith(year)),
        );
        frames.sort((a, b) => a.mjd - b.mjd);
        const ids = new Set(frames.map((fr) => fr.id));
        const pairs = (f?.pairs ?? []).filter((p) => ids.has(p.a) && ids.has(p.b));
        const trusted = pairs.filter((p) => p.trust === "high");
        return { item, f, frames, pairs, trusted };
      })
      .filter((r) => !r.f || r.frames.length > 0)
      .filter((r) => !onlyTrusted || r.trusted.length > 0)
      .filter((r) => {
        const q = query.trim().toLowerCase();
        return !q || friendly(r.item).name.toLowerCase().includes(q) || r.item.field_id.includes(q);
      });
  }, [catalog, fields, band, year, onlyTrusted, query]);

  const totalImages = results.reduce((n, r) => n + r.frames.length, 0);
  const totalTrusted = results.reduce((n, r) => n + r.trusted.length, 0);
  const sel = results.find((r) => r.item.field_id === selected) ?? results[0];

  const focus = sel?.f ? px(sel.f.center.ra_deg, sel.f.center.dec_deg) : { x: W / 2, y: H / 2 };
  const vw = W / zoom;
  const vh = H / zoom;
  const vx = Math.min(Math.max(focus.x - vw / 2, 0), W - vw);
  const vy = Math.min(Math.max(focus.y - vh / 2, 0), H - vh);
  const nep = px(NEPTUNE.ra, NEPTUNE.dec);

  return (
    <main className="app-screen sky-explorer">
      <div className="sx-backdrop" aria-hidden="true" />

      <SkySearch fields={catalog.map((c) => fields[c.field_id]).filter(Boolean)} go={go} />

      <aside className="glass sx-panel sx-filters" aria-label="Filter the sky">
        <div className="panel-title">
          <div>
            <small>SURVEY CONTROLS</small>
            <h3>Filter the sky</h3>
          </div>
        </div>

        <label className="field-label" htmlFor="sx-band">Infrared colour (wavelength)</label>
        <div className="sx-chips" id="sx-band" role="group">
          {BANDS.map((b) => (
            <button key={b.id} className={band === b.id ? "on" : ""} aria-pressed={band === b.id} onClick={() => setBand(b.id)}>
              {b.label}
            </button>
          ))}
        </div>

        <label className="field-label">Observed in</label>
        <div className="sx-chips" role="group">
          {(["all", "2025", "2026"] as const).map((y) => (
            <button key={y} className={year === y ? "on" : ""} aria-pressed={year === y} onClick={() => setYear(y)}>
              {y === "all" ? "Any year" : y}
            </button>
          ))}
        </div>

        <label className="toggle-row sx-toggle">
          <span>
            <b>Only fields with trustworthy pairs</b>
            <small>Two images in the same colour, safe to compare</small>
          </span>
          <input type="checkbox" checked={onlyTrusted} onChange={(e) => setOnlyTrusted(e.target.checked)} />
          <i />
        </label>

        <div className="sx-summary">
          <div>
            <b>{totalImages}</b>
            <span>images match</span>
          </div>
          <div>
            <b>{totalTrusted}</b>
            <span>trustworthy pairs</span>
          </div>
        </div>
      </aside>

      <section className="sx-map glass" aria-label="Sky map">
        <svg viewBox={`${vx} ${vy} ${vw} ${vh}`} preserveAspectRatio="xMidYMid meet" role="img" aria-label="All-sky map with SPHEREx fields">
          {layers.grid && (
            <g className="sx-grid">
              {[0, 30, 60, 90, 120, 150, 180, 210, 240, 270, 300, 330].map((ra) => {
                const x = px(ra, 0).x;
                return (
                  <g key={ra}>
                    <line x1={x} x2={x} y1={0} y2={H} />
                    <text x={x + 4} y={H - 8}>{ra / 15}h</text>
                  </g>
                );
              })}
              {[-60, -30, 0, 30, 60].map((d) => {
                const y = px(0, d).y;
                return (
                  <g key={d}>
                    <line x1={0} x2={W} y1={y} y2={y} className={d === 0 ? "eq" : ""} />
                    <text x={6} y={y - 4}>{d > 0 ? `+${d}°` : `${d}°`}</text>
                  </g>
                );
              })}
            </g>
          )}
          {layers.ecliptic && (
            <g className="sx-ecliptic">
              {ecliptic.map((s, i) => (
                <polyline key={i} points={s} />
              ))}
              <text x={px(90, 23.4).x + 10} y={px(90, 23.4).y - 8}>Ecliptic — where the planets travel</text>
            </g>
          )}

          <g className="sx-marker neptune" onClick={() => go("dial")} role="button" tabIndex={0}
            onKeyDown={(e) => e.key === "Enter" && go("dial")} aria-label="Neptune: open the Distance Dial">
            <circle cx={nep.x} cy={nep.y} r={9 / zoom} />
            <circle cx={nep.x} cy={nep.y} r={3 / zoom} className="dot" />
            <text x={nep.x + 14 / zoom} y={nep.y + 22 / zoom} style={{ fontSize: 12 / zoom }}>Neptune · Distance Dial</text>
          </g>

          {results.map((r) => {
            if (!r.f) return null;
            const p = px(r.f.center.ra_deg, r.f.center.dec_deg);
            const on = sel?.item.field_id === r.item.field_id;
            return (
              <g key={r.item.field_id} className={`sx-marker ${on ? "on" : ""}`} role="button" tabIndex={0}
                aria-label={`${friendly(r.item).name}, ${r.frames.length} images`}
                onClick={() => setSelected(r.item.field_id)}
                onKeyDown={(e) => e.key === "Enter" && setSelected(r.item.field_id)}>
                <circle cx={p.x} cy={p.y} r={(on ? 15 : 11) / zoom} />
                <circle cx={p.x} cy={p.y} r={3.5 / zoom} className="dot" />
                <text x={p.x + 18 / zoom} y={p.y - 2 / zoom} style={{ fontSize: 13 / zoom }}>{friendly(r.item).short}</text>
                <text x={p.x + 18 / zoom} y={p.y + 13 / zoom} className="sub" style={{ fontSize: 10 / zoom }}>
                  {r.frames.length} images
                </text>
              </g>
            );
          })}
        </svg>

        <div className="glass sx-tools">
          <button aria-label="Zoom in" onClick={() => setZoom((z) => Math.min(6, z * 1.6))}>+</button>
          <button aria-label="Zoom out" onClick={() => setZoom((z) => Math.max(1, z / 1.6))}>−</button>
          <i />
          <button className={layers.ecliptic ? "on" : ""} aria-pressed={layers.ecliptic} onClick={() => setLayers((l) => ({ ...l, ecliptic: !l.ecliptic }))}>Ecliptic</button>
          <button className={layers.grid ? "on" : ""} aria-pressed={layers.grid} onClick={() => setLayers((l) => ({ ...l, grid: !l.grid }))}>Grid</button>
        </div>

        {sel?.f && (
          <div className="glass sx-preview">
            <img src={imageUrl(sel.item.field_id, sel.item.thumbnail ?? "thumb.png")} alt="" />
            <div>
              <small>SELECTED FIELD</small>
              <b>{friendly(sel.item).name}</b>
              <span>
                RA {fmtRa(sel.f.center.ra_deg)} · Dec {fmtDec(sel.f.center.dec_deg)}
              </span>
              <div className="sx-actions">
                <button className="button primary" onClick={() => go("timelapse", sel.item.field_id)}>Watch timelapse</button>
                <button className="button secondary" onClick={() => go("compare", sel.item.field_id)}>Compare two images</button>
              </div>
            </div>
          </div>
        )}

      </section>

      <aside className="glass sx-panel sx-results" aria-label="Fields">
        <div className="panel-title">
          <div>
            <small>REAL SPHEREx FIELDS</small>
            <h3>{results.length} {results.length === 1 ? "field" : "fields"}</h3>
          </div>
          <span className="live-dot">IRSA data</span>
        </div>
        <div className="search">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden="true"><circle cx="11" cy="11" r="6.5" /><path d="m16 16 4 4" /></svg>
          <input aria-label="Search fields" placeholder="Search a field" value={query} onChange={(e) => setQuery(e.target.value)} />
        </div>
        <div className="candidate-list">
          {results.map((r) => {
            const on = sel?.item.field_id === r.item.field_id;
            const pct = r.f ? Math.round((r.frames.length / r.f.frames.length) * 100) : 0;
            return (
              <button key={r.item.field_id} className={`candidate sx-result ${on ? "selected" : ""}`} onClick={() => setSelected(r.item.field_id)}>
                <div className="candidate-thumb" style={{ backgroundImage: `url(${imageUrl(r.item.field_id, r.item.thumbnail ?? "thumb.png")})` }} />
                <div className="candidate-copy">
                  <div>
                    <b>{friendly(r.item).short}</b>
                    <span className={`chip ${r.trusted.length ? "success" : ""}`}>
                      {r.trusted.length ? `${r.trusted.length} safe pairs` : "no safe pair"}
                    </span>
                  </div>
                  {r.f && <small>RA {fmtRa(r.f.center.ra_deg)}</small>}
                  {r.f && <small>Dec {fmtDec(r.f.center.dec_deg)}</small>}
                  {r.frames.length > 0 && (
                    <small>
                      {niceDate(r.frames[0].obs_time_utc)} → {niceDate(r.frames[r.frames.length - 1].obs_time_utc)}
                    </small>
                  )}
                </div>
                <div className="score" style={{ ["--score" as string]: `${pct * 3.6}deg` }} title={`${r.frames.length} of ${r.f?.frames.length ?? "?"} images match`}>
                  <span>{r.frames.length}</span>
                </div>
              </button>
            );
          })}
          {!results.length && (
            <div className="empty">
              <b>No fields match</b>
              <p>Try another colour or year.</p>
            </div>
          )}
        </div>
      </aside>
    </main>
  );
}
