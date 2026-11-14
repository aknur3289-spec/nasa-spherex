import { SkyImage } from '../ui/SkyImage';
import { useEffect, useId, useState } from 'react';
import type { Field, Frame } from '../contract';
import { imageUrl } from '../data/loader';
import './science-panels.css';

const motionQuery = '(prefers-reduced-motion: reduce)';
const format = (value: number) => new Intl.NumberFormat('en', { maximumFractionDigits: 1 }).format(value);

function DialFrame({ frame, fieldId, caption }: { frame?: Frame; fieldId: string; caption: string }) {
  const [failed, setFailed] = useState(false);
  return <figure className="science-frame">
    <div className="science-image">
      {frame && !failed
        ? <><SkyImage src={imageUrl(fieldId, frame.png)} alt={caption} onError={() => setFailed(true)} /><span className="crosshair" aria-hidden="true" /></>
        : <div className="image-placeholder" role="status">Image unavailable.</div>}
    </div>
    <figcaption>{caption}</figcaption>
  </figure>;
}

export function DistanceDial({ field }: { field: Field }) {
  const [selected, setSelected] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [reducedMotion, setReducedMotion] = useState(() => window.matchMedia(motionQuery).matches);
  const dial = field.dial;
  const steps = [...(dial?.steps ?? [])].sort((a, b) => a.distance_au - b.distance_au);
  const length = steps.length;
  useEffect(() => {
    const media = window.matchMedia(motionQuery);
    const update = () => setReducedMotion(media.matches);
    media.addEventListener('change', update);
    return () => media.removeEventListener('change', update);
  }, []);
  useEffect(() => {
    if (!playing || reducedMotion || length < 2) return;
    let request = 0;
    const started = performance.now();
    const sweep = (now: number) => {
      const progress = Math.min(1, (now - started) / 8000);
      setSelected(Math.round((length - 1) * (.5 + .5 * Math.cos(progress * Math.PI))));
      if (progress < 1) request = requestAnimationFrame(sweep);
      else setPlaying(false);
    };
    request = requestAnimationFrame(sweep);
    return () => cancelAnimationFrame(request);
  }, [playing, reducedMotion, length]);
  if (!dial || !length) return null;
  const step = steps[selected] ?? steps[0];
  const reference = field.frames.find(frame => frame.id === dial.reference_frame);
  const candidate = field.frames.find(frame => frame.id === step.frame);
  const start = steps[0].distance_au;
  const end = steps[length - 1].distance_au;
  const snr = steps.map(point => point.snr);
  const minimum = Math.min(0, ...snr);
  const maximum = Math.max(0, ...snr);
  const x = (au: number) => 32 + 326 * Math.log(au / start) / (Math.log(end / start) || 1);
  const y = (signal: number) => 130 - 100 * (signal - minimum) / (maximum - minimum || 1);
  const path = steps
    .map((point, index) => (index ? 'L' : 'M') + x(point.distance_au) + ' ' + y(point.snr)).join(' ');
  const truthInRange = dial.truth.distance_au >= start && dial.truth.distance_au <= end;
  const truthLabel = field.provenance.synthetic ? 'Synthetic reference' : dial.truth.source;
  return <section className="science-section" aria-label="Distance dial">
    {field.provenance.synthetic && <p className="science-note">Synthetic demonstration · images and focus curve use fixture data.</p>}
    <div className="science-images">
      <DialFrame key={'reference-' + reference?.id} frame={reference} fieldId={field.field_id}
        caption={'Seen on ' + (reference?.obs_time_utc.slice(0, 10) ?? 'the reference date')} />
      <DialFrame key={'candidate-' + candidate?.id} frame={candidate} fieldId={field.field_id}
        caption={'Later frame · ' + (candidate?.obs_time_utc.slice(0, 10) ?? 'date unavailable') + ' · ' + format(step.distance_au) + ' AU hypothesis'} />
    </div>
    <div className="science-glass science-control">
      <label htmlFor="distance-control">Distance hypothesis <output>{format(step.distance_au)} AU</output></label>
      <div className="science-range-row">
        <input id="distance-control" type="range" min="0" max={Math.max(0, length - 1)} value={selected}
          disabled={length < 2} aria-valuetext={format(step.distance_au) + ' AU'} onChange={event => {
            setPlaying(false);
            setSelected(event.currentTarget.valueAsNumber);
          }} />
        {!reducedMotion && length > 1 && <button type="button" onClick={() => setPlaying(value => !value)}>{playing ? 'Stop sweep' : 'Sweep'}</button>}
      </div>
      <div className="science-axis-labels"><span>{format(start)} AU</span>{[30, 100, 300].filter(tick => tick > start && tick < end).map(tick => <span key={tick}>{tick}</span>)}<span>{format(end)} AU</span></div>
    </div>
    <div className="science-glass science-chart">
      <h3>Signal at the crosshair</h3>
      <p className="science-peak">{field.provenance.synthetic ? 'Synthetic peak' : 'Measured'} {format(dial.peak_distance_au)} AU</p>
      <svg viewBox="0 0 380 156" role="img" aria-label={'Signal-to-noise ratio by distance. Current signal: ' + format(step.snr)}>
        <path d="M32 28V130H358" fill="none" stroke="currentColor" opacity=".32" />
        {[30, 100, 300, 1000].filter(distance => distance >= start && distance <= end).map(distance =>
          <g key={distance}><path d={'M' + x(distance) + ' 30V130'} stroke="currentColor" opacity=".12" />
            <text x={x(distance)} y="148" textAnchor="middle">{distance}</text></g>)}
        {truthInRange && <line x1={x(dial.truth.distance_au)} x2={x(dial.truth.distance_au)}
          y1="22" y2="130" stroke="currentColor" opacity=".75" strokeDasharray="3 4" />}
        <path d={path} fill="none" stroke="#d4deee" strokeWidth="2" />
        <circle cx={x(step.distance_au)} cy={y(step.snr)} r="4" fill="#fff" />
        {dial.peak_distance_au >= start && dial.peak_distance_au <= end &&
          <path d={'M' + x(dial.peak_distance_au) + ' 18v-10'} stroke="#f2b441" strokeWidth="2" />}
      </svg>
      <p className="science-note">{truthLabel} {format(dial.truth.distance_au)} AU · Empty-sky curve unavailable for this field.</p>
    </div>
  </section>;
}

export function Detectability() {
  const [count, setCount] = useState(16);
  const inputId = useId();
  const gain = 2.5 * Math.log10(Math.sqrt(count));
  // At fixed apparent brightness, the reflected-light model gives radius proportional to distance squared.
  const axisWidth = 292;
  const x = (index: number) => 42 + axisWidth * index / 48;
  const threshold = (index: number, stackGain: number) => {
    const distance = 30 * (1000 / 30) ** (index / 48);
    const radius = (distance / 100) ** 2 * 10 ** (-stackGain / 5);
    return Math.max(20, Math.min(158, 158 - 138 * (Math.log10(radius) + 2) / 4));
  };
  const outline = (stackGain: number) => Array.from({ length: 49 }, (_, index) =>
    (index ? 'L' : 'M') + x(index) + ' ' + threshold(index, stackGain)).join(' ');
  return <section className="science-section science-glass science-chart" aria-label="What can SPHEREx see?">
    <p className="science-note">Illustrative reflected-light model · relative to an illustrative one-frame threshold at 100 AU. SPHEREx calibration pending.</p>
    <svg viewBox="0 0 360 196" role="img" aria-label="Relative body radius versus distance, showing single-frame, stack-only and below-limit regions">
      <path d="M42 20H334V158H42Z" fill="#ffffff08" />
      <path d={outline(gain) + 'L334 20H42Z'} fill="#ffffff20" />
      <path d={outline(0) + 'L334 20H42Z'} fill="#ffffff32" />
      <path d={outline(gain)} fill="none" stroke="#a9b4c8" strokeDasharray="4 4" />
      <path d={outline(0)} fill="none" stroke="#e0e6f0" />
      <path d="M42 20V158H334" fill="none" stroke="currentColor" opacity=".45" />
      <text x="14" y="100" transform="rotate(-90 14 100)">Relative radius</text>
      <text x="42" y="176">30</text><text x="142" y="176">100</text><text x="334" y="176" textAnchor="end">1000</text>
      <text x="190" y="192" textAnchor="middle">Distance (AU)</text>
    </svg>
    <ul className="science-legend"><li>Single frame</li><li>Stack only</li><li>Below threshold</li></ul>
    <label className="science-frame-count" htmlFor={inputId}>Stack size <output>{count} frames · +{format(gain)} mag</output></label>
    <input id={inputId} type="range" min="1" max="300" value={count} onChange={event => setCount(event.currentTarget.valueAsNumber)} />
    <p className="science-note">Order-of-magnitude estimate in reflected light. Ignores methane absorption and differences between visible and near-infrared brightness.</p>
  </section>;
}
