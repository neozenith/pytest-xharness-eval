import type { Cell } from "./types";

/** Number and label formatting shared by every table and chart; `–` is the one "no value" glyph. */
export const NONE = "–";

export const fmt = (n: number | null | undefined): string => (n == null || Number.isNaN(n) ? NONE : n.toLocaleString("en-US"));
export const usd = (n: number | null | undefined): string => (n == null ? NONE : `$${n.toFixed(4)}`);

/**
 * Three decimals rather than four, for the tables that print a cost beside thirteen other
 * columns. A tenth of a cent is below the resolution at which anyone ranks a sweep, and the
 * fourth digit was the widest glyph in the densest column; `ReconciliationPanel` and
 * `CostByTierPanel`, which exist to reconcile figures, keep `usd`.
 */
export const usd3 = (n: number | null | undefined): string => (n == null ? NONE : `$${n.toFixed(3)}`);
export const pct = (n: number | null | undefined): string => (n == null ? NONE : `${n.toFixed(1)}%`);
export const secs = (ms: number | null | undefined): string => (ms == null ? NONE : `${(ms / 1000).toFixed(1)}s`);
export const short = (id: string | null | undefined): string => (id ? id.slice(0, 8) : NONE);

/**
 * A fixed number of decimals, always. `fmt` drops a trailing zero, so `86.8` and `32.80` sat one
 * glyph apart and the decimal points walked — which is the whole of what a right-aligned
 * tabular-numeral column buys you. `SessionTable` and `SessionSummaryTable` print the same
 * quantities, so they print them through the same function.
 */
export const dec = (n: number, digits = 2): string => n.toLocaleString("en-US", { minimumFractionDigits: digits, maximumFractionDigits: digits });

/** `1000000` -> `1M`, `200000` -> `200k`; the window label beside every context figure. */
export const windowLabel = (w: number | null | undefined): string =>
  w == null ? "unknown window" : w >= 1e6 ? `${w / 1e6}M` : w >= 1e3 ? `${Math.round(w / 1e3)}k` : String(w);

export const when = (iso: string | null | undefined): string => {
  if (!iso) return NONE;
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short" });
};

export const modelTick = (model: string): string => model.replace(/^claude-/, "").replace(/^gpt-5\.6-/, "codex ");

/**
 * The vendor prefix every model of a provider shares: `claude-sonnet-5` -> `sonnet-5`,
 * `gpt-5.6-sol` -> `5.6-sol`. It is a column of glyphs that is constant within a harness, and
 * the harness is its own column one across, so the prefix says nothing the row does not.
 */
const VENDOR = /^(?:claude|gpt|openai|anthropic|gemini|google)-/;
export const modelShort = (model: string): string => model.replace(VENDOR, "");

/**
 * Short model names for a whole sweep, computed ONCE over the unfiltered cells so a name never
 * changes under a filter. Shortening is abandoned for the *whole* set the moment any two models
 * would collide: two rows reading `sonnet-5` with different `title`s is worse than a wide column,
 * and a partial map (some short, some full) reads as an inconsistency rather than as a rule.
 */
export function modelShortNames(models: Iterable<string>): (model: string) => string {
  const full = [...new Set(models)];
  const shortened = full.map(modelShort);
  const collides = new Set(shortened).size !== full.length;
  if (collides) return (model) => model;
  const map = new Map(full.map((m, i) => [m, shortened[i]!]));
  return (model) => map.get(model) ?? modelShort(model);
}

/**
 * `1,504,090` -> `1.5M`, `29,412` -> `29.4k`. Three significant figures is the most a reader
 * compares down a column at a glance, and the exact figure is always on the cell's `title`, so
 * the precision is moved rather than lost. Below 1000 the number is already short: print it.
 */
export const compact = (n: number | null | undefined): string => {
  if (n == null || Number.isNaN(n)) return NONE;
  const abs = Math.abs(n);
  if (abs >= 1e6) return `${dec(n / 1e6, 1)}M`;
  if (abs >= 1e3) {
    // The unit is chosen from the *rounded* figure, not the raw one: 999,999 rounds to 1000.0 at
    // one decimal, and `1,000.0k` is both wider than the number it abbreviates and a separator
    // inside a unit that is supposed to have replaced them.
    const k = n / 1e3;
    return Math.round(Math.abs(k) * 10) / 10 >= 1e3 ? `${dec(k / 1e3, 1)}M` : `${dec(k, 1)}k`;
  }
  return fmt(Math.round(n));
};

/**
 * `eval_discovery_refresh` -> `discovery_refresh`. Every case in a sweep is named `eval_*` (ADR
 * 0008 makes the prefix the collection rule), so the five glyphs are the same on every row: they
 * cost width and carry no signal. The full name stays on the cell's `title`.
 */
export const caseShort = (name: string): string => (name.startsWith("eval_") ? name.slice(5) : name);

/**
 * The share the `skill coverage` cell prints, not the raw `loaded` count behind it. A sweep
 * spanning two skills has two catalogue sizes (discovery has 5 files, mermaidjs-diagrams 18),
 * so sorting on the count inverted the column's own meaning: `6/18` (33%) ranked above `5/5`
 * (100%). This is the same normalisation the neighbouring `peak context` column makes by
 * sorting on `context_window_pct` rather than `peak_context_tokens`. A cell with no catalogue
 * stays null, so it keeps going last in both directions — and is skipped, not zero-filled, by
 * `lib/summary.ts`'s mean.
 */
export const coverageShare = (c: Cell): number | null => {
  const { files, loaded } = c.skill_coverage;
  return files != null && files > 0 ? (loaded ?? 0) / files : null;
};

/** `loaded/files · run/scripts`, ignored files excluded; a dash when no catalogue was taken. */
export const coverageText = (c: Cell): string => {
  const s = c.skill_coverage;
  if (s.files == null) return NONE;
  return `${s.loaded ?? 0}/${s.files} · ${s.run ?? 0}/${s.scripts ?? 0}`;
};
