import { useEffect, useRef, useState } from 'react';
import type { Field, Frame, TimelineEntry } from '../contract';
import { imageUrl } from '../data/loader';
import { copy, day } from '../copy';
import { SkyImage } from '../ui/SkyImage';
import { DifferenceImage } from './DifferenceImage';
import { DistanceDial } from './SciencePanels';
import { RecordClip } from './RecordClip';
import { TrustBadge } from './TrustBadge';

const modes = ['play', 'compare', 'changes', 'distance'] as const;
const labels = [copy.play, copy.compare, copy.change, copy.distance];
const query = '(prefers-reduced-motion: reduce)';

function FrameImage({ field, frame }: { field: Field; frame: Frame }) {
  const [failed, setFailed] = useState(false);
  return failed ? <div role="status" className="image-placeholder">{copy.unavailable} · {day(frame.obs_time_utc)}</div>
    : <SkyImage src={imageUrl(field.field_id, frame.png)} alt={day(frame.obs_time_utc)} onError={() => setFailed(true)} />;
}

export function SimpleViewer({ field, search }: { field: Field & { timeline?: TimelineEntry[] }; search?: string }) {
  const params = new URLSearchParams(search);
  const requested = modes.find(mode => mode === params.get('mode')) ?? 'play';
  const pairs = field.pairs.filter(pair => pair.a !== pair.b);
  const best = pairs.find(pair => pair.trust === 'high') ?? [...pairs].sort((a,b) => a.dlambda_frac-b.dlambda_frac)[0];
  const frames = field.timeline
    ? field.timeline.flatMap(entry => field.frames.find(frame => frame.id === entry.frame_id) ?? [])
    : [...field.frames].sort((a,b) => Date.parse(a.obs_time_utc)-Date.parse(b.obs_time_utc));
  const defaultA = params.get('a') ?? best?.a;
  const defaultB = params.get('b') ?? best?.b;
  const [mode, setMode] = useState(requested);
  const [aId, setA] = useState(defaultA);
  const [bId, setB] = useState(defaultB);
  const [epoch, setEpoch] = useState(0);
  const [speed, setSpeed] = useState(1);
  const [split, setSplit] = useState(50);
  const [reduced, setReduced] = useState(() => matchMedia(query).matches);
  const [playing, setPlaying] = useState(!reduced);
  const [hint, setHint] = useState(() => !sessionStorage.getItem('parallax-interacted'));
  const stage = useRef<HTMLDivElement>(null);
  const active = frames[epoch] ?? frames[0];
  const before = frames.find(frame => frame.id === aId) ?? frames.find(frame => frame.id === best?.a);
  const after = frames.find(frame => frame.id === bId && frame.id !== before?.id) ??
    frames.find(frame => frame.id === best?.b && frame.id !== before?.id) ??
    frames.find(frame => frame.id !== before?.id);
  const pair = pairs.find(pair => pair.a === before?.id && pair.b === after?.id);
  const validMode = mode === 'distance' && field.kind !== 'dial' || (mode === 'compare' || mode === 'changes') && !best ? 'play' : mode;

  useEffect(() => {
    const media = matchMedia(query);
    const update = () => { setReduced(media.matches); if (media.matches) setPlaying(false); };
    media.addEventListener('change', update);
    return () => media.removeEventListener('change', update);
  }, []);
  useEffect(() => {
    setMode(requested);
    setA(defaultA);
    setB(defaultB);
  }, [requested, defaultA, defaultB]);
  useEffect(() => {
    if (validMode !== 'play' || !playing || frames.length < 2) return;
    const timer = window.setTimeout(() => {
      if (epoch >= frames.length - 1) setPlaying(false);
      else setEpoch(epoch + 1);
    }, 850 / speed);
    return () => clearTimeout(timer);
  }, [epoch, frames.length, playing, speed, validMode]);
  useEffect(() => {
    if (!active) return;
    frames.slice(Math.max(0, epoch-3), epoch+4).forEach(frame => {
      if (frame === active) return;
      const img = new Image();
      img.src = imageUrl(field.field_id, frame.png);
    });
  }, [epoch, field]);

  function updateUrl(next: string, a?: string, b?: string) {
    const state = new URLSearchParams(location.hash.split('?')[1]);
    state.set('mode', next);
    if (a) state.set('a', a);
    if (b) state.set('b', b);
    history.replaceState(null, '', '#/field/' + field.field_id + '?' + state);
  }
  function dismissHint() {
    setHint(false);
    sessionStorage.setItem('parallax-interacted', '1');
  }
  function choose(next: typeof mode) {
    if ((next === 'compare' || next === 'changes') && !best || next === 'distance' && field.kind !== 'dial') return;
    setMode(next); updateUrl(next, before?.id, after?.id); dismissHint();
  }
  function toggle() {
    dismissHint();
    if (!playing && epoch === frames.length - 1) setEpoch(0);
    setPlaying(!playing);
  }
  useEffect(() => {
    function keyboard(event: KeyboardEvent) {
      if (event.altKey || event.ctrlKey || event.metaKey || (event.target instanceof Element &&
        event.target.closest('button,select,input,a,summary,textarea,[contenteditable]'))) return;
      const next = modes[Number(event.key)-1];
      if (next && event.key !== '4') choose(next);
      if (validMode !== 'play') return;
      if (event.code === 'Space' || event.key === ' ') { event.preventDefault(); if (!event.repeat) toggle(); }
      if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') {
        event.preventDefault(); dismissHint(); setPlaying(false);
        setEpoch(value => Math.max(0, Math.min(frames.length - 1, value + (event.key === 'ArrowLeft' ? -1 : 1))));
      }
    }
    window.addEventListener('keydown', keyboard);
    return () => window.removeEventListener('keydown', keyboard);
  });
  if (!active) return <p>{copy.noFrames}</p>;
  const current = validMode === 'play' ? active : before ?? active;
  const ticks = frames.filter((_, index) => index === 0 || index === frames.length - 1 || index % Math.ceil(frames.length / 4) === 0);

  return <div className="viewer-layout">
    <section className="player">
      {validMode === 'distance' ? <>
        <ol className="dial-guide">
          <li>{copy.seen} {day((field.frames.find(frame => frame.id === field.dial?.reference_frame) ?? active).obs_time_utc)}.</li>
          <li>{copy.earth}</li><li>{copy.align}</li>
        </ol>
        <DistanceDial field={field} />
      </> : <div className="image-area" ref={stage} onPointerDown={dismissHint}>
        {validMode === 'changes' && before && after
          ? <DifferenceImage key={before.id + ':' + after.id} fieldId={field.field_id} a={before} b={after} path={pair?.diff_png} />
          : validMode === 'compare' && before && after ? <div className="comparison">
            <FrameImage key={after.id} field={field} frame={after} />
            <div className="comparison-overlay" style={{ clipPath: 'inset(0 ' + (100 - split) + '% 0 0)' }}>
              <FrameImage key={before.id} field={field} frame={before} />
            </div>
          </div> : <FrameImage key={active.id} field={field} frame={active} />}
        <time className="date-badge" dateTime={current.obs_time_utc}>{day(current.obs_time_utc)}{field.provenance.synthetic && ' · ' + copy.synthetic}</time>
        {validMode === 'play' && hint && <button className="first-hint" onClick={toggle}>{copy.hint}</button>}
      </div>}
      {validMode === 'play' && <div className="transport">
        <button className="play-button" aria-label={playing ? copy.pause : copy.start} title={playing ? copy.pause : copy.start}
          onClick={toggle} disabled={frames.length < 2}>{playing ? '❚❚' : '▶'}</button>
        <div className="scrubber">
          <input type="range" min={0} max={frames.length-1} value={epoch} aria-label={copy.scrub} title={copy.scrub}
            aria-valuetext={day(active.obs_time_utc)} onChange={event => {
              setPlaying(false); dismissHint(); setEpoch(event.currentTarget.valueAsNumber);
            }} />
          <div className="date-ticks">{ticks.map(frame => <time key={frame.id}>{day(frame.obs_time_utc)}</time>)}</div>
        </div>
        <details className="more"><summary title={copy.more} aria-label={copy.more}>⋯</summary>
          <div className="more-menu">
            <label>{copy.speed}<select title={copy.speed} value={speed} onChange={event => setSpeed(Number(event.target.value))}>
              {[.5,1,2].map(value => <option key={value}>{value}</option>)}
            </select></label>
            <RecordClip stage={stage} />
          </div>
        </details>
      </div>}
      {validMode === 'compare' && before && after && <>
        <input type="range" min={0} max={100} value={split} className="compare-slider" aria-label={copy.split} title={copy.split}
          onChange={event => setSplit(event.currentTarget.valueAsNumber)} />
        <div className="date-pickers">{([copy.before, copy.after] as const).map((label, index) =>
          <label key={label}>{label}<select title={label} value={index ? after.id : before.id} onChange={event => {
            const value = event.target.value;
            if (index) setB(value); else setA(value);
            updateUrl(mode, index ? before.id : value, index ? value : after.id);
          }}>{frames.map(frame => <option key={frame.id} value={frame.id} disabled={frame.id === (index ? before.id : after.id)}>
            {day(frame.obs_time_utc)}</option>)}</select></label>)}</div>
      </>}
      {validMode === 'changes' && <p>{copy.changes}</p>}
      <div className="mode-switch" aria-label={copy.modes}>
        {modes.slice(0, field.kind === 'dial' ? 4 : 3).map((value, index) => <button key={value} title={labels[index]}
          aria-pressed={validMode === value} disabled={(value === 'compare' || value === 'changes') && !best} onClick={() => choose(value)}>
          {labels[index]}</button>)}
      </div>
      {!best && <p className="muted">{copy.noPair}</p>}
    </section>
    <aside className="information">
      <h2>{copy.what}</h2><p>{copy.explanation}</p>
      {field.provenance.synthetic && <span className="synthetic">{copy.synthetic}</span>}
      <details open><summary title={copy.details}>{copy.details}</summary>
        {(validMode === 'play' || !after ? [current] : [current, after]).map(frame => <div className="metadata" key={frame.id}>
          <div>{day(frame.obs_time_utc)} · {frame.wavelength_um.toFixed(2)} µm</div>
          <div>{copy.detector} {frame.detector}{frame.band && ' · ' + frame.band}</div>
          {!field.provenance.synthetic && <a href={frame.source_url} target="_blank" rel="noopener">{copy.source}</a>}
        </div>)}
      </details>
      {best && <details><summary title={copy.why}>{copy.why}</summary><p>{copy.trust}</p>
        {(validMode === 'play' ? best : pair) && <TrustBadge pair={(validMode === 'play' ? best : pair)!} />}
      </details>}
      <a href="#/limits">{copy.planet}</a>
    </aside>
  </div>;
}
