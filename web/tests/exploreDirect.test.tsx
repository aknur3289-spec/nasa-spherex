// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, test, vi } from 'vitest';
import App from '../src/survey/App';
import index from '../public/data/index.json';

vi.mock('aladin-lite', () => ({ default: { init: Promise.reject(new Error('Map unavailable')) } }));

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  history.replaceState(null, '', '/');
});

test('direct #/explore entry shows working map search when tiles fail', async () => {
  history.replaceState(null, '', '/#/explore');
  vi.stubGlobal('fetch', vi.fn(async (url: string) =>
    url.endsWith('index.json')
      ? Response.json([index.find((entry) => entry.field_id === 'm101')])
      : new Response(null, { status: 404 }),
  ));
  render(<App />);
  const input = await screen.findByPlaceholderText('Star, galaxy or RA Dec — e.g. Sirius, M42, 210.80 54.35');
  expect(input.closest('.ss-map')).toBeTruthy();
  expect(await screen.findByText('The whole-sky map is served by CDS and is not reachable from this network right now. Search still works.')).toBeTruthy();
  fireEvent.change(input, { target: { value: 'Vega' } });
  fireEvent.submit(input.closest('form')!);
  expect(await screen.findByText('OUTSIDE OUR TIME-LAPSE FIELDS')).toBeTruthy();
  expect(screen.getByRole('link', { name: /IRSA/ })).toBeTruthy();
});
