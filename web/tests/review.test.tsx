// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, expect, test, vi } from 'vitest';
import { Review } from '../src/survey/Review';
import { assetUrl, exportPayload, nextUnlabelled, order, summary, validateQueue } from '../src/survey/reviewData';
import queueJson from '../public/data/review/demo-synthetic/queue.json';
import indexJson from '../public/data/review/index.json';

const queue = validateQueue(queueJson);

beforeEach(() => {
  vi.stubGlobal('matchMedia', () => ({ matches: true, addEventListener() {}, removeEventListener() {} }));
  vi.stubGlobal('fetch', vi.fn(async (url: string) => {
    if (url.endsWith('review/index.json')) return Response.json(indexJson);
    if (url.endsWith('queue.json')) return Response.json(queueJson);
    return new Response(null, { status: 404 });
  }));
  localStorage.clear();
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

test('published demo queue is valid, synthetic and has practice items of both kinds', () => {
  expect(queue.synthetic).toBe(true);
  const { practice, work } = order(queue);
  expect(practice).toHaveLength(5);
  expect(new Set(practice.map(c => c.gold!.answer))).toEqual(new Set(['real', 'bogus']));
  expect(practice.length + work.length).toBe(queue.candidates.length);
});

test('asset paths are confined to the review folder', () => {
  expect(assetUrl('demo-synthetic', 'stamps/c0000_sci.png')).toBe('data/review/demo-synthetic/stamps/c0000_sci.png');
  expect(() => assetUrl('demo', '../../secret.png')).toThrow();
  expect(() => assetUrl('../x', 'queue.json')).toThrow();
});

test('summary, next item and export payload', () => {
  const items = queue.candidates.slice(0, 4);
  const labels = { [items[0].id]: { answer: 'real' as const, at: 't', ml_score: items[0].ml_score, ms: 900 },
                   [items[1].id]: { answer: 'unsure' as const, at: 't', ml_score: items[1].ml_score, ms: 400 } };
  expect(nextUnlabelled(items, labels)).toBe(2);
  const s = summary(items, labels);
  expect(s.done).toBe(2);
  expect(s.real).toBe(1);
  const p = exportPayload(queue, labels, '  Aknur ');
  expect(p.volunteer).toBe('Aknur');
  expect(p.labels.map(l => l.id)).toEqual([items[0].id, items[1].id]);
  expect(p.labels[0].ml_score).toBe(items[0].ml_score);
});

test('volunteer flow: practice with feedback, then answers by keyboard are saved and undoable', async () => {
  render(<Review />);
  expect(await screen.findByText(/PRACTICE DATA \(synthetic\)/)).toBeTruthy();
  fireEvent.click(screen.getByRole('button', { name: /Start practice/ }));
  // the model hint is hidden before answering
  expect(screen.getByText(/appears after you answer/)).toBeTruthy();
  fireEvent.click(screen.getByRole('button', { name: /Real mover/ }));
  expect(await screen.findByText(/This one is/)).toBeTruthy();
  expect(screen.getByText(/Model says/)).toBeTruthy();
  fireEvent.click(screen.getByRole('button', { name: /Skip practice|Next example|Start the real queue/ }));

  // skip the rest of practice by answering with keys
  for (let i = 0; i < 4; i++) {
    act(() => { window.dispatchEvent(new KeyboardEvent('keydown', { key: '2' })); });
    act(() => { window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter' })); });
  }
  expect(await screen.findByText(/CANDIDATE 1 OF/)).toBeTruthy();
  act(() => { window.dispatchEvent(new KeyboardEvent('keydown', { key: '1' })); });
  expect(screen.getByText(/CANDIDATE 2 OF/)).toBeTruthy();
  const stored = JSON.parse(localStorage.getItem('parallax-review:demo-synthetic')!);
  expect(Object.keys(stored)).toHaveLength(6);
  act(() => { window.dispatchEvent(new KeyboardEvent('keydown', { key: 'z' })); });
  expect(Object.keys(JSON.parse(localStorage.getItem('parallax-review:demo-synthetic')!))).toHaveLength(5);
  expect(screen.getByRole('button', { name: /Download answers \(5\)/ })).toBeTruthy();
});
