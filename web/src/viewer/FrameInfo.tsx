import type { Frame } from '../contract';

export function FrameInfo({ frame, slot }: { frame: Frame; slot: 'A' | 'B' }) {
  return <figcaption className="frame-info">
    <span>{slot} · {frame.obs_time_utc.slice(0, 10)} · {frame.wavelength_um.toFixed(2)} µm · Detector {frame.detector}{frame.band && ' / ' + frame.band}</span>
    <a href={frame.source_url} target="_blank" rel="noopener">Open source file at IRSA</a>
  </figcaption>;
}
