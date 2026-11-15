// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, test, vi } from 'vitest';
import { SkySearch } from '../src/survey/SkySearch';

const mock = vi.hoisted(() => ({
  layers: [] as { url: string; fail: () => void }[],
  installed: [] as string[],
  options: undefined as { showSimbadPointerControl: boolean } | undefined,
  sources: [] as { ra: number; dec: number }[],
  positions: [] as { ra: number; dec: number }[],
}));
vi.mock('aladin-lite', () => ({
  default: {
    init: Promise.resolve(),
    catalog: () => ({
      removeAll: () => { mock.sources.length = 0; },
      addSources: (sources: { ra: number; dec: number }[]) => mock.sources.push(...sources),
    }),
    source: (ra: number, dec: number) => ({ ra, dec }),
    createImageSurvey: (_id: string, _label: string, url: string, _frame: string,
      _order: unknown, options: { errorCallback: () => void }) => {
      mock.layers.push({ url, fail: options.errorCallback });
      return { url };
    },
    aladin: (_host: unknown, options: { showSimbadPointerControl: boolean }) => {
      mock.options = options;
      return {
      on: () => undefined,
      addCatalog: () => undefined,
      gotoRaDec: (ra: number, dec: number) => mock.positions.push({ ra, dec }),
      setBaseImageLayer: (layer: { url: string }) => mock.installed.push(layer.url),
      };
    },
  },
}));

afterEach(() => { cleanup(); mock.layers.length = 0; mock.installed.length = 0; mock.sources.length = 0; mock.positions.length = 0; mock.options = undefined; });

test('failed tiles advance through both direct hosts before the proxy', async () => {
  render(<SkySearch fields={[]} go={() => undefined} />);
  await waitFor(() => expect(mock.layers).toHaveLength(1));
  expect(mock.layers[0].url).toBe('https://alasky.cds.unistra.fr/SPHEREx/color');
  act(() => mock.layers[0].fail());
  expect(mock.installed[0]).toBe('https://alaskybis.cds.unistra.fr/SPHEREx/color');
  act(() => mock.layers[1].fail());
  expect(mock.installed[1]).toBe(`${location.origin}/hips/SPHEREx/color`);
  act(() => mock.layers[2].fail());
  expect(await screen.findByText('The whole-sky map is served by CDS and is not reachable from this network right now. Search still works.')).toBeTruthy();
});

test('map search places one marker and enables the SIMBAD pointer', async () => {
  render(<SkySearch fields={[]} go={() => undefined} />);
  await waitFor(() => expect(mock.options?.showSimbadPointerControl).toBe(true));
  const input = screen.getByPlaceholderText('Star, galaxy or RA Dec — e.g. Sirius, M42, 210.80 54.35');
  expect(input.closest('.ss-map')).toBeTruthy();
  fireEvent.change(input, { target: { value: '210.80 54.35' } });
  fireEvent.submit(input.closest('form')!);
  expect(mock.positions.at(-1)).toEqual({ ra: 210.8, dec: 54.35 });
  expect(mock.sources).toEqual([{ ra: 210.8, dec: 54.35 }]);

  fireEvent.change(input, { target: { value: 'Vega' } });
  fireEvent.click(screen.getByRole('button', { name: 'Find' }));
  await waitFor(() => expect(mock.sources[0]?.ra).toBeCloseTo(279.235));
  expect(mock.sources).toHaveLength(1);
});
