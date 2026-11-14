// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, act } from '@testing-library/react';
import { afterEach, beforeEach, expect, test, vi } from 'vitest';
import App from '../src/App';
import { BlinkViewer } from '../src/viewer/BlinkViewer';
import type { Field } from '../src/contract';
import index from '../public/data/index.json';
import staticFixture from '../public/data/fixture-static/field.json';
import dialFixture from '../public/data/fixture-dial/field.json';

const field = staticFixture as Field;

beforeEach(() => {
  vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue(null);
  vi.stubGlobal('matchMedia', vi.fn().mockReturnValue({
    matches: true,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
  }));
});

afterEach(() => {
  cleanup();
  window.history.replaceState(null, "", "/");
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  vi.useRealTimers();
});

test('loads both fixtures and initially renders the first high-trust pair', async () => {
  vi.stubGlobal('fetch', vi.fn(async (url: string) => Response.json(
    url.endsWith('/index.json') ? [...index, { ...index[0], field_id: 'pending-field', title: 'Pending field', status: 'pending' }] : url.includes('fixture-dial') ? dialFixture : field,
  )));
  render(<App />);
  expect(await screen.findByText('High trust · wavelengths differ 0.8% · 183 days apart')).toBeTruthy();
  expect(screen.getByRole("img").getAttribute("alt")).toBe("Sky field, frame epoch-1");
  expect(screen.queryByText('Pending field')).toBeNull();
  fireEvent.click(screen.getByRole('link', { name: /Parallax dial fixture/ }));
  expect(await screen.findByText("Signal at the crosshair")).toBeTruthy();
});

test('Space toggles frames and the arrow keys change pair', () => {
  render(<BlinkViewer field={field} />);
  fireEvent.keyDown(window, { key: '3' });
  expect(screen.getByRole('img').getAttribute('alt')).toBe('Sky field, frame epoch-1');
  fireEvent.keyDown(window, { code: 'Space' });
  expect(screen.getByRole('img').getAttribute('alt')).toBe('Sky field, frame epoch-2');
  fireEvent.keyDown(window, { key: 'ArrowLeft' });
  expect(screen.getByText(/Medium trust/)).toBeTruthy();
  fireEvent.keyDown(window, { key: ' ' });
  expect(screen.getByRole('img').getAttribute('alt')).toBe('Sky field, frame epoch-3');
});

test('reduced motion disables automatic blinking', () => {
  vi.useFakeTimers();
  render(<BlinkViewer field={field} />);
  fireEvent.keyDown(window, { key: '2' });
  act(() => vi.advanceTimersByTime(850));
  expect(screen.getByRole('img').getAttribute('alt')).toBe('Sky field, frame epoch-1');
  fireEvent.click(screen.getByRole('button', { name: 'Toggle frame' }));
  expect(screen.getByRole('img').getAttribute('alt')).toBe('Sky field, frame epoch-2');
});

test('rejects a same-frame pair and displays one frame when no distinct B exists', () => {
  render(<BlinkViewer field={{ ...field, frames: [field.frames[0]], pairs: [
    { ...field.pairs[0], b: field.pairs[0].a },
  ] }} />);
  expect(screen.getAllByRole('img')).toHaveLength(1);
  expect(screen.queryByLabelText('Observation pair')).toBeNull();
});

test('labels synthetic data', () => {
  render(<BlinkViewer field={field} />);
  expect(screen.getByText('Synthetic data')).toBeTruthy();
});

test('a broken PNG shows a placeholder and leaves the other frame available', () => {
  render(<BlinkViewer field={field} />);
  fireEvent.error(screen.getByRole('img', { name: 'Sky field, frame epoch-1' }));
  expect(screen.getByRole('status').textContent).toContain('Image unavailable for frame epoch-1');
  expect(screen.getByRole('img', { name: 'Sky field, frame epoch-2' })).toBeTruthy();
});

test('integer scaling and pixel-centre mapping preserve the source grid', async () => {
  const { integerScale, pixelCentre } = await import('../src/ui/pixels');
  expect(integerScale(590, 99)).toBe(5);
  expect(integerScale(594, 99)).toBe(6);
  expect(pixelCentre(7, 6)).toBe(45);
});
