import { useLayoutEffect, useRef, useState } from 'react';
import { integerScale } from './pixels';

export function SkyImage({ src, alt, onError }: { src: string; alt: string; onError: () => void }) {
  const host = useRef<HTMLDivElement>(null);
  const [available, setAvailable] = useState(0);
  const [native, setNative] = useState<{ width: number; height: number }>();
  useLayoutEffect(() => {
    if (!host.current || typeof ResizeObserver === 'undefined') return;
    const observer = new ResizeObserver(([entry]) => setAvailable(entry.contentRect.width));
    observer.observe(host.current);
    return () => observer.disconnect();
  }, []);
  const scale = native && available ? integerScale(available, native.width) : 1;
  return <div className="pixel-stage" ref={host}>
    <img src={src} alt={alt} onError={onError} onLoad={event => {
      const { naturalWidth: width, naturalHeight: height } = event.currentTarget;
      setNative({ width, height });
    }} style={native && available >= native.width ? { width: native.width * scale, height: native.height * scale } : undefined} />
  </div>;
}
