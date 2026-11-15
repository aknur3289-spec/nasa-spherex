/**
 * Display-only normalisation of a grey sky PNG: the background (median of valid pixels) maps to near-black
 * and the brightest stars (99.7th percentile) to white, with an asinh curve. This keeps every frame of a
 * timelapse equally dark even when SPHEREx's sky background differs between wavelengths. Analysis data and
 * honesty labels are not affected. Transparent (masked / off-detector) pixels stay transparent.
 */
const cache = new Map<string, Promise<ImageData>>();

function load(src: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = reject;
    img.src = src;
  });
}

export function normalisedPixels(src: string): Promise<ImageData> {
  let hit = cache.get(src);
  if (!hit) {
    hit = load(src).then((img) => {
      const canvas = document.createElement("canvas");
      canvas.width = img.naturalWidth;
      canvas.height = img.naturalHeight;
      const ctx = canvas.getContext("2d", { willReadFrequently: true })!;
      ctx.drawImage(img, 0, 0);
      const px = ctx.getImageData(0, 0, canvas.width, canvas.height);
      const d = px.data;
      const vals: number[] = [];
      for (let i = 0; i < d.length; i += 4) if (d[i + 3] > 0) vals.push(d[i]);
      if (vals.length < 20) return px;
      vals.sort((a, b) => a - b);
      const q = (p: number) => vals[Math.min(vals.length - 1, Math.floor(p * vals.length))];
      const bg = q(0.5), top = Math.max(q(0.997), bg + 8);
      const k = 6, norm = Math.asinh(k);
      for (let i = 0; i < d.length; i += 4) {
        const t = Math.min(1, Math.max(0, (d[i] - bg) / (top - bg)));
        const g = Math.round(12 + 243 * (Math.asinh(k * t) / norm));
        d[i] = d[i + 1] = d[i + 2] = g;
      }
      return px;
    });
    cache.set(src, hit);
  }
  return hit;
}

export async function normalisedUrl(src: string): Promise<string> {
  const px = await normalisedPixels(src);
  const canvas = document.createElement("canvas");
  canvas.width = px.width;
  canvas.height = px.height;
  canvas.getContext("2d")!.putImageData(px, 0, 0);
  return canvas.toDataURL("image/png");
}
