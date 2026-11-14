import { useEffect, useState } from 'react';
import type { Field, FieldSummary, Frame } from './contract';
import { imageUrl, loadField, loadIndex } from './data/loader';

const date = (frame: Frame) => frame.obs_time_utc.slice(0, 10);
const metadata = (frame: Frame) => (frame.band ?? 'Detector ' + frame.detector) + ' · ' + frame.wavelength_um + ' µm';

function Viewer({ field }: { field: Field }) {
  const frames = [...field.frames].sort((a, b) => Date.parse(a.obs_time_utc) - Date.parse(b.obs_time_utc));
  const [a, setA] = useState(0);
  const [b, setB] = useState(Math.min(1, frames.length - 1));
  const [target, setTarget] = useState<'A' | 'B'>('B');
  const [blink, setBlink] = useState(false);
  const [playing, setPlaying] = useState(false);
  const [second, setSecond] = useState(false);
  useEffect(() => {
    if (!blink || !playing) return;
    const timer = window.setInterval(() => setSecond(value => !value), 850);
    return () => window.clearInterval(timer);
  }, [blink, playing, a, b]);

  if (!frames.length) return <p>No frames in this field.</p>;
  const framePanel = (slot: 'A' | 'B', index: number, hidden = false) => {
    const frame = frames[index];
    return <figure key={slot} hidden={hidden}>
      <img src={imageUrl(field.field_id, frame.png)} alt={'Sky field, frame ' + frame.id} />
      <figcaption><strong>{slot} · {date(frame)}</strong><span>{metadata(frame)}</span></figcaption>
    </figure>;
  };
  return <>
    <div className="controls" aria-label="Comparison mode">
      <button aria-pressed={!blink} onClick={() => { setBlink(false); setPlaying(false); }}>Side by side</button>
      <button aria-pressed={blink} disabled={frames.length < 2} onClick={() => {
        if (!blink) { setSecond(false); setBlink(true); setPlaying(true); }
      }}>Blink</button>
      {blink && <button onClick={() => setPlaying(value => !value)}>{playing ? 'Pause' : 'Play'}</button>}
    </div>
    <div className={blink ? 'images blink' : 'images'}>
      {framePanel('A', a, blink && second)}
      {framePanel('B', b, blink && !second)}
    </div>
    <section className="timeline" aria-label="Observation timeline">
      <div className="timeline-head"><h2>Timeline</h2><div className="controls" aria-label="Frame to replace">
        <button aria-pressed={target === 'A'} onClick={() => setTarget('A')}>Set A</button>
        <button aria-pressed={target === 'B'} onClick={() => setTarget('B')}>Set B</button>
      </div></div>
      <ol>{frames.map((frame, i) => <li key={frame.id}>
        <button aria-pressed={i === (target === 'A' ? a : b)} onClick={() => {
          (target === 'A' ? setA : setB)(i);
          setSecond(target === 'B');
        }}>
          <strong>{date(frame)} {i === a && ' · A'}{i === b && ' · B'}</strong><span>{metadata(frame)}</span>
        </button>
      </li>)}</ol>
    </section>
  </>;
}

export default function App() {
  const [index, setIndex] = useState<FieldSummary[]>();
  const [id, setId] = useState('');
  const [field, setField] = useState<Field>();
  const [error, setError] = useState('');
  useEffect(() => {
    const controller = new AbortController();
    loadIndex(controller.signal).then(list => {
      if (controller.signal.aborted) return;
      setIndex(list);
      setId(list[0]?.field_id ?? '');
    }).catch(e => { if (!controller.signal.aborted) setError(e.message); });
    return () => controller.abort();
  }, []);
  useEffect(() => {
    if (!id) return;
    const controller = new AbortController();
    loadField(id, controller.signal).then(value => {
      if (!controller.signal.aborted) setField(value);
    }).catch(e => { if (!controller.signal.aborted) setError(e.message); });
    return () => controller.abort();
  }, [id]);
  const current = field?.field_id === id ? field : undefined;
  return <main>
    <header><div className="brand">✧ SPHEREx</div>
      {current?.provenance.synthetic && <div className="badge">DEMO DATA</div>}
    </header>
    <h1>Compare observations</h1>
    {index && index.length > 0 && <label>Sky field <select value={id} onChange={e => {
      setError(''); setField(undefined); setId(e.target.value);
    }}>{index.map(item => <option key={item.field_id} value={item.field_id}>{item.title}</option>)}</select></label>}
    {error && <p role="alert">{error}</p>}
    {!error && (!index || (id && !current)) && <p role="status">Loading observations…</p>}
    {index?.length === 0 && <p>No sky fields available.</p>}
    {current && <>
      <p className="description">{current.description}</p>
      <Viewer key={current.field_id} field={current} />
    </>}
  </main>;
}
