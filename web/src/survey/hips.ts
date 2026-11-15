/** Preferred public HiPS hosts, with our CDS rewrite as the last fallback. */
export function hipsUrls(id: string, origin: string): string[] {
  return [
    `https://alasky.cds.unistra.fr/SPHEREx/${id}`,
    `https://alaskybis.cds.unistra.fr/SPHEREx/${id}`,
    `${origin}/hips/SPHEREx/${id}`,
  ];
}
