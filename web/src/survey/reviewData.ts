// Data and storage helpers for the volunteer Review page (schema "review-1.0", written by ml/export_review.py).

export type Answer = "real" | "bogus" | "unsure";

export type Candidate = {
  id: string;
  ra_deg: number;
  dec_deg: number;
  mjd?: number;
  ml_score: number;
  group: string;
  stamps: { sci: string; ref: string; diff: string };
  features: Record<string, number | null>;
  gold?: { answer: "real" | "bogus"; kind: string };
};

export type ReviewQueue = {
  schema_version: "review-1.0";
  set_id: string;
  title: string;
  description: string;
  synthetic: boolean;
  created_utc: string;
  stamp_px: number;
  model: { name: string; trained_on?: string; cv_roc_auc?: number | null };
  candidates: Candidate[];
};

export type ReviewSet = { set_id: string; title: string; synthetic: boolean; n: number; queue: string };

export type Label = { answer: Answer; at: string; ml_score: number; ms: number };
export type Labels = Record<string, Label>;

export const REVIEW_ROOT = "data/review/";
const SAFE = /^[a-z0-9][a-z0-9_.-]*$/i;
const SAFE_PATH = /^[a-z0-9_./-]+\.(png|json)$/i;

export function assetUrl(setId: string, path: string) {
  if (!SAFE.test(setId) || !SAFE_PATH.test(path) || path.includes("..")) throw new Error("Invalid review asset path.");
  return `${REVIEW_ROOT}${setId}/${path}`;
}

export function validateQueue(q: unknown): ReviewQueue {
  const v = q as ReviewQueue;
  if (!v || v.schema_version !== "review-1.0" || !Array.isArray(v.candidates)) throw new Error("Unsupported review queue.");
  for (const c of v.candidates) {
    if (typeof c.id !== "string" || !(c.ml_score >= 0 && c.ml_score <= 1) || !c.stamps?.sci || !c.stamps?.ref || !c.stamps?.diff)
      throw new Error(`Bad candidate in review queue: ${String(c?.id)}`);
  }
  return v;
}

export async function loadSets(signal?: AbortSignal): Promise<ReviewSet[]> {
  const r = await fetch(REVIEW_ROOT + "index.json", { signal });
  if (!r.ok) throw new Error("No review sets are published yet.");
  const body = await r.json();
  return Array.isArray(body?.sets) ? body.sets : [];
}

export async function loadQueue(set: ReviewSet, signal?: AbortSignal): Promise<ReviewQueue> {
  const r = await fetch(assetUrl(set.set_id, "queue.json"), { signal });
  if (!r.ok) throw new Error(`Could not load review set ${set.set_id}.`);
  return validateQueue(await r.json());
}

// ---- local storage (labels never leave the browser unless the volunteer exports them)
const key = (setId: string) => `parallax-review:${setId}`;

export function readLabels(setId: string): Labels {
  try {
    const raw = localStorage.getItem(key(setId));
    return raw ? (JSON.parse(raw) as Labels) : {};
  } catch {
    return {};
  }
}

export function writeLabels(setId: string, labels: Labels) {
  try {
    localStorage.setItem(key(setId), JSON.stringify(labels));
  } catch {
    /* private mode or storage full: labels stay in memory for this visit */
  }
}

/** Practice items first (known answers), then the ML-ranked queue, skipping what is already labelled. */
export function order(queue: ReviewQueue, practiceCount = 5): { practice: Candidate[]; work: Candidate[] } {
  const gold = queue.candidates.filter((c) => c.gold);
  const realGold = gold.filter((c) => c.gold!.answer === "real");
  const bogusGold = gold.filter((c) => c.gold!.answer === "bogus");
  const practice: Candidate[] = [];
  for (let i = 0; practice.length < practiceCount && (i < realGold.length || i < bogusGold.length); i++) {
    if (realGold[i]) practice.push(realGold[i]);
    if (bogusGold[i] && practice.length < practiceCount) practice.push(bogusGold[i]);
  }
  const used = new Set(practice.map((c) => c.id));
  return { practice, work: queue.candidates.filter((c) => !used.has(c.id)) };
}

export function nextUnlabelled(items: Candidate[], labels: Labels, from = 0): number {
  for (let i = from; i < items.length; i++) if (!labels[items[i].id]) return i;
  for (let i = 0; i < from; i++) if (!labels[items[i].id]) return i;
  return -1;
}

export function summary(items: Candidate[], labels: Labels) {
  let real = 0, bogus = 0, unsure = 0, goldSeen = 0, goldRight = 0, agreeModel = 0, decided = 0;
  for (const c of items) {
    const l = labels[c.id];
    if (!l) continue;
    if (l.answer === "real") real++;
    else if (l.answer === "bogus") bogus++;
    else unsure++;
    if (c.gold && l.answer !== "unsure") {
      goldSeen++;
      if (c.gold.answer === l.answer) goldRight++;
    }
    if (l.answer !== "unsure") {
      decided++;
      if ((c.ml_score >= 0.5) === (l.answer === "real")) agreeModel++;
    }
  }
  return { done: real + bogus + unsure, total: items.length, real, bogus, unsure, goldSeen, goldRight, agreeModel, decided };
}

/** JSON a volunteer can send back to the team; becomes new training labels for ml/train.py. */
export function exportPayload(queue: ReviewQueue, labels: Labels, volunteer: string) {
  return {
    schema_version: "review-labels-1.0",
    set_id: queue.set_id,
    synthetic: queue.synthetic,
    volunteer: volunteer.trim().slice(0, 60) || "anonymous",
    exported_utc: new Date().toISOString(),
    labels: queue.candidates
      .filter((c) => labels[c.id])
      .map((c) => ({ id: c.id, group: c.group, ra_deg: c.ra_deg, dec_deg: c.dec_deg, ...labels[c.id], ml_score: c.ml_score })),
  };
}

export function verdict(score: number) {
  if (score >= 0.8) return { text: "likely a real mover", tone: "real" as const };
  if (score >= 0.5) return { text: "maybe real", tone: "maybe" as const };
  if (score >= 0.2) return { text: "probably an artefact", tone: "maybe" as const };
  return { text: "likely an artefact", tone: "bogus" as const };
}

export const KIND_HELP: Record<string, string> = {
  mover: "A round dot the size of a star that is in the NEW image but not in the OLD one. In the difference it is a clean white dot.",
  injected: "A test source we added on purpose to check the search. It looks exactly like a real faint mover.",
  cosmic: "Cosmic ray or hot pixel: one or two very sharp pixels, smaller than a star, with nothing around them.",
  dipole: "A star that did not subtract cleanly: it is in BOTH images, and the difference shows a black-and-white pair.",
  ghost: "Optical ghost or glare: a big soft blob, much wider than a star.",
  streak: "Satellite or particle streak: an elongated line, not a round dot.",
  neptune_other: "Not the planet: glare, a ghost of the bright planet, or a star residual near it.",
};
