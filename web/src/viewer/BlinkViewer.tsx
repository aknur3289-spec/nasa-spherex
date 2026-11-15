import { RecordClip } from './RecordClip';
import { DifferenceImage } from './DifferenceImage';
import { SkyImage } from '../ui/SkyImage';
import type { TimelineEntry } from '../contract';
import { useEffect, useRef, useState } from 'react';
import type { Field, Frame } from '../contract';
import { imageUrl } from '../data/loader';
import { FrameInfo } from './FrameInfo';
import { PairPicker } from './PairPicker';
import { TrustBadge } from './TrustBadge';
import './Viewer.css';

const modes = ['Blink', 'Slider', 'Difference', 'Timelapse'] as const;
type Mode = (typeof modes)[number] | 'Side by side' | 'Manual';
const shortcuts: Record<string, Mode> = { 1: 'Side by side', 2: 'Blink', 3: 'Manual' };
const motionQuery = '(prefers-reduced-motion: reduce)';
const date = (frame: Frame) => frame.obs_time_utc.slice(0, 10);

function FrameImage({ frame, fieldId }: { frame: Frame; fieldId: string }) {
  const [failed, setFailed] = useState(false);
  return failed
    ? <div className="image-placeholder" role="status">Image unavailable for frame {frame.id}.</div>
    : <SkyImage src={imageUrl(fieldId, frame.png)} alt={'Sky field, frame ' + frame.id} onError={() => setFailed(true)} />;
}

export function BlinkViewer({ field, home = false }: { field: Field & { timeline?: TimelineEntry[] }; home?: boolean }) {
  const pairs = field.pairs.filter(pair => pair.a !== pair.b);
  const byId = new Map(field.frames.map(frame => [frame.id, frame]));
  const frames = field.timeline?.flatMap(entry => byId.get(entry.frame_id) ?? []) ??
    [...field.frames].sort((a, b) => Date.parse(a.obs_time_utc) - Date.parse(b.obs_time_utc));
  const [selected, setSelected] = useState(() => Math.max(0, pairs.findIndex(pair => pair.trust === 'high')));
  const [mode, setMode] = useState<Mode>(home ? 'Timelapse' : 'Side by side');
  const [second, setSecond] = useState(false);
  const [epoch, setEpoch] = useState(0);
  const [speed, setSpeed] = useState(1);
  const [split, setSplit] = useState(50);
  const [honest, setHonest] = useState(true);
  const [naiveA, setNaiveA] = useState(frames[0]?.id);
  const [naiveB, setNaiveB] = useState(frames[1]?.id);
  const [reducedMotion, setReducedMotion] = useState(() => window.matchMedia(motionQuery).matches);
  const [paused, setPaused] = useState(false);
  const [expanded, setExpanded] = useState(true);
  const dragStart = useRef<number | null>(null);
  const dragged = useRef(false);
  const stage = useRef<HTMLDivElement>(null);
  const pair = pairs[selected];
  const a = frames.find(frame => frame.id === (honest ? pair?.a : naiveA)) ?? frames[0];
  const b = frames.find(frame => frame.id !== a?.id && frame.id === (honest ? pair?.b : naiveB))
    ?? frames.find(frame => frame.id !== a?.id);
  const timeline = frames[epoch] ?? a;
  const playing = !paused && !reducedMotion;
  const timed = mode === 'Blink' || mode === 'Timelapse';

  useEffect(() => {
    const media = window.matchMedia(motionQuery);
    const update = () => setReducedMotion(media.matches);
    media.addEventListener('change', update);
    return () => media.removeEventListener('change', update);
  }, []);
  useEffect(() => {
    if (!b || !playing || !timed) return;
    const next = (epoch + 1) % frames.length;
    const days = Math.abs(frames[next].mjd - frames[epoch].mjd);
    const delay = mode === 'Timelapse' ? Math.max(350, Math.min(1600, days * 8)) : 850;
    const timer = window.setInterval(() => {
      if (mode === 'Timelapse') setEpoch(next);
      else setSecond(value => !value);
    }, delay / speed);
    return () => window.clearInterval(timer);
  }, [b, epoch, frames.length, mode, playing, selected, speed, timed]);

  useEffect(() => {
    if (mode !== 'Timelapse') return;
    for (const frame of field.frames) {
      const img = new Image();
      img.src = imageUrl(field.field_id, frame.png);
    }
  }, [field, mode]);

  function choosePair(index: number) {
    setSelected(index);
    setSecond(false);
    setHonest(true);
  }

  function toggle() {
    if (!b) return;
    if (mode === 'Timelapse') {
      setEpoch(value => (value + 1) % frames.length);
      return;
    }
    if (mode !== 'Blink' && mode !== 'Manual') setMode('Manual');
    setSecond(value => !value);
  }

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.defaultPrevented || event.altKey || event.ctrlKey || event.metaKey ||
          (event.target instanceof Element && event.target.closest('input, select, textarea, button, a, [contenteditable]'))) return;
      if (event.code === 'Space' || event.key === ' ') {
        event.preventDefault();
        if (!event.repeat) toggle();
      } else if (pairs.length && (event.key === 'ArrowLeft' || event.key === 'ArrowRight')) {
        event.preventDefault();
        const direction = event.key === 'ArrowLeft' ? -1 : 1;
        choosePair((selected + direction + pairs.length) % pairs.length);
      } else if (b && shortcuts[event.key]) {
        setMode(shortcuts[event.key]);
      }
    }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [b, frames.length, mode, pairs.length, selected]);

  if (!a) return <p>No frames in this field.</p>;
  const comparison = mode === 'Slider' || mode === 'Difference';
  const single = mode === 'Blink' || mode === 'Manual';
  const showBoth = !!b && mode === 'Side by side';
  const showTimeline = mode === 'Timelapse' && timeline;
  const active = single && second && b ? b : a;

  function panel(frame: Frame, slot: 'A' | 'B', hidden = false) {
    return <figure key={slot + '-' + frame.id} hidden={hidden} className="observation-panel">
      <FrameImage frame={frame} fieldId={field.field_id} />
      <time className="frame-stamp" dateTime={frame.obs_time_utc}>{mode === "Timelapse" ? "" : slot + " · "}{date(frame)}</time>
    </figure>;
  }

  function naivePicker(slot: 'A' | 'B', current: Frame, other: Frame) {
    return <label>Frame {slot} <select value={current.id}
      onChange={event => (slot === 'A' ? setNaiveA : setNaiveB)(event.target.value)}>
      {frames.map(frame => <option value={frame.id} key={frame.id} disabled={frame.id === other.id}>{date(frame)}</option>)}
    </select></label>;
  }

  return <section className={home ? 'observation-viewer home-player' : 'observation-viewer'} aria-label="Observation viewer">
    {field.provenance.synthetic && <p className="badge viewer-synthetic">Synthetic data</p>}
    {!home && <p className="description">{field.description}</p>}
    <div ref={stage} className={'observation-stage' + (showBoth ? ' observation-pair' : '')} onPointerUp={event => {
      if (event.pointerType === 'touch' && (event.target as Element).closest('img, .image-placeholder')) toggle();
    }}>
      {mode === 'Difference' && b ? <figure>
        <DifferenceImage key={a.id + '/' + b.id} a={a} b={b} fieldId={field.field_id} path={honest ? pair?.diff_png : undefined} />
      </figure> : comparison && b ? <figure className={'observation-composite ' + mode.toLowerCase()}>
        <FrameImage key={a.id} frame={a} fieldId={field.field_id} />
        <div className="observation-overlay" style={mode === 'Slider' ? { clipPath: 'inset(0 ' + (100 - split) + '% 0 0)' } : undefined}>
          <FrameImage key={b.id} frame={b} fieldId={field.field_id} />
        </div>
        {mode === 'Slider' && <div className="observation-divider" style={{ left: split + '%' }} aria-hidden="true" />}
      </figure> : showTimeline ? panel(timeline, 'A') : <>
        {panel(a, 'A', single && second && !!b)}
        {b && panel(b, 'B', !showBoth && !(single && second))}
      </>}
    </div>
    <div className={'observation-sheet' + (expanded ? '' : ' sheet-collapsed')}>
      {!home && <button className="sheet-handle" type="button" aria-expanded={expanded} aria-label="Toggle comparison details"
        onClick={event => { if (!dragged.current || event.detail === 0) setExpanded(value => !value); }}
        onPointerDown={event => {
          dragged.current = false;
          if (event.pointerType !== 'touch') return;
          dragStart.current = event.clientY;
          event.currentTarget.setPointerCapture(event.pointerId);
        }}
        onPointerCancel={() => { dragStart.current = null; }}
        onPointerUp={event => {
          if (dragStart.current === null) return;
          const travel = event.clientY - dragStart.current;
          dragStart.current = null;
          if (Math.abs(travel) > 25) {
            dragged.current = true;
            setExpanded(travel < 0);
          }
        }} />}
      {b && <div className="observation-toolbar">
        <div className="viewer-segmented" aria-label="Comparison mode">
          {modes.map(item => <button key={item} data-mode={item} aria-pressed={mode === item} onClick={() => setMode(item)}>{item}</button>)}
          {!home && <button aria-pressed={mode === 'Side by side'} onClick={() => setMode('Side by side')}>Side by side</button>}
        </div>
        {timed && !reducedMotion && <button onClick={() => setPaused(value => !value)}>{paused ? 'Play' : 'Pause'}</button>}
        {(single || showTimeline) && <button onClick={toggle}>Toggle frame</button>}
        {mode === 'Timelapse' && <RecordClip stage={stage} />}
        {timed && <label>Speed <select value={speed} onChange={event => setSpeed(Number(event.target.value))}>
          {[0.5, 1, 2].map(value => <option value={value} key={value}>{value}×</option>)}
        </select></label>}
      </div>}
      {showTimeline && <div className="observation-scrub">
        <input type="range" aria-label="Observation date" aria-valuetext={date(timeline)}
          min={0} max={frames.length - 1} value={epoch} onChange={event => {
            setEpoch(Number(event.target.value));
            setPaused(true);
          }} />
        <div className="observation-dates">{frames.map(frame => <time key={frame.id} dateTime={frame.obs_time_utc}>{date(frame)}</time>)}</div>
      </div>}
      {comparison && mode === 'Slider' && <label className="comparison-position">Comparison position
        <input type="range" min={0} max={100} value={split} onChange={event => setSplit(Number(event.target.value))} />
      </label>}
      <div className="observation-details">
        {!home && b && <div className="viewer-segmented" aria-label="Pair selection">
          <button aria-pressed={!honest} onClick={() => setHonest(false)}>Naive</button>
          <button aria-pressed={honest} onClick={() => setHonest(true)}>Honest</button>
        </div>}
        {honest ? <PairPicker frames={frames} pairs={pairs} selected={selected} onChange={choosePair} />
          : b && <div className="observation-toolbar">{naivePicker('A', a, b)}{naivePicker('B', b, a)}</div>}
        {honest && pair && <TrustBadge pair={pair} />}
        {honest && !pair && b && <p>No documented trust rating for this field.</p>}
        {!honest && <p>Manual pairing · trust unverified</p>}
        <figure className="observation-meta">
          <FrameInfo frame={showTimeline ? timeline : active} slot={single && active === b ? 'B' : 'A'} />
        </figure>
        {b && (showBoth || comparison) && <figure className="observation-meta"><FrameInfo frame={b} slot="B" /></figure>}
        {mode === 'Difference' && <p>Absolute difference of displayed grayscale pixels.</p>}
      </div>
    </div>
  </section>;
}
