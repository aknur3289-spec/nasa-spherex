import { useEffect, useMemo, useRef, useState } from "react";
import type { Field } from "../contract";
import { fmtDec, fmtRa, friendly } from "./fields";
import { formatSep, insideSquare, parseCoords, separationDeg, squareCorners, type RaDec } from "./skyCoords";
import { resolveSesameName } from "./sesame";
import { hipsUrls } from "./hips";

/**
 * Whole-sky search on the SPHEREx QR2 HiPS maps from CDS, shown with Aladin Lite.
 * Our three time-lapse fields and Neptune's path are drawn on top.
 * A point inside one of our fields links to Timelapse / Compare; anywhere else we say
 * honestly that we have no time series there and point to the IRSA archive.
 */

type Go = (screen: "timelapse" | "compare" | "dial", id?: string) => void;

const SURVEYS = [
  { id: "color", label: "Colour" },
  ...[1, 2, 3, 4, 5, 6].map((n) => ({ id: `D${n}`, label: `D${n}` })),
];
const IRSA_EXPLORER = "https://irsa.ipac.caltech.edu/applications/spherex/";
const MAP_UNAVAILABLE = "The whole-sky map is served by CDS and is not reachable from this network right now. Search still works.";

// Neptune in our two dial images: June 2025 reference crop and December 2025 measured centroid.
const NEPTUNE_PATH: { ra: number; dec: number; label: string }[] = [
  { ra: 2.15087, dec: -0.5024, label: "Neptune · Jun 2025" },
  { ra: 359.636378, dec: -1.620821, label: "Neptune · Dec 2025" },
];

const EXAMPLES = ["M101", "210.80 54.35", "14h03m13s +54°20′", "Neptune"];

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type AladinAny = any;
let aladinApi: AladinAny;
let aladinScript: Promise<AladinAny> | undefined;
function loadAladin(): Promise<AladinAny> {
  aladinScript ??= (async () => {
    const { default: A } = await import("aladin-lite");
    await A.init;
    aladinApi = A;
    return A;
  })().catch((error) => {
    aladinScript = undefined;
    throw error;
  });
  return aladinScript;
}

function surveyLayer(A: AladinAny, id: string, url: string, onError: () => void): AladinAny {
  return A.createImageSurvey(
    `CDS/P/SPHEREx/QR2/${id}`,
    `SPHEREx QR2 ${id}`,
    url,
    "equatorial",
    undefined,
    { errorCallback: onError },
  );
}

function surveyWithFallback(
  A: AladinAny, id: string, getAladin: () => AladinAny,
  isCurrent: () => boolean, onUnavailable: () => void,
): AladinAny {
  const urls = hipsUrls(id, location.origin);
  let attempt = 0;
  const make = (index: number): AladinAny => surveyLayer(A, id, urls[index], () => {
    if (!isCurrent() || attempt !== index) return;
    attempt += 1;
    if (attempt === urls.length) {
      onUnavailable();
      return;
    }
    const next = make(attempt);
    const a = getAladin();
    if (a?.setBaseImageLayer) a.setBaseImageLayer(next);
    else a?.setImageSurvey?.(next);
  });
  return make(0);
}

function focusMap(a: AladinAny, at: RaDec, fov: number): void {
  try {
    a?.gotoRaDec(at.ra, at.dec);
    a?.setFoV?.(fov);
  } catch {
    // The result card works even when Aladin is unavailable.
  }
}

function openLive(at: RaDec, label: string) {
  const q = new URLSearchParams({ ra: at.ra.toFixed(5), dec: at.dec.toFixed(5), name: label });
  location.hash = "/live?" + q.toString();
}

type Hit =
  | { kind: "field"; at: RaDec; field: Field; label: string }
  | { kind: "neptune"; at: RaDec; label: string }
  | { kind: "outside"; at: RaDec; label: string; nearest?: { field: Field; sep: number } };

export function SkySearch({ fields, go }: { fields: Field[]; go: Go }) {
  const host = useRef<HTMLDivElement>(null);
  const aladin = useRef<AladinAny>(null);
  const surveyGeneration = useRef(0);
  const searchNumber = useRef(0);
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");
  const [survey, setSurvey] = useState("color");
  const [query, setQuery] = useState("");
  const [hit, setHit] = useState<Hit>();
  const [message, setMessage] = useState<string>();
  const fieldsRef = useRef(fields);
  fieldsRef.current = fields;

  const classify = useMemo(
    () =>
      (at: RaDec, label: string): Hit => {
        const inField = fields.find((f) => insideSquare(at, { ra: f.center.ra_deg, dec: f.center.dec_deg }, f.size_arcmin));
        if (inField) return { kind: "field", at, field: inField, label };
        const nearest = fields
          .map((f) => ({ field: f, sep: separationDeg(at, { ra: f.center.ra_deg, dec: f.center.dec_deg }) }))
          .sort((a, b) => a.sep - b.sep)[0];
        return { kind: "outside", at, label, nearest };
      },
    [fields],
  );

  const classifyRef = useRef(classify);
  classifyRef.current = classify;

  // Boot Aladin once.
  useEffect(() => {
    let alive = true;
    loadAladin()
      .then((A) => {
        if (!alive || !host.current) return;
        const generation = ++surveyGeneration.current;
        const layer = surveyWithFallback(
          A, "color", () => aladin.current,
          () => generation === surveyGeneration.current,
          () => setStatus("error"),
        );
        const a = A.aladin(host.current, {
          survey: layer,
          fov: 1,
          target: "210.80227 +54.34895",
          log: false,
          showReticle: true,
          showCooGrid: false,
          showLayersControl: false,
          showGotoControl: false,
          showProjectionControl: false,
          showFrame: true,
          showFullscreenControl: true,
          showShareControl: false,
          showSimbadPointerControl: true,
        });
        aladin.current = a;
        a.on?.("objectClicked", (obj: AladinAny) => {
          const d = obj?.data;
          if (!d?.kind) return;
          if (d.kind === "neptune") setHit({ kind: "neptune", at: { ra: obj.ra, dec: obj.dec }, label: d.name });
          else {
            const f = fieldsRef.current.find((x) => x.field_id === d.id);
            if (f) setHit({ kind: "field", at: { ra: f.center.ra_deg, dec: f.center.dec_deg }, field: f, label: d.name });
          }
        });
        // Click anywhere on the sky: offer live SPHEREx images of that exact point.
        a.on?.("click", (e: AladinAny) => {
          if (e?.isDragging) return;
          const ra = Number(e?.ra), dec = Number(e?.dec);
          if (!Number.isFinite(ra) || !Number.isFinite(dec)) return;
          setHit(classifyRef.current({ ra, dec }, "Point you clicked"));
        });
        setStatus("ready");
      })
      .catch(() => alive && setStatus("error"));
    return () => {
      alive = false;
    };
  }, []);

  // Draw our fields and Neptune once both Aladin and the fields are ready.
  const drawnKey = useRef("");
  useEffect(() => {
    const a = aladin.current;
    const A = aladinApi;
    if (status !== "ready" || !a || !A || !fields.length) return;
    const key = fields.map((f) => f.field_id).join(",");
    if (drawnKey.current === key) return;
    drawnKey.current = key;

    const boxes = A.graphicOverlay({ color: "#3dd6ff", lineWidth: 2, name: "Our time-lapse fields" });
    a.addOverlay(boxes);
    const marks = A.catalog({ name: "Our fields", sourceSize: 16, color: "#3dd6ff", shape: "circle", displayLabel: true, labelColumn: "name", labelColor: "#3dd6ff", labelFont: "13px DM Mono, monospace" });
    a.addCatalog(marks);
    fields.forEach((f) => {
      boxes.add(A.polygon(squareCorners({ ra: f.center.ra_deg, dec: f.center.dec_deg }, f.size_arcmin), { color: "#3dd6ff" }));
      marks.addSources([A.source(f.center.ra_deg, f.center.dec_deg, { kind: "field", id: f.field_id, name: friendly(f).short })]);
    });

    const path = A.graphicOverlay({ color: "#b8a2ff", lineWidth: 2, name: "Neptune" });
    a.addOverlay(path);
    path.add(A.polyline(NEPTUNE_PATH.map((p) => [p.ra, p.dec]), { color: "#b8a2ff", lineWidth: 2 }));
    const nep = A.catalog({ name: "Neptune", sourceSize: 14, color: "#b8a2ff", shape: "circle", displayLabel: true, labelColumn: "name", labelColor: "#d6ccff", labelFont: "13px DM Mono, monospace" });
    a.addCatalog(nep);
    nep.addSources(NEPTUNE_PATH.map((p) => A.source(p.ra, p.dec, { kind: "neptune", name: p.label })));
  }, [status, fields]);

  useEffect(() => {
    const a = aladin.current;
    if (!a || !aladinApi) return;
    const id = SURVEYS.find((s) => s.id === survey)!.id;
    const generation = ++surveyGeneration.current;
    const layer = surveyWithFallback(
      aladinApi, id, () => aladin.current,
      () => generation === surveyGeneration.current,
      () => setStatus("error"),
    );
    setStatus("ready");
    if (a.setBaseImageLayer) a.setBaseImageLayer(layer);
    else a.setImageSurvey?.(layer);
  }, [survey]);

  const search = async (text = query) => {
    const requestNumber = ++searchNumber.current;
    const q = text.trim();
    setQuery(q);
    setMessage(undefined);
    if (!q) return;
    const a = aladin.current;
    if (/^neptune$/i.test(q)) {
      const p = NEPTUNE_PATH[1];
      focusMap(a, p, 1.5);
      setHit({ kind: "neptune", at: { ra: p.ra, dec: p.dec }, label: "Neptune · Dec 2025" });
      return;
    }
    const c = parseCoords(q);
    if (c) {
      focusMap(a, c, 0.5);
      setHit(classify(c, q));
      return;
    }
    try {
      const { ra, dec } = await resolveSesameName(q);
      if (requestNumber !== searchNumber.current) return;
      focusMap(a, { ra, dec }, 0.5);
      setHit(classify({ ra, dec }, q));
    } catch {
      if (requestNumber === searchNumber.current) setMessage("Name not found, try coordinates");
    }
  };

  return (
    <section className="glass sky-search" aria-label="Find any point in the sky">
      <div className="ss-head">
        <div>
          <small>WHOLE SKY · SPHEREx QR2</small>
          <h2>Find any star, galaxy or coordinate</h2>
          <p>Type a name or coordinates. If the point is inside one of our three fields you can watch it change over time.</p>
        </div>
        <form
          className="ss-form"
          onSubmit={(e) => {
            e.preventDefault();
            search();
          }}
        >
          <input
            aria-label="Object name or coordinates"
            placeholder="M101, 210.80 54.35 or 14h03m13s +54°20′"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <button className="button primary" type="submit">Find</button>
        </form>
        <div className="ss-examples">
          <span>Try:</span>
          {EXAMPLES.map((x) => (
            <button key={x} type="button" onClick={() => search(x)}>{x}</button>
          ))}
        </div>
      </div>

      <div className="ss-body">
        <div className="ss-map">
          <div ref={host} className="ss-aladin" />
          {status !== "ready" && (
            <div className="ss-map-status" role="status">
              {status === "loading" ? "Loading the SPHEREx sky map…" : MAP_UNAVAILABLE}
            </div>
          )}
          <div className="ss-layers" role="group" aria-label="Map layer">
            {SURVEYS.map((s) => (
              <button key={s.id} className={survey === s.id ? "on" : ""} aria-pressed={survey === s.id} onClick={() => setSurvey(s.id)} title={s.id === "color" ? "All detectors combined" : `Detector ${s.id} only`}>
                {s.label}
              </button>
            ))}
          </div>
          <div className="ss-legend">
            <span><i className="box" /> Our time-lapse fields (10′, about a third of the Moon)</span>
            <span><i className="nep" /> Neptune in our June and December 2025 images</span>
          </div>
        </div>

        <aside className="ss-result" aria-live="polite">
          {message && <p className="ss-msg">{message}</p>}
          {!hit && !message && (
            <div className="ss-empty">
              <b>Search or click a blue square</b>
              <span>Blue squares are the three patches where we have many SPHEREx images over time. The purple marks are Neptune.</span>
            </div>
          )}
          {hit?.kind === "field" && (
            <div className="ss-card in">
              <small>INSIDE OUR DATA</small>
              <h3>{friendly(hit.field).name}</h3>
              <p className="mono">{fmtRa(hit.at.ra)} · {fmtDec(hit.at.dec)}</p>
              <p>We have {hit.field.frames.length} SPHEREx images of this patch, taken months apart.</p>
              <div className="ss-actions">
                <button className="button primary" onClick={() => go("timelapse", hit.field.field_id)}>Watch timelapse</button>
                <button className="button secondary" onClick={() => go("compare", hit.field.field_id)}>Compare two dates</button>
              </div>
              <button className="ss-nearest ss-live" onClick={() => openLive(hit.at, hit.label)}>
                <span>Or fetch fresh images live from IRSA</span>
                <b>Load real SPHEREx images here →</b>
              </button>
            </div>
          )}
          {hit?.kind === "neptune" && (
            <div className="ss-card nep">
              <small>KNOWN PLANET</small>
              <h3>{hit.label}</h3>
              <p className="mono">{fmtRa(hit.at.ra)} · {fmtDec(hit.at.dec)}</p>
              <p>Neptune shifted between our June and December 2025 images. Use that shift to measure its distance yourself.</p>
              <div className="ss-actions">
                <button className="button primary" onClick={() => go("dial")}>Play the Distance Dial</button>
              </div>
            </div>
          )}
          {hit?.kind === "outside" && (
            <div className="ss-card out">
              <small>OUTSIDE OUR TIME-LAPSE FIELDS</small>
              <h3>{hit.label}</h3>
              <p className="mono">{fmtRa(hit.at.ra)} · {fmtDec(hit.at.dec)}</p>
              <p>
                SPHEREx scans the whole sky every six months. Load its real images of this exact point straight from NASA's archive and compare them over time.
              </p>
              <div className="ss-actions">
                <button className="button primary" onClick={() => openLive(hit.at, hit.label)}>Load real SPHEREx images here</button>
              </div>
              {hit.nearest && (
                <button className="ss-nearest" onClick={() => go("timelapse", hit.nearest!.field.field_id)}>
                  <span>Nearest of our fields</span>
                  <b>{friendly(hit.nearest.field).name}</b>
                  <em>{formatSep(hit.nearest.sep)} away →</em>
                </button>
              )}
              <a className="ss-irsa" href={IRSA_EXPLORER} target="_blank" rel="noreferrer">
                Search all SPHEREx images of this spot at IRSA ↗
              </a>
            </div>
          )}
        </aside>
      </div>

      <p className="ss-credit">
        Whole-sky map: SPHEREx QR2, HiPS by{" "}
        <a href="https://aladin.cds.unistra.fr/" target="_blank" rel="noreferrer">CDS/Unistra</a> (ODbL), shown with Aladin Lite. Data: NASA/IPAC IRSA.
      </p>
    </section>
  );
}
