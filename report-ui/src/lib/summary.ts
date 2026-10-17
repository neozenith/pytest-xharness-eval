/**
 * `SessionSummaryTable`'s rows (ADR 0042, ADR 0071): one per cell of exactly the sessions the
 * `SessionTable` beneath it lists, each carrying that cell's Important Metrics. Pure and
 * unit-tested, like `lib/series.ts`.
 *
 * GROUPING KEY: skill × case × harness × model × effort × treatment — deliberately the same partition
 * `accumulationGroups` draws with (its `suite` basename is 1:1 with `case` within a skill), so
 * one summary row is one line of the `TokenAccumulationChart` and the two read as a pair. It is
 * also exactly the cell `emit/samples.py` reduces samples over, so a row finds its aggregates by
 * this same key. Row order is fixed and ascending by that key (a null skill last), compared with
 * plain `<` — except effort, which is a ladder and sorts by rung position (`lib/effort.ts`), a
 * group that named no rung after every rung; and treatment, whose control leads its treated twins
 * (`lib/treatment.ts`). Deterministic, locale-independent, and no second sort param on the route.
 *
 * Effort is in the key because two rungs of one model are two experiments (ADR 0049), and
 * treatment twice over (ADR 0055): a control and its treated twin are the comparison the axis
 * exists to measure, so they are two adjacent rows, never one blended figure.
 *
 * NO ARITHMETIC HERE. Each metric declares its own aggregates (ADR 0071, superseding the single
 * mean of ADR 0042 §3): a median and quartiles for a heavy-tailed cost, a mean and extremes for a
 * share, a pass rate with its interval for the verdict. Python reduces the samples once and this
 * module looks the result up, so the page and `index.json` can never disagree about a cell. Every
 * facet the overview filters by is part of this key or a property of the model, so a filter drops
 * whole cells and never splits one: an aggregate computed over the whole cell is still true of the
 * row shown.
 */
import { compareEffort } from "./effort";
import { compareTreatment } from "./treatment";
import type { Aggregates, Cell, ImportantMetricsDoc } from "./types";

/** The six fields that name a cell, on a session row and on `index.json`'s aggregated cells alike. */
export type CellIdentity = Pick<Cell, "skill" | "case" | "harness" | "model" | "effort" | "treatment">;

export interface SummaryRow {
  key: string;
  skill: string | null;
  case: string;
  harness: string;
  model: string;
  /** The rung every run in the group was sent; null when none named one (ADR 0049). */
  effort: string | null;
  /** The treatment every run in the group ran under; null for the control (ADR 0055). */
  treatment: string | null;
  /**
   * The model catalogue's facts about the group's model (ADR 0057). A property of the model, never
   * part of the key: every run in a group ran the same model, so they agree by construction.
   */
  line: string | null;
  family_tier: number | null;
  released: string | null;
  /** Sessions this group lists: the rows of `SessionTable` it rolls up. */
  runs: number;
  /** Graded sessions the aggregates are over (ADR 0071); fewer than `runs` when some carry no verdict. */
  samples: number;
  /** Each Important Metric's aggregates by metric id; empty when `index.json` has none for this cell. */
  metrics: Record<string, Aggregates>;
}

/**
 * The arm a group belongs to: its key without the rung or the treatment, so one arm's rungs, and
 * each rung's control beside its treated twins, can be ordered side by side.
 */
export const armKey = (c: CellIdentity): string => `${c.skill ?? ""}|${c.case}|${c.harness}|${c.model}`;

/**
 * The one partition key, exported so `accumulationGroups` draws with *this* function rather than
 * a second spelling of it: the pairing is structural, not a coincidence two keys keep up.
 *
 * A treatment rides after the rung on the same `+` the cache's model level uses (ADR 0055), so a
 * control and its treated twin are two groups — the measured comparison the axis exists to show —
 * and a control's key is byte-identical to every key written before the axis. `+` never appears
 * in a rung, so `|high+x` cannot collide with a rung spelled `high+x`.
 */
export const groupKey = (c: CellIdentity): string => `${armKey(c)}${c.effort ? `|${c.effort}` : ""}${c.treatment ? `+${c.treatment}` : ""}`;

const cmp = (a: string, b: string): number => (a < b ? -1 : a > b ? 1 : 0);

/**
 * Ascending by skill (null last), then case, harness, model, effort in ladder order, and last the
 * treatment, control first: so a control row and its treated twins sit on adjacent lines.
 */
const byKey = (a: SummaryRow, b: SummaryRow): number => {
  if (a.skill !== b.skill) {
    if (a.skill == null) return 1;
    if (b.skill == null) return -1;
    return cmp(a.skill, b.skill);
  }
  return (
    cmp(a.case, b.case) || cmp(a.harness, b.harness) || cmp(a.model, b.model) || compareEffort(a.effort, b.effort) || compareTreatment(a.treatment, b.treatment)
  );
};

export function summaryRows(cells: Cell[], doc?: ImportantMetricsDoc): SummaryRow[] {
  const aggregated = new Map((doc?.cells ?? []).map((c) => [groupKey(c), c]));
  const groups = new Map<string, Cell[]>();
  for (const cell of cells) {
    const key = groupKey(cell);
    const group = groups.get(key);
    if (group) group.push(cell);
    else groups.set(key, [cell]);
  }
  const rows = [...groups.entries()].map(([key, group]): SummaryRow => {
    const first = group[0]!;
    const cell = aggregated.get(key);
    return {
      key,
      skill: first.skill,
      case: first.case,
      harness: first.harness,
      model: first.model,
      effort: first.effort,
      treatment: first.treatment,
      line: first.line,
      family_tier: first.family_tier,
      released: first.released,
      runs: group.length,
      samples: cell?.samples ?? 0,
      metrics: cell?.metrics ?? {},
    };
  });
  return rows.sort(byKey);
}
