// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, beforeEach, expect, test, vi } from 'vitest';
import App from '../src/App';
import { SimpleViewer } from '../src/viewer/SimpleViewer';
import { integerScale, pixelCentre } from '../src/ui/pixels';
import type { Field } from '../src/contract';
import staticFixture from '../public/data/fixture-static/field.json';
import dialFixture from '../public/data/fixture-dial/field.json';
import index from '../public/data/index.json';

let reduced: boolean;
const field = staticFixture as Field;
beforeEach(() => {
  reduced = true;
  vi.stubGlobal('matchMedia', () => ({ matches: reduced, addEventListener() {}, removeEventListener() {} }));
});
afterEach(() => {
  cleanup(); vi.unstubAllGlobals(); vi.useRealTimers(); sessionStorage.clear(); history.replaceState(null, '', '/');
});
test('catalog renders new index entries and hides pending and missing fields', async () => {
  const extra = { ...index[0], field_id: 'new-field', title: 'New field' };
  vi.stubGlobal('fetch', vi.fn(async (url: string) => {
    if (url.endsWith('index.json')) return Response.json([
      ...index, extra, { ...extra, field_id: 'pending', title: 'Pending field', status: 'pending' },
      { ...extra, field_id: 'missing', title: 'Missing field' },
    ]);
    if (url.includes('/missing/')) return new Response(null, { status: 404 });
    if (url.includes('/new-field/')) return Response.json({ ...field, field_id: 'new-field' });
    return Response.json(field);
  }));
  render(<App />);
  expect(await screen.findByText('+2 coming soon')).toBeTruthy();
  const catalog = screen.getByRole('complementary', { name: 'Sky fields' });
  expect(within(catalog).getAllByRole('link')).toHaveLength(index.length + 1);
  expect(within(catalog).queryByText('Pending field')).toBeNull();
  expect(within(catalog).queryByText('Missing field')).toBeNull();
  fireEvent.click(within(catalog).getByRole('link', { name: /New field/ }));
  expect(await screen.findByRole('heading', { name: 'New field' })).toBeTruthy();
});
test('play follows UTC order and stops on the last frame', () => {
  reduced = false;
  vi.useFakeTimers();
  render(<SimpleViewer field={{ ...field, frames: [...field.frames].reverse() }} />);
  expect(screen.getByRole('img').getAttribute('alt')).toBe('1 Jan 2030');
  act(() => vi.advanceTimersByTime(850));
  expect(screen.getByRole('img').getAttribute('alt')).toBe('3 Jul 2030');
  act(() => vi.advanceTimersByTime(850));
  expect(screen.getByRole('img').getAttribute('alt')).toBe('1 Aug 2030');
  act(() => vi.advanceTimersByTime(850));
  expect(screen.getByRole('button', { name: 'Start playback' })).toBeTruthy();
});
test('compare defaults to high trust and labels options by date', () => {
  render(<SimpleViewer field={field} search="mode=compare" />);
  const after = screen.getByLabelText('After') as HTMLSelectElement;
  expect(after.selectedOptions[0].textContent).toBe('3 Jul 2030');
  expect(screen.queryByRole('button', { name: 'Distance', exact: true })).toBeNull();
});
test('distance mode is available for dial fields', () => {
  render(<SimpleViewer field={dialFixture as Field} search="mode=distance&d=30" />);
  expect(screen.getByRole('button', { name: 'Distance', exact: true })).toBeTruthy();
  expect(screen.getByText('Signal at the crosshair')).toBeTruthy();
});
test('reduced motion disables autoplay and a broken image has a placeholder', () => {
  vi.useFakeTimers();
  render(<SimpleViewer field={field} />);
  act(() => vi.advanceTimersByTime(2000));
  expect(screen.getByRole('img').getAttribute('alt')).toBe('1 Jan 2030');
  fireEvent.error(screen.getByRole('img'));
  expect(screen.getByRole('status').textContent).toContain('Image unavailable');
});
test('integer scale uses complete source pixels and maps their centres', () => {
  expect(integerScale(390, 99)).toBe(3);
  expect(integerScale(594, 99)).toBe(6);
  expect(pixelCentre(7, 6)).toBe(45);
});
