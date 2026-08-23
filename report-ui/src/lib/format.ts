import type { Cell } from "./types";

/** Number and label formatting shared by every table and chart; `–` is the one "no value" glyph. */
export const NONE = "–";

export const fmt = (n: number | null | undefined): string => (n == null || Number.isNaN(n) ? NONE : n.toLocaleString("en-US"));
export const usd = (n: number | null | undefined): string => (n == null ? NONE : `$${n.toFixed(4)}`);
export const pct = (n: number | null | undefined): string => (n == null ? NONE : `${n.toFixed(1)}%`);
export const secs = (ms: number | null | undefined): string => (ms == null ? NONE : `${(ms / 1000).toFixed(1)}s`);
export const short = (id: string | null | undefined): string => (id ? id.slice(0, 8) : NONE);

/** `1000000` -> `1M`, `200000` -> `200k`; the window label beside every context figure. */
export const windowLabel = (w: number | null | undefined): string =>
  w == null ? "unknown window" : w >= 1e6 ? `${w / 1e6}M` : w >= 1e3 ? `${Math.round(w / 1e3)}k` : String(w);

export const when = (iso: string | null | undefined): string => {
  if (!iso) return NONE;
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short" });
};

export const modelTick = (model: string): string => model.replace(/^claude-/, "").replace(/^gpt-5\.6-/, "codex ");

/** `loaded/files · run/scripts`, ignored files excluded; a dash when no catalogue was taken. */
export const coverageText = (c: Cell): string => {
  const s = c.skill_coverage;
  if (s.files == null) return NONE;
  return `${s.loaded ?? 0}/${s.files} · ${s.run ?? 0}/${s.scripts ?? 0}`;
};
