import { useEffect, useState } from 'react';
import type { FieldSummary } from './contract';
import { imageUrl, loadField, loadIndex, fieldExists } from './data/loader';
import { copy, day } from './copy';
import { SimpleViewer } from './viewer/SimpleViewer';
import { Detectability } from './viewer/SciencePanels';
import { ErrorBoundary } from './viewer/ErrorBoundary';

export default function App() {
  const [index, setIndex] = useState<FieldSummary[]>();
  const [missing, setMissing] = useState<string[]>([]);
  const [error, setError] = useState('');
  const [hash, setHash] = useState(location.hash);
  const [query, setQuery] = useState('');
  const [kind, setKind] = useState('');
  const [sort, setSort] = useState('name');
  const [page, setPage] = useState(0);
  const [loaded, setLoaded] = useState<{ id: string; field?: Awaited<ReturnType<typeof loadField>>; error?: string }>();
  const [route, search] = hash.split('?');
  const requested = route.match(/^#\/?field\/([a-z0-9_-]+)$/)?.[1];
  const ready = (index ?? []).filter(item => item.status !== 'pending' && !missing.includes(item.field_id));
  const selected = ready.find(item => item.field_id === requested)
    ?? (route === '#dial' ? ready.find(item => item.kind === 'dial') : undefined) ?? ready[0];
  const id = selected?.field_id;
  const limits = route === '#limits' || route === '#/limits';
  const filtered = ready.filter(item => (!kind || item.kind === kind) && item.title.toLowerCase().includes(query.trim().toLowerCase()))
    .sort((a, b) => (sort === 'date' ? (b.date_range?.end_utc ?? '').localeCompare(a.date_range?.end_utc ?? '') : 0) ||
      a.title.localeCompare(b.title));
  const coming = (index?.length ?? 0) - ready.length;
  const visible = filtered.slice(page * 50, (page + 1) * 50);

  useEffect(() => {
    const update = () => setHash(location.hash);
    addEventListener('hashchange', update);
    return () => removeEventListener('hashchange', update);
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    loadIndex(controller.signal).then(items => {
      if (controller.signal.aborted) return;
      setIndex(items);
      const queue = items.filter(item => item.status !== 'pending');
      let next = 0;
      async function check() {
        while (!controller.signal.aborted && next < queue.length) {
          const item = queue[next++];
          if (await fieldExists(item.field_id, controller.signal) === false && !controller.signal.aborted) {
            setMissing(value => [...value, item.field_id]);
          }
        }
      }
      void Promise.all(Array.from({ length: Math.min(6, queue.length) }, check));
    }).catch(error => { if (!controller.signal.aborted) setError(error.message); });
    return () => controller.abort();
  }, []);

  useEffect(() => {
    if (!id) return;
    const controller = new AbortController();
    loadField(id, controller.signal).then(field => {
      if (!controller.signal.aborted) setLoaded({ id, field });
    }).catch(error => { if (!controller.signal.aborted) setLoaded({ id, error: error.message }); });
    return () => controller.abort();
  }, [id]);

  const current = loaded?.id === id ? loaded : undefined;
  const field = current?.field;
  const changeField = (value: string) => { if (value) location.hash = '/field/' + value; };

  return <>
    <a className="skip-link" href="#workspace" onClick={event => { event.preventDefault(); document.getElementById('workspace')?.focus(); }}>Skip to content</a>
    <header className="topbar">
      <a href="#/" className="brand">{copy.title}<span> · {copy.subtitle}</span></a>
      <input type="search" aria-label={copy.search} placeholder={copy.search} title={copy.search} value={query} onChange={event => {
        setQuery(event.target.value); setPage(0);
      }} />
      <a href="#/limits" className="help" title={copy.planet} aria-label={copy.planet}>?</a>
    </header>
    <div className="workspace" id="workspace" tabIndex={-1}>
      <aside className="catalog" aria-label={copy.fields}>
        <h2>{copy.fields}</h2>
        <div className="filters">
          <select aria-label="Filter fields" title="Filter fields" value={kind} onChange={event => { setKind(event.target.value); setPage(0); }}>
            <option value="">{copy.all}</option><option value="static">{copy.static}</option><option value="dial">{copy.dial}</option>
          </select>
          <select aria-label="Sort fields" title="Sort fields" value={sort} onChange={event => { setSort(event.target.value); setPage(0); }}>
            <option value="name">{copy.sortName}</option><option value="date">{copy.sortDate}</option>
          </select>
        </div>
        <div className="field-list">{visible.map(item => <a key={item.field_id} className="field-row"
          href={'#/field/' + item.field_id} aria-current={id === item.field_id && !limits ? 'page' : undefined}>
          <img loading="lazy" src={imageUrl(item.field_id, item.thumbnail)} alt="" width="46" height="46"
            onError={event => { event.currentTarget.style.visibility = 'hidden'; }} />
          <span><strong>{item.title}</strong><small>{item.kind === 'dial' ? copy.dial : copy.static}
            {item.n_frames !== undefined && ' · ' + item.n_frames}</small>
            {item.date_range && <small>{day(item.date_range.start_utc)} – {day(item.date_range.end_utc)}</small>}</span>
        </a>)}</div>
        <select className="mobile-fields" aria-label={copy.fields} title={copy.fields} value={visible.some(item => item.field_id === id) ? id : ''}
          onChange={event => changeField(event.target.value)}>
          <option value="" disabled>{copy.fields}</option>
          {visible.map(item => <option key={item.field_id} value={item.field_id}>{item.title}</option>)}
        </select>
        {index && !visible.length && <p>{copy.empty}</p>}
        {filtered.length > 50 && <div className="pagination">
          <button title={copy.previous} disabled={!page} onClick={() => setPage(page - 1)}>{copy.previous}</button>
          <span>{page + 1} / {Math.ceil(filtered.length / 50)}</span>
          <button title={copy.next} disabled={(page + 1) * 50 >= filtered.length} onClick={() => setPage(page + 1)}>{copy.next}</button>
        </div>}
        {!!coming && <p className="muted">+{coming} {copy.soon}</p>}
      </aside>
      <main className="content">
        {limits ? <><h1>{copy.planet}</h1><Detectability /></> : <>
          <h1>{selected?.title ?? copy.fields}</h1>
          {(error || current?.error) && <p role="alert">{error || current?.error}</p>}
          {!error && (!index || (id && !current)) && <p role="status">{copy.loading}</p>}
          {field && <ErrorBoundary key={field.field_id}><SimpleViewer field={field} search={search ?? (route === "#dial" ? "mode=distance" : undefined)} /></ErrorBoundary>}
        </>}
      </main>
    </div>
  </>;
}
