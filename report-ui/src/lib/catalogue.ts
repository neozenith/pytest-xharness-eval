/**
 * What kind of model ran (ADR 0057): the model catalogue's three facts about a model, as the page
 * reads them. Pure, like `lib/treatment.ts`.
 *
 * `line` is the provider's product line (`opus`, `sol`, …), `family_tier` a hand-curated numbered
 * role in the provider's lineup (1 the smallest), and `released` the model's release date. The
 * tier is a number, never a name, because lineup names are reassigned while the numbers keep
 * sliding — and the number is what makes two providers comparable: "every tier 3 model".
 *
 * All three are null on every session captured before the catalogue existed, and on a model it
 * never described. A null tier, like a missing rung, is never a facet option: there is no value
 * to compare it against. The index reader folds each wire spelling here, once.
 *
 * The tier is a property of the model, not a new partition: it never splits a summary group,
 * a nav branch or a chart line (`lib/summary.ts` `groupKey` does not name it).
 */

/** A tier the wire carries, or null: only a positive integer is one. */
export const tierOf = (tier: unknown): number | null => (typeof tier === "number" && Number.isInteger(tier) && tier >= 1 ? tier : null);

/** A product line, or null for an absent key or the empty string. */
export const lineOf = (line: unknown): string | null => (typeof line === "string" && line !== "" ? line : null);

/** A release date as the wire writes it (`YYYY-MM-DD`), or null for anything else. */
export const releasedOf = (released: unknown): string | null => (typeof released === "string" && /^\d{4}-\d{2}-\d{2}$/.test(released) ? released : null);

/** The tier's prose label, for a facet chip and the session metadata: `tier 3`. */
export const tierLabel = (tier: number): string => `tier ${tier}`;

/** The tier's compact mark inside a table's model cell: `T3`. */
export const tierBadge = (tier: number): string => `T${tier}`;

/** Ascending by number, so `tier 10` follows `tier 9` rather than `tier 1`. */
export const compareTier = (a: string, b: string): number => Number(a) - Number(b);

/** What the catalogue says of a model, for a cell's `title`: one clause per fact it has. */
export const catalogueNote = (c: { family_tier: number | null; line: string | null; released: string | null }): string =>
  [
    c.line != null ? `line ${c.line}` : null,
    c.family_tier != null ? `family tier ${c.family_tier}` : null,
    c.released != null ? `released ${c.released}` : null,
  ]
    .filter(Boolean)
    .join(" · ");

/** What the session metadata says for a fact the catalogue does not carry. */
export const NOT_CATALOGUED = "not in the model catalogue (captured before ADR 0057, or a model it does not describe)";
