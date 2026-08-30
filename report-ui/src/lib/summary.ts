/**
 * `SessionSummaryTable`'s arithmetic (ADR 0042): the aggregate of exactly the cells the
 * `SessionTable` beneath it lists. Pure and unit-tested, like `lib/series.ts`.
 *
 * GROUPING KEY: skill × case × harness × model — deliberately the same partition
 * `accumulationGroups` draws with (its `suite` basename is 1:1 with `case` within a skill), so
 * one summary row is one line of the `TokenAccumulationChart` above and the two read as a pair.
 * Row order is fixed and ascending by that key (a null skill last), compared with plain `<`:
 * deterministic, locale-independent, and no second sort param on the route.
 *
 * THE ONE AGGREGATION RULE, applied to every `mean_*` field: the arithmetic mean over the
 * group's cells that carry a value, and `null` when none of them does. A missing value is never
 * treated as zero and the divisor is the count of present values, never `runs` — a sparse column
 * has to read as sparse.
 *
 * MEAN, NOT MEDIAN, deliberately: (i) the sibling chart already draws a *mean* line with a
 * min–max envelope, so a median row beside it would disagree with the picture the reader is
 * looking at, by construction; (ii) cost and tokens are additive, so `mean × runs` is the group's
 * total — the arithmetic a reader actually does — and a median has no such relation; (iii) group
 * `n` is 1–2 on a real capture, where a median is either the single value or the mean of the two.
 * Every column is named `mean <field>` in full (ADR 0021), so the choice is never inferred.
 */
import { coverageShare } from "./format";
import type { Cell } from "./types";

export interface SummaryRow {
  key: string;
  skill: string | null;
  case: string;
  harness: string;
  model: string;
  runs: number;
  /** runs whose verdict is exactly `pass`, over `graded` — an ungraded run is never a failure. */
  pass: number;
  /** runs that carry a verdict at all; the pass rate's denominator. */
  graded: number;
  mean_estimated_cost_usd: number | null;
  mean_accumulative_billed_tokens: number | null;
  mean_peak_context_tokens: number | null;
  mean_context_window_pct: number | null;
  context_window: number | null;
  mean_turns: number | null;
  mean_tool_calls: number | null;
  mean_skill_coverage_share: number | null;
  mean_output_tokens_per_sec: number | null;
  mean_wall_ms: number | null;
}

const groupKey = (c: Cell): string => `${c.skill ?? ""}|${c.case}|${c.harness}|${c.model}`;

const mean = (cells: Cell[], valueOf: (c: Cell) => number | null | undefined): number | null => {
  const values = cells.map(valueOf).filter((v): v is number => v != null && !Number.isNaN(v));
  return values.length ? values.reduce((sum, v) => sum + v, 0) / values.length : null;
};

const cmp = (a: string, b: string): number => (a < b ? -1 : a > b ? 1 : 0);

/** Ascending by skill (null last), then case, harness, model. */
const byKey = (a: SummaryRow, b: SummaryRow): number => {
  if (a.skill !== b.skill) {
    if (a.skill == null) return 1;
    if (b.skill == null) return -1;
    return cmp(a.skill, b.skill);
  }
  return cmp(a.case, b.case) || cmp(a.harness, b.harness) || cmp(a.model, b.model);
};

export function summaryRows(cells: Cell[]): SummaryRow[] {
  const groups = new Map<string, Cell[]>();
  for (const cell of cells) {
    const key = groupKey(cell);
    const group = groups.get(key);
    if (group) group.push(cell);
    else groups.set(key, [cell]);
  }
  const rows = [...groups.entries()].map(([key, group]): SummaryRow => {
    const first = group[0]!;
    return {
      key,
      skill: first.skill,
      case: first.case,
      harness: first.harness,
      model: first.model,
      runs: group.length,
      pass: group.filter((c) => c.verdict === "pass").length,
      graded: group.filter((c) => c.verdict != null).length,
      mean_estimated_cost_usd: mean(group, (c) => c.estimated_cost_usd),
      mean_accumulative_billed_tokens: mean(group, (c) => c.accumulative_billed_tokens),
      mean_peak_context_tokens: mean(group, (c) => c.peak_context_tokens),
      // The mean of the cells' own `context_window_pct`, not `mean_peak / context_window`: the
      // window is constant within a group today, so the two agree, and taking the cell's own
      // field keeps the column honest if a group ever spans two windows.
      mean_context_window_pct: mean(group, (c) => c.context_window_pct),
      context_window: group.find((c) => c.context_window != null)?.context_window ?? null,
      mean_turns: mean(group, (c) => c.turns),
      mean_tool_calls: mean(group, (c) => c.tool_calls),
      // `loaded / files`, ignored files already excluded upstream; a cell with no catalogue is
      // skipped rather than counted as zero coverage.
      mean_skill_coverage_share: mean(group, coverageShare),
      mean_output_tokens_per_sec: mean(group, (c) => c.output_tokens_per_sec),
      mean_wall_ms: mean(group, (c) => c.wall_ms),
    };
  });
  return rows.sort(byKey);
}
