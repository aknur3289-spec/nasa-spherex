import { useEffect, useRef } from "react";
import { normalisedPixels } from "./displayNorm";
import { NormImg } from "./NormImg";
import type { CSSProperties } from "react";

export type ColourMap = "grey" | "inferno";

const stops = [
  [0, 0, 4], [31, 12, 44], [85, 15, 109], [136, 34, 106],
  [186, 54, 85], [227, 89, 51], [249, 140, 10], [252, 195, 48], [252, 255, 164],
];

function inferno(value: number): [number, number, number] {
  const position = value / 255 * (stops.length - 1);
  const i = Math.min(stops.length - 2, Math.floor(position));
  const t = position - i;
  return [0, 1, 2].map(channel => Math.round(stops[i][channel] * (1 - t) + stops[i + 1][channel] * t)) as [number, number, number];
}

export function MappedImage({ src, alt, map, className, style }: {
  src: string; alt: string; map: ColourMap; className?: string; style?: CSSProperties;
}) {
  const canvas = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    if (map !== "inferno") return;
    let alive = true;
    normalisedPixels(src).then((source) => {
      if (!alive || !canvas.current) return;
      const output = canvas.current;
      output.width = source.width;
      output.height = source.height;
      const context = output.getContext("2d");
      if (!context) return;
      const pixels = new ImageData(new Uint8ClampedArray(source.data), source.width, source.height);
      for (let i = 0; i < pixels.data.length; i += 4) {
        const [r, g, b] = inferno(pixels.data[i]);
        pixels.data[i] = r;
        pixels.data[i + 1] = g;
        pixels.data[i + 2] = b;
      }
      context.putImageData(pixels, 0, 0);
    }).catch(() => undefined);
    return () => { alive = false; };
  }, [src, map]);
  return map === "grey"
    ? <NormImg src={src} alt={alt} className={className} style={style} />
    : <canvas ref={canvas} role="img" aria-label={alt} className={className} style={style} />;
}
