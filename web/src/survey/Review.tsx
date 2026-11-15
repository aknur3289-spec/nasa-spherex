import { Fragment, useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  type Answer, type Candidate, type Labels, type ReviewQueue, type ReviewSet,
  KIND_HELP, assetUrl, exportPayload, loadQueue, loadSets, nextUnlabelled, order, readLabels, summary, verdict, writeLabels,
} from "./reviewData";
import "./review.css";

type View = "blink" | "ref" | "sci" | "diff";
type Phase = "intro" | "practice" | "work";

const VIEW_LABEL: Record<View, string> = { blink: "Blink old ↔ new", ref: "Old (reference)", sci: "New (science)", diff: "Difference" };
const reducedMotion = () => typeof matchMedia === "function" && matchMedia("(prefers-reduced-motion: reduce)").matches;

function Stamp({ src, label, big = false, marker = true }: { src: string; label: string; big?: boolean; marker?: boolean }) {
  return (
    <figure className={`rv-stamp ${big ? "big" : ""}`}>
      <div className="rv-stamp-img">
        <img src={src} alt={label} draggable={false} />
        {marker && <span className="rv-marker" aria-hidden="true"><i /><i /><i /><i /></span>}
      </div>
      {!big && <figcaption>{label}</figcaption>}
    </figure>
  );
}

function Viewer({ setId, c, view, setView }: { setId: string; c: Candidate; view: View; setView: (v: View) => void }) {
  const [phase, setPhase] = useState(0);
  useEffect(() => {
    if (view !== "blink") return;
    const t = setInterval(() => setPhase((p) => 1 - p), 650);
    return () => clearInterval(t);
  }, [view]);
  const show = view === "blink" ? (phase ? "sci" : "ref") : view;
  const name = show === "ref" ? "OLD" : show === "sci" ? "NEW" : "DIFFERENCE";
  return (
    <div className="rv-viewer">
      <div className="rv-big">
        <Stamp src={assetUrl(setId, c.stamps[show])} label={`${name} image of candidate ${c.id}`} big />
        <span className={`rv-tag ${show}`}>{name}</span>
      </div>
      <div className="rv-views" role="tablist" aria-label="Image view">
        {(["blink", "ref", "sci", "diff"] as View[]).map((v) => (
          <button key={v} role="tab" aria-selected={view === v} className={view === v ? "on" : ""} onClick={() => setView(v)}>
            {VIEW_LABEL[v]}
          </button>
        ))}
      </div>
      <div className="rv-strip">
        <Stamp src={assetUrl(setId, c.stamps.ref)} label="Old" />
        <Stamp src={assetUrl(setId, c.stamps.sci)} label="New" />
        <Stamp src={assetUrl(setId, c.stamps.diff)} label="New − old" />
      </div>
    </div>
  );
}

function Guide() {
  return (
    <details className="rv-guide glass" open>
      <summary>What am I looking for?</summary>
      <div className="rv-guide-grid">
        <div>
          <b className="ok">Real mover — press 1</b>
          <ul>
            <li>A <b>round dot</b>, about the size of the stars around it</li>
            <li>Present in <b>NEW</b>, missing in <b>OLD</b> (it moved here)</li>
            <li>Difference: one clean <b>white</b> dot in the crosshair</li>
          </ul>
        </div>
        <div>
          <b className="bad">Artefact — press 2</b>
          <ul>
            <li><b>Black + white pair</b>: a star that did not subtract</li>
            <li><b>One tiny sharp pixel</b>: cosmic ray or hot pixel</li>
            <li><b>Big soft blob</b>: optical ghost or glare</li>
            <li><b>Line</b>: satellite or particle streak</li>
            <li>Sits on the edge of a <b>masked (empty)</b> area</li>
          </ul>
        </div>
      </div>
      <p className="rv-guide-note">Not sure? Press 3 — honest "not sure" answers are useful too.</p>
    </details>
  );
}

export function Review() {
  const [sets, setSets] = useState<ReviewSet[]>();
  const [setId, setSetId] = useState<string>();
  const [queue, setQueue] = useState<ReviewQueue>();
  const [labels, setLabels] = useState<Labels>({});
  const [error, setError] = useState("");
  const [phase, setPhase] = useState<Phase>("intro");
  const [pos, setPos] = useState(0);
  const [view, setView] = useState<View>(reducedMotion() ? "ref" : "blink");
  const [hintFirst, setHintFirst] = useState(false);
  const [feedback, setFeedback] = useState<{ answer: Answer; c: Candidate }>();
  const [toast, setToast] = useState("");
  const [volunteer, setVolunteer] = useState("");
  const shownAt = useRef(Date.now());
  const undoStack = useRef<string[]>([]);

  useEffect(() => {
    const ctl = new AbortController();
    loadSets(ctl.signal).then((s) => {
      setSets(s);
      setSetId((cur) => cur ?? s[0]?.set_id);
    }).catch((e) => !ctl.signal.aborted && setError(e.message));
    return () => ctl.abort();
  }, []);

  useEffect(() => {
    const set = sets?.find((s) => s.set_id === setId);
    if (!set) return;
    const ctl = new AbortController();
    setQueue(undefined);
    loadQueue(set, ctl.signal).then((q) => {
      const l = readLabels(q.set_id);
      setQueue(q);
      setLabels(l);
      setPhase(Object.keys(l).length ? "work" : "intro");
      setFeedback(undefined);
      undoStack.current = [];
    }).catch((e) => !ctl.signal.aborted && setError(e.message));
    return () => ctl.abort();
  }, [sets, setId]);

  const { practice, work } = useMemo(() => (queue ? order(queue) : { practice: [], work: [] }), [queue]);
  const items = phase === "practice" ? practice : work;

  useEffect(() => {
    if (phase === "work") setPos((p) => Math.max(0, nextUnlabelled(work, labels, Math.min(p, work.length - 1))));
    if (phase === "practice") setPos(0);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [phase, work]);

  const current: Candidate | undefined = feedback?.c ?? items[pos];
  useEffect(() => { shownAt.current = Date.now(); }, [current?.id]);

  const stats = useMemo(() => summary(work.concat(practice), labels), [work, practice, labels]);
  const workDone = useMemo(() => summary(work, labels), [work, labels]);
  const allDone = phase === "work" && nextUnlabelled(work, labels) === -1;

  const save = useCallback((next: Labels) => {
    setLabels(next);
    if (queue) writeLabels(queue.set_id, next);
  }, [queue]);

  const answer = useCallback((a: Answer) => {
    if (!current || !queue || feedback) return;
    const next = { ...labels, [current.id]: { answer: a, at: new Date().toISOString(), ml_score: current.ml_score, ms: Date.now() - shownAt.current } };
    save(next);
    undoStack.current.push(current.id);
    if (phase === "practice") {
      setFeedback({ answer: a, c: current });
      return;
    }
    setToast(a === "real" ? "Saved: real mover" : a === "bogus" ? "Saved: artefact" : "Saved: not sure");
    const n = nextUnlabelled(work, next, pos + 1);
    if (n >= 0) setPos(n);
  }, [current, queue, feedback, labels, save, phase, work, pos]);

  const advancePractice = useCallback(() => {
    setFeedback(undefined);
    if (pos + 1 < practice.length) setPos(pos + 1);
    else { setPhase("work"); setPos(0); }
  }, [pos, practice.length]);

  const undo = useCallback(() => {
    const id = undoStack.current.pop();
    if (!id) return;
    const next = { ...labels };
    delete next[id];
    save(next);
    setFeedback(undefined);
    const i = items.findIndex((c) => c.id === id);
    if (i >= 0) setPos(i);
    setToast("Undone");
  }, [labels, save, items]);

  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(""), 1400);
    return () => clearTimeout(t);
  }, [toast]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement)?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || e.metaKey || e.ctrlKey || e.altKey) return;
      if (phase === "intro") { if (e.key === "Enter") setPhase(practice.length ? "practice" : "work"); return; }
      const k = e.key.toLowerCase();
      if (feedback && (k === "enter" || k === " " || k === "arrowright")) { e.preventDefault(); advancePractice(); return; }
      if (k === "1" || k === "r") answer("real");
      else if (k === "2" || k === "b") answer("bogus");
      else if (k === "3" || k === "s" || k === "?") answer("unsure");
      else if (k === "z" || k === "backspace") undo();
      else if (k === " ") { e.preventDefault(); setView((v) => (v === "blink" ? "ref" : "blink")); }
      else if (k === "d") setView("diff");
      else if (k === "arrowright" && phase === "work") setPos((p) => Math.min(items.length - 1, p + 1));
      else if (k === "arrowleft" && phase === "work") setPos((p) => Math.max(0, p - 1));
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [phase, feedback, answer, undo, advancePractice, items.length, practice.length]);

  const download = () => {
    if (!queue) return;
    const blob = new Blob([JSON.stringify(exportPayload(queue, labels, volunteer), null, 1)], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `parallax-labels-${queue.set_id}-${new Date().toISOString().slice(0, 10)}.json`;
    a.click();
    URL.revokeObjectURL(a.href);
  };

  const reset = () => {
    if (!queue) return;
    save({});
    undoStack.current = [];
    setPhase("intro");
    setPos(0);
    setFeedback(undefined);
  };

  if (error) return <main className="content-screen rv-screen"><p role="alert" className="glass rv-empty">{error}</p></main>;
  if (!sets || !queue) return <main className="content-screen rv-screen"><p role="status">Loading review set…</p></main>;

  const lbl = current ? labels[current.id] : undefined;
  const revealHint = hintFirst || !!lbl || !!feedback;
  const v = current ? verdict(current.ml_score) : undefined;

  return (
    <main className="content-screen rv-screen">
      <div className={`section-title rv-head ${phase === "intro" ? "" : "compact"}`}>
        <small>HELP THE SEARCH · VOLUNTEER REVIEW</small>
        <h1>Is it a real moving dot, or a fake?</h1>
        {phase === "intro" && <p>
          Our detector finds hundreds of "new" dots in SPHEREx image differences. Most are artefacts. A model ranks them,
          but people are still better at the hard cases. Look at each one, decide, and your answers train the next model.
        </p>}
      </div>

      {sets.length > 1 && (
        <div className="rv-sets" role="group" aria-label="Choose a review set">
          {sets.map((s) => (
            <button key={s.set_id} className={`lab-chip ${s.set_id === setId ? "on" : ""}`} aria-pressed={s.set_id === setId} onClick={() => setSetId(s.set_id)}>
              {s.title} · {s.n}
            </button>
          ))}
        </div>
      )}

      {queue.synthetic && (
        <p className="rv-banner" role="note">
          <b>PRACTICE DATA (synthetic).</b> These images are simulated with known answers so you can learn. Nothing on this set is a real
          detection. Real candidates appear here once the search has run on new SPHEREx data.
        </p>
      )}

      <div className="rv-progress" aria-label="Progress">
        <div className="rv-bar"><span style={{ width: `${(100 * workDone.done) / Math.max(workDone.total, 1)}%` }} /></div>
        <span>{workDone.done} / {workDone.total} reviewed</span>
        {stats.goldSeen > 0 && <span>· practice score {stats.goldRight}/{stats.goldSeen}</span>}
        {stats.decided > 0 && <span>· you agree with the model on {Math.round((100 * stats.agreeModel) / stats.decided)}%</span>}
      </div>

      {phase === "intro" && (
        <section className="glass rv-intro">
          <h2>How it works (1 minute)</h2>
          <ol>
            <li><b>Look.</b> Each candidate shows the same tiny patch of sky twice: <b>OLD</b> and <b>NEW</b>. The crosshair marks the suspicious dot. "Blink" flips between them.</li>
            <li><b>Decide.</b> A real mover is a round, star-sized dot that is only in NEW. Fakes are sharp pixels, black/white pairs, blobs or lines.</li>
            <li><b>Answer</b> with the buttons or keys <kbd>1</kbd> real · <kbd>2</kbd> artefact · <kbd>3</kbd> not sure. <kbd>Z</kbd> undoes.</li>
          </ol>
          <p>{practice.length ? `First, ${practice.length} practice examples with known answers. You get feedback after each.` : "There are no practice items in this set."}</p>
          <button className="button primary" onClick={() => setPhase(practice.length ? "practice" : "work")}>
            {practice.length ? "Start practice" : "Start reviewing"} →
          </button>
          {practice.length > 0 && <button className="text-link rv-skip" onClick={() => setPhase("work")}>Skip practice</button>}
        </section>
      )}

      {phase !== "intro" && allDone && !feedback && (
        <section className="glass rv-intro">
          <h2>All done — thank you!</h2>
          <p>You reviewed {workDone.done} candidates: {workDone.real} real, {workDone.bogus} artefacts, {workDone.unsure} not sure. Download your answers and send them to the team; they become training labels for the model.</p>
        </section>
      )}

      {phase !== "intro" && current && !(allDone && !feedback) && (
        <section className="rv-work">
          <Viewer setId={queue.set_id} c={current} view={view} setView={setView} />

          <div className="rv-panel">
            <div className="glass rv-card">
              <small>{phase === "practice" ? `PRACTICE ${pos + 1} OF ${practice.length}` : `CANDIDATE ${pos + 1} OF ${work.length}`}{current.gold && phase === "work" ? " · KNOWN ANSWER" : ""}</small>
              <h2>Real mover or artefact?</h2>

              {!feedback && (
                <div className="rv-answers">
                  <button className={`rv-ans real ${lbl?.answer === "real" ? "chosen" : ""}`} onClick={() => answer("real")}>
                    <kbd>1</kbd> Real mover
                  </button>
                  <button className={`rv-ans bogus ${lbl?.answer === "bogus" ? "chosen" : ""}`} onClick={() => answer("bogus")}>
                    <kbd>2</kbd> Artefact
                  </button>
                  <button className={`rv-ans unsure ${lbl?.answer === "unsure" ? "chosen" : ""}`} onClick={() => answer("unsure")}>
                    <kbd>3</kbd> Not sure
                  </button>
                </div>
              )}

              {feedback && current.gold && (
                <div className={`rv-feedback ${feedback.answer === current.gold.answer ? "right" : feedback.answer === "unsure" ? "neutral" : "wrong"}`} role="status">
                  <b>
                    {feedback.answer === current.gold.answer ? "Correct!" : feedback.answer === "unsure" ? "Good to be careful." : "Not quite."}{" "}
                    This one is {current.gold.answer === "real" ? "a real mover" : "an artefact"}.
                  </b>
                  <p>{KIND_HELP[current.gold.kind] ?? ""}</p>
                  <button className="button primary" onClick={advancePractice} autoFocus>
                    {pos + 1 < practice.length ? "Next example" : "Start the real queue"} →
                  </button>
                </div>
              )}

              <div className={`rv-hint ${revealHint ? v?.tone : "hidden"}`}>
                {revealHint ? (
                  <>
                    <span>Model says: <b>{v?.text}</b></span>
                    <span className="rv-score">{Math.round(current.ml_score * 100)}%</span>
                  </>
                ) : (
                  <span>The model's opinion appears after you answer, so it does not sway you.</span>
                )}
              </div>

              <div className="rv-tools">
                <button className="text-link" onClick={undo} disabled={!undoStack.current.length}>↶ Undo (Z)</button>
                {phase === "work" && <>
                  <button className="text-link" onClick={() => setPos((p) => Math.max(0, p - 1))} disabled={pos === 0}>← Prev</button>
                  <button className="text-link" onClick={() => setPos((p) => Math.min(work.length - 1, p + 1))} disabled={pos >= work.length - 1}>Next →</button>
                </>}
                <label className="rv-toggle">
                  <input type="checkbox" checked={hintFirst} onChange={(e) => setHintFirst(e.target.checked)} /> show model first
                </label>
              </div>
              <p className="rv-keys"><kbd>Space</kbd> blink on/off · <kbd>D</kbd> difference · <kbd>←</kbd><kbd>→</kbd> move</p>
            </div>

            <details className="glass rv-details">
              <summary>Details for this candidate</summary>
              <dl>
                <dt>Position</dt><dd>RA {current.ra_deg.toFixed(4)}°, Dec {current.dec_deg.toFixed(4)}°</dd>
                {Object.entries(current.features).map(([k, val]) => (
                  <Fragment key={k}><dt>{k}</dt><dd>{val ?? "—"}</dd></Fragment>
                ))}
                <dt>Image pair</dt><dd>{current.group}</dd>
              </dl>
              {!queue.synthetic && (
                <a className="text-link" href={`#/live?ra=${current.ra_deg}&dec=${current.dec_deg}&name=Candidate%20${current.id}`}>
                  Open this spot in the sky viewer →
                </a>
              )}
            </details>
          </div>
        </section>
      )}

      {phase !== "intro" && <Guide />}

      <section className="glass rv-export">
        <div>
          <h3>Your answers</h3>
          <p>Saved in this browser only. Download them and send the file to the team; they become new training labels.</p>
        </div>
        <div className="rv-export-row">
          <input aria-label="Your name or nickname (optional)" placeholder="Name or nickname (optional)" value={volunteer} onChange={(e) => setVolunteer(e.target.value)} />
          <button className="button primary" onClick={download} disabled={!stats.done}>Download answers ({stats.done})</button>
          <button className="button ghost" onClick={reset} disabled={!stats.done}>Start over</button>
        </div>
        <small className="rv-model">Ranking model: {queue.model.name}{queue.model.cv_roc_auc != null ? ` · cross-validated AUC ${queue.model.cv_roc_auc} on ${queue.model.trained_on === "synthetic" ? "synthetic data" : "labelled data"}` : ""}</small>
      </section>

      {toast && <div className="rv-toast" role="status">{toast}</div>}
    </main>
  );
}
