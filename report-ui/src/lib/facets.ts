/**
 * The overview's filter vocabulary and its one predicate (ADR 0042). Pure, like `lib/series.ts`:
 * it reads no route and touches no DOM, so every rule here is unit-testable.
 *
 * OR within a facet, AND across facets: `?harness=claude,codex&model=claude-opus-5` selects the
 * cells whose harness is claude *or* codex *and* whose model is claude-opus-5. A `null` facet
 * matches every cell, which is exactly what an absent param means, so the unfiltered overview
 * runs the same predicate as a filtered one.
 *
 * `Cell.skill` and `Cell.effort` may be null. Null is never an option and is never selectable,
 * so a skill-less (or rung-less) cell survives only while that facet is `null` — a selection is
 * always a positive claim about a value the data actually carries. For `effort` that reading is
 * the right one twice over: a cell that named no rung ran at a CLI default nobody wrote down,
 * so there is no value to compare it against, and every session captured before ADR 0049 is in
 * exactly that position.
 *
 * `treatment` is the one facet whose null IS selectable (ADR 0055). A null treatment is the
 * control: not an absence but the measured baseline every treated twin is compared against, so
 * it carries the reserved name `control` (`lib/treatment.ts`) as its facet value and is selected
 * with `?treatment=control`, exactly like any named treatment. An untreated sweep offers no
 * treatment options at all — one `control` chip on every pre-ADR-0055 sweep would be a choice
 * with nothing to choose between.
 */
import { compareEffort } from "./effort";
import type { FacetSelection } from "./route";
import { anyTreated, compareTreatment, CONTROL, treatmentLabel } from "./treatment";
import type { Cell } from "./types";

export const FACETS = ["skill", "harness", "model", "effort", "treatment"] as const;
export type Facet = (typeof FACETS)[number];

export const facetValue = (cell: Cell, facet: Facet): string | null => (facet === "treatment" ? treatmentLabel(cell.treatment) : cell[facet]);

/** `control` first, then the named treatments alphabetically: the baseline leads its twins. */
const compareTreatmentLabel = (a: string, b: string): number => compareTreatment(a === CONTROL ? null : a, b === CONTROL ? null : b);

/**
 * The facet's distinct values across the sweep, lexicographic (`.sort()`, locale-independent,
 * the same order `ReportHeader` puts its skills in) — except `effort`, whose rungs come in ladder
 * order (`lib/effort.ts`): `low medium high` is a scale, and alphabetised it reads
 * `high low medium`; and `treatment`, whose `control` leads. Nulls are dropped: they are not
 * options. A sweep with no treated cell offers no treatment option, not a lone `control`.
 */
export function facetOptions(cells: Cell[], facet: Facet): string[] {
  if (facet === "treatment" && !anyTreated(cells)) return [];
  const values = new Set<string>();
  for (const cell of cells) {
    const value = facetValue(cell, facet);
    if (value != null) values.add(value);
  }
  return facet === "effort" ? [...values].sort(compareEffort) : facet === "treatment" ? [...values].sort(compareTreatmentLabel) : [...values].sort();
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
 * What clicking a chip would actually get you: the cells matching the OTHER facets whose own
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
