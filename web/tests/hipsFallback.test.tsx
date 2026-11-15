// @vitest-environment jsdom
import { act, cleanup, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, test, vi } from 'vitest';
import { SkySearch } from '../src/survey/SkySearch';

const mock = vi.hoisted(() => ({ layers: [] as { url: string; fail: () => void }[], installed: [] as string[] }));
vi.mock('aladin-lite', () => ({
  default: {
    init: Promise.resolve(),
    createImageSurvey: (_id: string, _label: string, url: string, _frame: string,
      _order: unknown, options: { errorCallback: () => void }) => {
      mock.layers.push({ url, fail: options.errorCallback });
      return { url };
    },
    aladin: () => ({
      on: () => undefined,
      setBaseImageLayer: (layer: { url: string }) => mock.installed.push(layer.url),
    }),
  },
}));

afterEach(() => { cleanup(); mock.layers.length = 0; mock.installed.length = 0; });

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
