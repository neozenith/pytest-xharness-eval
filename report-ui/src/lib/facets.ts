/**
 * The overview's filter vocabulary and its one predicate (ADR 0042). Pure, like `lib/series.ts`:
 * it reads no route and touches no DOM, so every rule here is unit-testable.
 *
 * OR within a facet, AND across facets: `?harness=claude,codex&model=claude-opus-5` selects the
 * cells whose harness is claude *or* codex *and* whose model is claude-opus-5. A `null` facet
 * matches every cell, which is exactly what an absent param means, so the unfiltered overview
 * runs the same predicate as a filtered one.
 *
 * `Cell.skill` may be null. Null is never an option and is never selectable, so a skill-less
 * cell survives only while the skill facet is `null` — a selection is always a positive claim
 * about a value the data actually carries.
 */
import type { FacetSelection } from "./route";
import type { Cell } from "./types";

export const FACETS = ["skill", "harness", "model"] as const;
export type Facet = (typeof FACETS)[number];

export const facetValue = (cell: Cell, facet: Facet): string | null => cell[facet];

/**
 * The facet's distinct values across the sweep, lexicographic (`.sort()`, locale-independent,
 * the same order `ReportHeader` puts its skills in). Nulls are dropped: they are not options.
 */
export function facetOptions(cells: Cell[], facet: Facet): string[] {
  const values = new Set<string>();
  for (const cell of cells) {
    const value = facetValue(cell, facet);
    if (value != null) values.add(value);
  }
  return [...values].sort();
}

export function matchesFacets(cell: Cell, facets: FacetSelection): boolean {
  for (const facet of FACETS) {
    const selected = facets[facet];
    if (!selected) continue;
    const value = facetValue(cell, facet);
    if (value == null || !selected.includes(value)) return false;
  }
  return true;
}

/** The visible cells: derived once by `SweepOverview` and handed to all three consumers. */
export const filterCells = (cells: Cell[], facets: FacetSelection): Cell[] => cells.filter((cell) => matchesFacets(cell, facets));

/**
 * What clicking a chip would actually get you: the cells matching the OTHER two facets whose own
 * value equals `value`. A facet never filters itself, so selecting `claude` does not collapse the
 * harness row to a single count of one — but it does zero the models claude never ran.
 */
export function facetCount(cells: Cell[], facets: FacetSelection, facet: Facet, value: string): number {
  const others: FacetSelection = { ...facets, [facet]: null };
  return cells.filter((cell) => facetValue(cell, facet) === value && matchesFacets(cell, others)).length;
}

/** Add at the end, remove in place; the facet returns to `null` — every value — when the last one goes. */
export function toggleFacet(facets: FacetSelection, facet: Facet, value: string): FacetSelection {
  const current = facets[facet] ?? [];
  const next = current.includes(value) ? current.filter((v) => v !== value) : [...current, value];
  return { ...facets, [facet]: next.length ? next : null };
}

/**
 * The one sentence the chart, the summary and the session table all print when the filter selects
 * nothing. One string, so a filtered-to-nothing overview says so three times in one voice rather
 * than in three near-identical wordings — or, worse, as three empty boxes.
 */
export const NO_MATCH = "No session matches the current filters.";
