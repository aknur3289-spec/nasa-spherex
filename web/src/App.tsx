import { GuidedTour } from './ui/GuidedTour';
import type { CSSProperties } from 'react';
import { Starfield } from './ui/Starfield';
import { useEffect, useState } from 'react';
import type { FieldSummary } from './contract';
import { imageUrl, loadField, loadIndex } from './data/loader';
import { BlinkViewer } from './viewer/BlinkViewer';
import { ErrorBoundary } from './viewer/ErrorBoundary';
import { Detectability, DistanceDial } from './viewer/SciencePanels';

const fieldRoute = (id: string) => '#field/' + id;
function Skeleton() {
  return <div className="player-skeleton" role="status" aria-label="Loading observations">
    <div /><span />
  </div>;
}

export default function App() {
  const [route, setRoute] = useState(() => window.location.hash);
  const [index, setIndex] = useState<FieldSummary[]>();
  const [indexError, setIndexError] = useState('');
  const [result, setResult] = useState<{ id: string; field?: Awaited<ReturnType<typeof loadField>>; error?: string }>();
  const view = route === '#limits' ? 'limits' : route === '#dial' ? 'dial' : route.startsWith('#field/') ? 'field' : 'home';
  const selectedId = view === 'field' ? route.slice(7)
    : view === 'dial' ? index?.find(item => item.kind === 'dial')?.field_id
    : view === 'home' ? (index?.find(item => item.kind === 'static') ?? index?.[0])?.field_id
    : undefined;

  useEffect(() => {
    const update = () => setRoute(window.location.hash);
    window.addEventListener('hashchange', update);
    return () => window.removeEventListener('hashchange', update);
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    loadIndex(controller.signal).then(items => {
      if (!controller.signal.aborted) setIndex(items.filter(item => item.status !== 'pending'));
    }).catch(error => {
      if (!controller.signal.aborted) setIndexError(error.message);
    });
    return () => controller.abort();
  }, []);

  useEffect(() => {
    if (!selectedId) return;
    const controller = new AbortController();
    loadField(selectedId, controller.signal).then(field => {
      if (!controller.signal.aborted) setResult({ id: selectedId, field });
    }).catch(error => {
      if (!controller.signal.aborted) setResult({ id: selectedId, error: error.message });
    });
    return () => controller.abort();
  }, [selectedId]);

  const current = result && result.id === selectedId ? result : undefined;
  const field = current?.field;
  const error = indexError || current?.error;
  const pending = !error && (!index || (!!selectedId && !current));
  const dial = field?.kind === 'dial' && view !== 'home';

  return <>
    <Starfield />
    <a className="skip-link" href="#main-content" onClick={event => { event.preventDefault(); document.getElementById("main-content")?.focus(); }}>Skip to content</a>
    <header className="site-header">
      <nav className="site-nav glass" aria-label="Main navigation">
        <a className="wordmark" href="#home"><span className="wordmark-icon" aria-hidden="true">✦</span>Parallax Dial</a>
        <div className="nav-links">
          <a href="#home" aria-current={view === 'home' || view === 'field' ? 'page' : undefined}>Explore</a>
          <a href="#dial" aria-current={view === 'dial' ? 'page' : undefined}>Distance Dial</a>
          <a href="#limits" aria-current={view === 'limits' ? 'page' : undefined}>Detectability</a>
        </div>
      </nav>
    </header>
    <main id="main-content" tabIndex={-1}>
      <div className={view === 'home' ? 'page-intro home-intro' : 'page-intro'}>
        <div className="intro-content">
          {view === 'home' ? <>
            <p className="eyebrow"><span aria-hidden="true">✧</span> SPHEREx Sky Explorer</p>
            <h1>{"See the infrared sky change.".split(" ").map((word, index) => <span key={word}><span className="hero-word" style={{ "--word": index } as CSSProperties}>{word}</span>{" "}</span>)}</h1>
            <p>Compare views of the same patch of sky and see how motion can reveal distance.</p>
            <a className="intro-link" href="#gallery">Browse sky fields <span aria-hidden="true">↓</span></a>
          </> : <>
            <a className="back-link" href="#home">← Explore sky fields</a>
            <h1>{view === 'limits' ? 'What can SPHEREx see?' : view === 'dial' ? 'Distance Dial' : field?.title ?? 'Sky field'}</h1>
            {view === 'dial' && <p>Explore how a change in viewpoint can reveal an object’s distance.</p>}
          </>}
        </div>
      </div>
      <div className="page-body">
        {view === 'limits' ? <Detectability /> : <>
          {error && <p className="glass notice" role="alert">{error}</p>}
          {pending && <Skeleton />}
          {field && <ErrorBoundary key={view + field.field_id}>
            {dial ? <DistanceDial field={field} /> : <BlinkViewer field={field} home={view === 'home'} />}
          </ErrorBoundary>}
          {!pending && !error && !field && <p className="glass notice">No fields available for this view.</p>}
        </>}
        {view === 'home' && <section className="gallery" id="gallery" aria-labelledby="gallery-title">
          <div className="gallery-head">
            <div><h2 id="gallery-title">Explore the sky</h2><p>Choose a field to compare its observation dates.</p></div>

          </div>
          <div className="gallery-grid">
            {index?.map(item => <a className="field-card glass" href={fieldRoute(item.field_id)} key={item.field_id}>
              <img src={imageUrl(item.field_id, item.thumbnail)} alt="" loading="lazy"
                onError={event => { event.currentTarget.hidden = true; }} />
              <div className="field-card-copy">
                <span>{item.kind === 'dial' ? 'Distance dial' : 'Sky field'}</span>
                <h3>{item.title}</h3><span aria-hidden="true" className="card-arrow">↗</span>
              </div>
            </a>)}

          </div>
        </section>}
        <footer>Parallax Dial <span>·</span> An independent SPHEREx sky explorer</footer>
      </div>
      <GuidedTour fieldId={index?.find(item => item.kind === "static")?.field_id} />
    </main>
  </>;
}
