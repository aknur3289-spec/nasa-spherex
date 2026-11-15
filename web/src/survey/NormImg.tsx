import { useEffect, useState, type CSSProperties } from "react";
import { normalisedUrl } from "./displayNorm";

/** <img> that shows the display-normalised version of a grey sky PNG (falls back to the original). */
export function NormImg({ src, alt, className, style }: { src: string; alt: string; className?: string; style?: CSSProperties }) {
  const [out, setOut] = useState<string>();
  useEffect(() => {
    let alive = true;
    setOut(undefined);
    normalisedUrl(src).then((u) => alive && setOut(u)).catch(() => alive && setOut(src));
    return () => { alive = false; };
  }, [src]);
  return <img src={out ?? src} alt={alt} className={className} style={{ ...style, visibility: out ? undefined : "hidden" }} />;
}
