/**
 * The treatment axis on the page (ADR 0055): how a treatment is named, ordered and selected
 * beside the harness, model and rung it qualifies. Pure, like `lib/effort.ts`.
 *
 * A treatment is a named directory of files layered over a case's fixture; the untreated cell
 * is its CONTROL, and every treated case also sweeps its control. On the wire a control is
 * `null` (an index row), `""` (a history line), or no key at all (every session captured before
 * ADR 0055). `Cell` says `string | null`, and the index reader folds all three to null here, once.
 *
 * UNLIKE A NULL RUNG, a control is a measured arm, not an absence: it is the baseline every
 * treated twin is compared against. So it is NAMED — the reserved word `control`, spelled once,
 * here — wherever a label is needed, it is selectable as a facet value (`?treatment=control`),
 * and it sorts FIRST: the baseline leads, then treatments alphabetically.
 */

/** The reserved word for the untreated arm. The Python side refuses it as a treatment name. */
export const CONTROL = "control";

/**
 * The treatment a wire row carries, or null for the control. The empty string, an absent key and
 * the reserved word itself all mean "untreated", so none of them reaches a consumer as a name.
 */
export const treatmentOf = (treatment: unknown): string | null =>
  typeof treatment === "string" && treatment !== "" && treatment !== CONTROL ? treatment : null;

/** The arm's name for a label, a facet chip or a column: the treatment, or `control`. */
export const treatmentLabel = (treatment: string | null | undefined): string => treatment ?? CONTROL;

/** Control first, then treatments alphabetically (`<`, locale-independent). */
export const compareTreatment = (a: string | null | undefined, b: string | null | undefined): number => {
  // `== null` on both sides: an absent key and a null are the same control.
  if (a == null || b == null) return a == null ? (b == null ? 0 : -1) : 1;
  return a < b ? -1 : a > b ? 1 : 0;
};

/**
 * A sort value for a table column, which ranks with a plain `<` and puts a null last: so the
 * control is a real value (`0`) and every treatment sorts after it (`1 <name>`), exactly
 * `compareTreatment`. Never null — the control is the one row that must lead.
 */
export const treatmentSortValue = (treatment: string | null | undefined): string => (treatment == null ? "0" : `1 ${treatment}`);

/** Whether any of these cells ran under a treatment: an untreated sweep never shows the axis. */
export const anyTreated = (cells: readonly { treatment: string | null }[]): boolean => cells.some((c) => c.treatment != null);

/** The treatment as prose, for the session metadata row of a control. */
export const TREATMENT_CONTROL = "control: the case's fixture alone, no treatment layered over it";
