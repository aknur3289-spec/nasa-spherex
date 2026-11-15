import { useEffect, useRef } from 'react';

export function Starfield() {
  const ref = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const canvas = ref.current!;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    const motion = matchMedia('(prefers-reduced-motion: reduce)');
    const stars = Array.from({ length: 490 }, (_, i) => ({
      x: Math.random(), y: Math.random(), depth: 1 + i % 3, phase: Math.random() * 6.28,
    }));
    let width = 0, height = 0, x = 0, y = 0, frame = 0, last = -Infinity;
    const draw = (time: number) => {
      if (time - last >= 32 || motion.matches) {
        last = time;
        ctx.clearRect(0, 0, width, height);
        ctx.fillStyle = '#dce9ff';
        for (const star of stars) {
          const shift = motion.matches ? 0 : star.depth * (x * 10 + time / 4200);
          const vertical = motion.matches ? 0 : star.depth * (y * 8 - scrollY * .035);
          const px = ((star.x * width + shift) % width + width) % width;
          const py = ((star.y * height + vertical) % height + height) % height;
          ctx.globalAlpha = .12 + .09 * star.depth + (motion.matches ? 0 : .08 * Math.sin(time / 900 + star.phase));
          ctx.fillRect(px, py, star.depth === 3 ? 1.6 : 1, star.depth === 3 ? 1.6 : 1);
        }
        ctx.globalAlpha = 1;
      }
      if (!motion.matches && !document.hidden) frame = requestAnimationFrame(draw);
    };
    const restart = () => {
      cancelAnimationFrame(frame);
      last = -Infinity;
      if (!document.hidden) draw(performance.now());
    };
    const resize = () => {
      width = innerWidth;
      height = innerHeight;
      const dpr = Math.min(devicePixelRatio, 2);
      canvas.width = width * dpr;
      canvas.height = height * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      restart();
    };
    const pointer = (event: PointerEvent) => {
      x = event.clientX / width - .5;
      y = event.clientY / height - .5;
    };
    resize();
    addEventListener('resize', resize);
    addEventListener('pointermove', pointer, { passive: true });
    document.addEventListener('visibilitychange', restart);
    motion.addEventListener('change', restart);
    return () => {
      cancelAnimationFrame(frame);
      removeEventListener('resize', resize);
      removeEventListener('pointermove', pointer);
      document.removeEventListener('visibilitychange', restart);
      motion.removeEventListener('change', restart);
    };
  }, []);
  return <canvas className="living-stars" ref={ref} aria-hidden="true" />;
}
