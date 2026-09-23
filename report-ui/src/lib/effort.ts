/**
 * The effort axis on the page (ADR 0049): how a rung is ordered and how it is named beside the
 * harness and model it qualifies. Pure, like `lib/facets.ts`.
 *
 * ORDER. A rung is a position on a ladder, so the page sorts rungs by that position and never by
 * spelling: alphabetically `high < low < max < medium < xhigh`, which is the one order a reader
 * comparing budgets cannot use. `LADDER` mirrors the native rungs of `model/effort.py`, lowest
 * first. A rung this page has not heard of (a third harness's ladder) is still data: it sorts
 * after every known rung, lexically among its peers, and is never dropped or renamed.
 *
 * NULL. A cell that named no rung ran at a CLI default nobody wrote down, and every session
 * captured before ADR 0049 is in that position. It is not a rung, so it sorts after every rung
 * (the same place a null sorts in every column on this page) and a label simply omits it rather
 * than printing a word the CLI was never sent.
 */

/** The native rungs of `model/effort.py`, lowest first. Keep in step with `Effort` there. */
export const LADDER: readonly string[] = ["low", "medium", "high", "xhigh", "max"] as const;

/** The rung's position: its ladder index, or past the ladder for one the page does not know. */
export const effortRank = (effort: string): number => {
  const i = LADDER.indexOf(effort);
  return i === -1 ? LADDER.length : i;
};

/** Ladder order, unknown rungs after it (lexically), null last. */
export const compareEffort = (a: string | null, b: string | null): number => {
  if (a === b) return 0;
  if (a == null) return 1;
  if (b == null) return -1;
  return effortRank(a) - effortRank(b) || (a < b ? -1 : a > b ? 1 : 0);
};

/**
 * A sort value for a table column: numeric, so a column comparator that ranks with `<` puts the
 * ladder in order. Unknown rungs share one rank past the ladder; null stays null (sorts last).
 */
export const effortSortValue = (effort: string | null): number | null => (effort == null ? null : effortRank(effort));

/** `claude/claude-opus-5 · high`, or `claude/claude-opus-5` for a cell that named no rung. */
export const armLabel = (harness: string, model: string, effort: string | null): string => `${harness}/${model}${effort ? ` · ${effort}` : ""}`;

/** The rung as prose, for the places that must say something when there is none. */
export const EFFORT_DEFAULT = "not named: the CLI's default";
