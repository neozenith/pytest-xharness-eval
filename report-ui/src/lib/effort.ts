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
  // `== null` on both sides, not `===`: a key a pre-axis row never wrote (`undefined`) and a
  // `null` are the same no-rung, or the comparator answers 1 both ways and a sort is undefined.
  if (a == null || b == null) return a == null ? (b == null ? 0 : 1) : -1;
  if (a === b) return 0;
  return effortRank(a) - effortRank(b) || (a < b ? -1 : a > b ? 1 : 0);
};

/**
 * A sort value for a table column, which ranks with a plain `<`: the ladder position, zero-padded,
 * then the rung itself, so `<` on it is exactly `compareEffort`. Unknown rungs sort lexically
 * among themselves rather than tying (a tie left two of a third harness's rungs in whatever order
 * the rows arrived, and a descending click did not reverse them). Null stays null (sorts last).
 */
export const effortSortValue = (effort: string | null): string | null => (effort == null ? null : `${String(effortRank(effort)).padStart(3, "0")} ${effort}`);

/**
 * The rung a wire row carries, or null for none. ADR 0049 lets an emitter write the empty string
 * for a cell that named no rung, and a row captured before the axis has no key at all; both are
 * "no rung", and `Cell` says `string | null`, so the index reader folds them here, once.
 */
export const rungOf = (effort: unknown): string | null => (typeof effort === "string" && effort !== "" ? effort : null);

/** `claude/claude-opus-5 · high`, or `claude/claude-opus-5` for a cell that named no rung. */
export const armLabel = (harness: string, model: string, effort: string | null): string => `${harness}/${model}${effort ? ` · ${effort}` : ""}`;

/** The rung as prose, for the places that must say something when there is none. */
export const EFFORT_DEFAULT = "not named: the CLI's default";
