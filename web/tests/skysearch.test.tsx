// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, test, vi } from 'vitest';
import { SkySearch } from '../src/survey/SkySearch';
import type { Field } from '../src/contract';
import m101 from '../public/data/m101/field.json';

vi.mock('aladin-lite', () => ({ default: { init: Promise.reject(new Error('CDS unavailable')) } }));

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

test('name and coordinate results remain usable when the map cannot load', async () => {
  const go = vi.fn();
  vi.stubGlobal('fetch', vi.fn(() => { throw new Error('known names must stay offline'); }));
  render(<SkySearch fields={[m101 as Field]} go={go} />);
  expect(await screen.findByText('The whole-sky map is served by CDS and is not reachable from this network right now. Search still works.')).toBeTruthy();

  fireEvent.change(screen.getByLabelText('Object name or coordinates'), { target: { value: 'M 101' } });
  fireEvent.click(screen.getByRole('button', { name: 'Find' }));
  expect(await screen.findByText('INSIDE OUR DATA')).toBeTruthy();
  fireEvent.click(screen.getByRole('button', { name: 'Watch timelapse' }));
  expect(go).toHaveBeenCalledWith('timelapse', 'm101');

  fireEvent.change(screen.getByLabelText('Object name or coordinates'), { target: { value: 'Vega' } });
  fireEvent.click(screen.getByRole('button', { name: 'Find' }));
  expect(await screen.findByText('OUTSIDE OUR TIME-LAPSE FIELDS')).toBeTruthy();
  expect(screen.getByText('Nearest of our fields')).toBeTruthy();
  expect(screen.getByRole('link', { name: /IRSA/ })).toBeTruthy();
});
