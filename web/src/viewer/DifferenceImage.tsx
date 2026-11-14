import { useEffect, useState } from 'react';
import type { Frame } from '../contract';
import { imageUrl } from '../data/loader';
import { SkyImage } from '../ui/SkyImage';

export function DifferenceImage({ fieldId, a, b, path }: { fieldId: string; a: Frame; b: Frame; path?: string }) {
  const [failed, setFailed] = useState(false);
  const [result, setResult] = useState('');
  useEffect(() => {
    if (path && !failed) return;
    let active = true;
    const load = (frame: Frame) => new Promise<HTMLImageElement>((resolve, reject) => {
      const img = new Image();
      img.onload = () => resolve(img);
      img.onerror = reject;
      img.src = imageUrl(fieldId, frame.png);
    });
    Promise.all([load(a), load(b)]).then(([first, second]) => {
      if (!active) return;
      if (first.naturalWidth !== second.naturalWidth || first.naturalHeight !== second.naturalHeight) throw new Error('Image sizes differ');
      const canvas = document.createElement('canvas');
      canvas.width = first.naturalWidth;
      canvas.height = first.naturalHeight;
      const ctx = canvas.getContext('2d', { willReadFrequently: true })!;
      ctx.imageSmoothingEnabled = false;
      ctx.drawImage(first, 0, 0);
      const pixels = ctx.getImageData(0, 0, canvas.width, canvas.height);
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      ctx.drawImage(second, 0, 0);
      const other = ctx.getImageData(0, 0, canvas.width, canvas.height);
      for (let i = 0; i < pixels.data.length; i += 4) {
        const delta = .2126 * (pixels.data[i] - other.data[i]) + .7152 * (pixels.data[i+1] - other.data[i+1]) + .0722 * (pixels.data[i+2] - other.data[i+2]);
        pixels.data.fill(Math.round(Math.abs(delta)), i, i+3);
        pixels.data[i+3] = 255;
      }
      ctx.putImageData(pixels, 0, 0);
      setResult(canvas.toDataURL());
    }).catch(() => { if (active) setResult('unavailable'); });
    return () => { active = false; };
  }, [a, b, failed, fieldId, path]);

  const src = path && !failed ? imageUrl(fieldId, path) : result;
  if (!src || src === 'unavailable') return <div className="image-placeholder" role="status">
    {src ? 'Difference image unavailable.' : 'Preparing difference image…'}
  </div>;
  return <SkyImage src={src} alt="Absolute pixel difference" onError={() => setFailed(true)} />;
}

