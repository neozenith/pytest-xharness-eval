/**
 * The route-permutation matrix: every deeplinkable URL state of the SPA, enumerated from the
 * data itself. The Playwright matrix test sweeps exactly this list, so a permutation's
 * `slug` is the shared language between a human, an agent and the e2e artifacts saved
 * under `tmp/e2e/<test>/<slug>/` — one slug names one screenshot, one console log and one
 * set of network timings.
 *
 * Keep this the single source of truth: a new route param added to `lib/route.ts` must be
 * enumerated here in the same change, or the matrix silently stops covering it.
 */
import { overviewSearch, sessionSearch, type TurnView } from "./route";
import type { Cell, Index, RunResult } from "./types";

export interface Permutation {
  /** Unique, deterministic, filesystem-safe id for this state. */
  slug: string;
  /** The query string that deeplinks to this state (`"?"` for the plain overview). */
  search: string;
  /** What a human should expect to see. */
  description: string;
}

/** Lowercase, alphanumerics and dashes only: safe as a directory name and stable across runs. */
export function slugify(...parts: (string | number | null | undefined)[]): string {
  return parts
    .filter((p): p is string | number => p != null && p !== "")
    .map((p) =>
      String(p)
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, "-")
        .replace(/^-+|-+$/g, ""),
    )
    .filter(Boolean)
    .join("--");
}

function cellSlug(cell: Cell): string {
  // The case × harness × model triple reads well; the session-id prefix guarantees
  // uniqueness when the same cell was captured more than once.
  return slugify(cell.case, `${cell.harness}-${cell.model}`, cell.session_id.slice(0, 8));
}

function turnCount(cell: Cell, result: RunResult | null | undefined): number {
  if (result?.calls?.length) return result.calls.length;
  return cell.turns ?? 0;
}

/**
 * A tier constrains each dimension of the matrix to one or many of its possible values, so
 * the cartesian product scales with the cost you are willing to absorb:
 *
 *   small   the inner loop: one session per harness, one mid turn, detailed view only
 *   medium  breadth: one session per harness×model, first/middle/last turns, every variant
 *   large   the full covering matrix: every session, every turn, both views, every variant
 *
 * A tier's permutations keep the slugs they would have in `large`, so a faster run
 * refreshes a subset of the same `tmp/e2e/matrix/<slug>/` artifact tree.
 */
export type TierName = "small" | "medium" | "large";

export interface MatrixTier {
  name: TierName;
  /** which sessions participate */
  cells: (cells: Cell[]) => Cell[];
  /** which turn numbers of an n-turn session participate */
  turns: (n: number) => number[];
  /** which turn-table views participate */
  views: TurnView[];
  /** which single-param variants are included */
  variants: { sortedOverview: boolean; darkOverview: boolean; axisLine: boolean; dark: boolean; recRaw: boolean; line: boolean };
}

const firstBy = (cells: Cell[], keyOf: (c: Cell) => string): Cell[] => {
  const seen = new Set<string>();
  return cells.filter((c) => {
    const key = keyOf(c);
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
};

const mid = (n: number): number => Math.max(1, Math.ceil(n / 2));

export const TIERS: Record<TierName, MatrixTier> = {
  small: {
    name: "small",
    cells: (cells) => firstBy(cells, (c) => c.harness),
    turns: (n) => (n ? [mid(n)] : []),
    views: ["detailed"],
    variants: { sortedOverview: false, darkOverview: false, axisLine: false, dark: false, recRaw: false, line: false },
  },
  medium: {
    name: "medium",
    cells: (cells) => firstBy(cells, (c) => `${c.harness}/${c.model}`),
    turns: (n) => (n ? [...new Set([1, mid(n), n])] : []),
    views: ["summary", "detailed"],
    variants: { sortedOverview: true, darkOverview: true, axisLine: true, dark: true, recRaw: true, line: true },
  },
  large: {
    name: "large",
    cells: (cells) => cells,
    turns: (n) => Array.from({ length: n }, (_, i) => i + 1),
    views: ["summary", "detailed"],
    variants: { sortedOverview: true, darkOverview: true, axisLine: true, dark: true, recRaw: true, line: true },
  },
};

/**
 * Enumerate the tier's covering matrix: the overview (plain, sorted, dark), then per
 * participating session its landing state, the per-line chart axis, the dark theme, the raw
 * record view, a record-level `line=` deeplink, and the tier's turns in the tier's views.
 * In `large` every route param appears in at least one permutation per view type; the full
 * cross-product of params is reachable by URL but is not swept (it would multiply the
 * matrix without exercising any new code path).
 */
export function enumeratePermutations(
  index: Index,
  results: Record<string, RunResult | null | undefined> = {},
  tier: TierName | MatrixTier = "large",
): Permutation[] {
  const t = typeof tier === "string" ? TIERS[tier] : tier;
  const perms: Permutation[] = [{ slug: "overview", search: "?", description: `SweepOverview: ${index.cells.length} sessions` }];
  if (t.variants.sortedOverview) {
    perms.push({
      slug: "overview--sort-cost",
      search: overviewSearch({ key: "estimated_cost_usd", dir: "desc" }),
      description: "SweepOverview sorted by estimated cost",
    });
  }
  if (t.variants.darkOverview) {
    perms.push({ slug: "overview--dark", search: overviewSearch(null, "dark"), description: "SweepOverview in the dark theme" });
  }
  for (const cell of t.cells(index.cells)) {
    const base = cellSlug(cell);
    const name = `${cell.case} ${cell.harness}/${cell.model}`;
    perms.push({ slug: base, search: sessionSearch(cell.session_id), description: `SessionView: ${name}` });
    if (t.variants.axisLine) {
      perms.push({
        slug: `${base}--axis-line`,
        search: sessionSearch(cell.session_id, null, null, { axis: "line" }),
        description: `SessionView: ${name}, per-line axis`,
      });
    }
    if (t.variants.dark) {
      perms.push({
        slug: `${base}--dark`,
        search: sessionSearch(cell.session_id, null, null, { theme: "dark" }),
        description: `SessionView: ${name}, dark theme`,
      });
    }
    if (t.variants.recRaw) {
      perms.push({
        slug: `${base}--detailed--rec-raw`,
        search: sessionSearch(cell.session_id, null, "detailed", { rec: "raw" }),
        description: `SessionView: ${name}, detailed turn table, raw records`,
      });
    }
    if (t.variants.line) {
      // one record-level deeplink per session: the first record of the second turn (else the first)
      const calls = results[cell.session_id]?.calls ?? [];
      const line = (calls[1] ?? calls[0])?.records?.[0];
      if (line != null) {
        perms.push({
          slug: `${base}--line-${String(line).padStart(3, "0")}`,
          search: sessionSearch(cell.session_id, null, null, { line }),
          description: `SessionView: ${name}, scrolled to log line ${line}`,
        });
      }
    }
    const turns = t.turns(turnCount(cell, results[cell.session_id]));
    for (const view of t.views) {
      // Compose onto the already-slugified base: re-slugifying would collapse its `--` separators.
      perms.push({
        slug: `${base}--${view}`,
        search: sessionSearch(cell.session_id, null, view),
        description: `SessionView: ${name}, ${view} turn table`,
      });
      for (const turn of turns) {
        perms.push({
          slug: `${base}--${view}--turn-${String(turn).padStart(2, "0")}`,
          search: sessionSearch(cell.session_id, turn, view),
          description: `SessionView: ${name}, turn ${turn} open, ${view} records`,
        });
      }
    }
  }
  return perms;
}

/** Throw when two permutations collide: every slug must name exactly one state. */
export function assertUniqueSlugs(perms: Permutation[]): void {
  const seen = new Map<string, string>();
  for (const p of perms) {
    const other = seen.get(p.slug);
    if (other !== undefined) throw new Error(`duplicate slug "${p.slug}": "${other}" and "${p.search}"`);
    seen.set(p.slug, p.search);
  }
}
