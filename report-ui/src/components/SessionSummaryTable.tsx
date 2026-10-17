/**
 * The Important Metrics of exactly the runs `SessionTable` lists (glossary: `SessionSummaryTable`,
 * ADR 0042, ADR 0071): one row per skill × case × harness × model × effort × treatment — one cell
 * of the experiment, and one line of the `TokenAccumulationChart` — so the overview leads with how
 * each cell performed across its samples rather than with a pass count.
 *
 * Its measure columns are not written here. They are the metrics `model/metrics.py` declares,
 * read from `index.json` in declaration order, so a metric added in Python is a column here with no
 * edit. Each cell prints its metric's headline aggregate (a median for a spread, a mean for a share
 * or a count, a pass rate for the verdict) and its `title` spells out every aggregate, so the
 * spread is one hover away and costs no width (ADR 0043).
 *
 * It takes the cells it is given and knows nothing about filters; its grouping is in
 * `lib/summary.ts`. It sorts on its OWN param pair (`ssort`/`sdir`), because the reader ranks
 * cells by cost while ranking sessions by when they ran, and a shared pair would have made every
 * click here silently reorder the table below. Unsorted, the rows come out in the fixed
 * `skill|case|harness|model|effort|treatment` key order — the only order in which the banding and
 * the repeat muting below tell the truth, which is why both switch off the moment a column is sorted.
 *
 * Every measure head answers to its full name — the headline's operation and the field it reduces,
 * `median estimated_cost_usd` (ADR 0021) — in its tooltip and its accessible name, while printing
 * only the metric's short label.
 */
import { useMemo } from "react";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { ColumnHead } from "@/components/ColumnHead";
import { TierBadge } from "@/components/TierBadge";
import { caseShort, fmt, modelShort, NONE } from "@/lib/format";
import { aggregatesTitle, formatAggregate, headline, headlineValue, metricName } from "@/lib/metrics";
import { effortSortValue } from "@/lib/effort";
import { NO_MATCH } from "@/lib/facets";
import { anyTreated, treatmentLabel, treatmentSortValue } from "@/lib/treatment";
import { overviewWith, replaceRoute, useRoute, type SortDir } from "@/lib/route";
import { summaryRows, type SummaryRow } from "@/lib/summary";
import type { RowContext } from "@/components/SessionTable";
import type { Cell, ImportantMetric, ImportantMetricsDoc } from "@/lib/types";

interface Column {
  /** The `ssort=` value: short, stable, and never the printed label. */
  key: string;
  /** The canonical name: the tooltip's first line and the head's accessible name. */
  name: string;
  /** What the header prints. */
  label: string;
  title: string;
  numeric?: boolean;
  /** The first metrics column; it draws the rule that divides the table in two. */
  group?: boolean;
  /**
   * True when this row's value repeats the row above's, so the cell can recede to the muted
   * ink and let the first of each run lead. Only the fixed-order `SessionSummaryTable` may do
   * this: `SessionTable` re-sorts, so "the row above" there is whatever the reader last
   * clicked and a suppressed repeat would be a lie about the order.
   */
  repeat?: (r: SummaryRow, above: SummaryRow) => boolean;
  /** What the column ranks by; a null always sorts last, in both directions. */
  sortValue: (r: SummaryRow) => string | number | null;
  render: (r: SummaryRow, ctx: RowContext) => React.ReactNode;
}

/** A missing aggregate is the shared muted glyph, never `0`: a sparse column has to read as sparse. */
const nil = <span className="muted">{NONE}</span>;
const orNil = (v: unknown, text: string): React.ReactNode => (v == null ? nil : text);

const KEY_COLUMNS: Column[] = [
  {
    key: "skill",
    name: "skill",
    label: "skill",
    title: "the skill under test",
    // Eight consecutive `mermaidjs-diagrams` at full ink were the heaviest mark in the table
    // and the one carrying the least information. The repeats are still printed — a row read
    // on its own, or copied out of the page, still says which skill it is — but they recede,
    // so the eye lands on `case`, which is what actually changes down the column.
    repeat: (r, above) => r.skill === above.skill,
    sortValue: (r) => r.skill,
    render: (r) => orNil(r.skill, r.skill ?? ""),
  },
  {
    key: "case",
    name: "case",
    label: "case",
    title: "the @evalcase function, without the eval_ prefix every case shares; hover a cell for the full name",
    sortValue: (r) => r.case,
    render: (r) => <span title={r.case}>{caseShort(r.case)}</span>,
  },
  { key: "harness", name: "harness", label: "harness", title: "which CLI ran the runs in this group", sortValue: (r) => r.harness, render: (r) => r.harness },
  {
    key: "model",
    name: "model",
    label: "model",
    title: "the model the harness was told to use, without its vendor prefix; hover a cell for the full id",
    sortValue: (r) => r.model,
    // The tier is a mark on the model, never a column or a key (ADR 0057): it never splits a group.
    render: (r, ctx) => (
      <>
        <code title={r.model}>{ctx.shortModel(r.model)}</code>
        <TierBadge model={r} />
      </>
    ),
  },
  {
    key: "effort",
    name: "effort",
    label: "effort",
    title: "the reasoning rung every run in this group was sent, on that harness's own ladder; blank when none was named and the CLI ran at its default",
    // A rung is a position on a ladder, so it ranks by that position: `low` before `max`, never
    // `high` before `low` because h sorts before l.
    sortValue: (r) => effortSortValue(r.effort),
    render: (r) => orNil(r.effort, r.effort ?? ""),
  },
  {
    key: "treatment",
    name: "treatment",
    label: "treatment",
    title: "the named treatment every run in this group ran under (ADR 0055); control is the untreated arm, and leads its treated twins",
    // The control is the baseline, so it ranks first and is named rather than blank.
    sortValue: (r) => treatmentSortValue(r.treatment),
    render: (r) => treatmentLabel(r.treatment),
  },
  {
    key: "samples",
    name: "samples",
    label: "samples",
    title: "graded sessions of this cell: every metric to the right is reduced over these samples",
    numeric: true,
    group: true,
    sortValue: (r) => r.samples,
    render: (r) =>
      r.samples === r.runs ? (
        fmt(r.samples)
      ) : (
        <>
          {fmt(r.samples)}
          <span className="muted"> · {r.runs - r.samples} not graded</span>
        </>
      ),
  },
];

/**
 * The verdict's pass rate prints as the fraction it is, `passes/n`, because the table's one scanned
 * cell must answer the `VerdictBadge` rail below in the same key: a cell that did not pass clean
 * takes `bad` ink at 600 weight, a clean one stays quiet. The percentage and interval are its title.
 */
const verdictCell = (metric: ImportantMetric, r: SummaryRow): React.ReactNode => {
  const aggregates = r.metrics[metric.id];
  const rate = aggregates?.pass_rate;
  const n = aggregates?.n ?? 0;
  if (rate == null || !n) return nil;
  const passes = Math.round(rate * n);
  return (
    <span title={aggregatesTitle(metric, aggregates)}>
      <span className={passes === n ? undefined : "bad strong"}>
        {passes}/{n}
      </span>
    </span>
  );
};

/** One measure column per declared metric: its headline in the cell, every aggregate on the title. */
const metricColumn = (metric: ImportantMetric): Column => ({
  key: metric.id,
  name: metricName(metric),
  label: metric.label,
  title: `${metric.why}. Reduced over the cell's samples: ${metric.aggregates.join(", ")}; the cell shows the ${headline(metric)}`,
  numeric: true,
  sortValue: (r) => headlineValue(metric, r.metrics[metric.id]),
  render: (r) => {
    if (metric.kind === "rate") return verdictCell(metric, r);
    const value = headlineValue(metric, r.metrics[metric.id]);
    return value == null ? nil : <span title={aggregatesTitle(metric, r.metrics[metric.id])}>{formatAggregate(metric, headline(metric), value)}</span>;
  },
});

/**
 * One row per skill × case × harness × model × effort × treatment group of the cells it is given, in the fixed key
 * order until a head is clicked.
 */
export function SessionSummaryTable({
  cells,
  metrics,
  shortModel = modelShort,
}: {
  cells: Cell[];
  /** `index.json`'s `important_metrics`; absent, the table lists its cells with no measure columns. */
  metrics?: ImportantMetricsDoc;
  shortModel?: (model: string) => string;
}) {
  const route = useRoute();
  const routeSort = route.view === "overview" ? route.summarySort : null;
  const allColumns = useMemo(() => [...KEY_COLUMNS, ...(metrics?.metrics ?? []).map(metricColumn)], [metrics]);
  const column = routeSort ? (allColumns.find((c) => c.key === routeSort.key) ?? null) : null;
  const dir: 1 | -1 = routeSort?.dir === "desc" ? -1 : 1;
  const ctx: RowContext = { shortModel };
  /*
   * `treatment` shows only when a group in view ran under one (ADR 0055). An untreated sweep is
   * all control, and a column reading `control` down every row would print an axis it never used.
   */
  const columns = useMemo(() => (anyTreated(cells) ? allColumns : allColumns.filter((col) => col.key !== "treatment")), [cells, allColumns]);

  const rows = useMemo(() => {
    const grouped = summaryRows(cells, metrics);
    if (!column) return grouped;
    // `summaryRows` already returns the key order, and `sort` is stable, so equal values keep it:
    // ranking by `runs` leaves the groups that tie alphabetical rather than arbitrary.
    return [...grouped].sort((a, b) => {
      const x = column.sortValue(a);
      const y = column.sortValue(b);
      if (x == null && y == null) return 0;
      if (x == null) return 1;
      if (y == null) return -1;
      return (x < y ? -1 : x > y ? 1 : 0) * dir;
    });
  }, [cells, metrics, column, dir]);

  /**
   * What a click on this head would sort by. A fresh text column opens ascending (A first) and a
   * fresh measure descending (the largest first, which is the question a reader has about a mean
   * cost); clicking the active column flips it.
   */
  const nextDir = (col: Column): SortDir => (col.key === column?.key ? (dir === 1 ? "desc" : "asc") : col.numeric ? "desc" : "asc");
  const sortBy = (col: Column) => replaceRoute(overviewWith(route, { summarySort: { key: col.key, dir: nextDir(col) } }));

  return (
    /*
     * Every cell in this table's *body* is text: no row opens anything, nothing in one is
     * focusable. So the scroll box is the tab stop — see `scrollLabel` in components/ui/table.tsx
     * — or a column past the fold is readable with a mouse and by no other means.
     */
    <Table id="SessionSummaryTable" scrollLabel="Summary table, scrollable">
      {/*
       * Read before the table by a screen reader, which is where the word the eight measure heads
       * no longer print belongs: it qualifies all of them at once.
       */}
      <caption>
        each metric is reduced over the cell&apos;s samples by its own aggregate: the <span className="const">median</span> of a spread, the{" "}
        <span className="const">mean</span> of a share or a count, the <span className="const">pass rate</span> of the verdict; hover a cell for the rest
      </caption>
      <TableHeader>
        <TableRow>
          {columns.map((col) => {
            const active = column?.key === col.key;
            return (
              <TableHead
                key={col.key}
                className={col.numeric ? "num" : undefined}
                data-k={col.key}
                data-group={col.group ? "metrics" : undefined}
                aria-sort={active ? (dir === 1 ? "ascending" : "descending") : "none"}
              >
                <ColumnHead
                  defId={`SessionSummaryTable-def-${col.key}`}
                  name={col.name}
                  label={col.label}
                  title={col.title}
                  active={active}
                  ascending={active ? dir === 1 : nextDir(col) === "asc"}
                  onSort={() => sortBy(col)}
                />
              </TableHead>
            );
          })}
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.length === 0 ? (
          <TableRow>
            {/* The head stays, so the reader sees what would be there; the body says why it is not. */}
            <TableCell className="empty" colSpan={columns.length}>
              {NO_MATCH}
            </TableCell>
          </TableRow>
        ) : (
          rows.map((row, i) => (
            <TableRow
              key={row.key}
              data-key={row.key}
              /*
               * In key order a change of skill is a change of subject, so the first row of each
               * one opens a band — it is what makes this table read as *rolled up* rather than
               * as a shorter `SessionTable`, and the altitude is in the banding rather than in a
               * second border vocabulary. Under any other order "the row above" is whatever the
               * reader last clicked, so a band would be drawing a grouping the table is no
               * longer in: both the band and the repeat muting below switch off with the sort.
               * Drawn as an inset shadow because a collapsed table resolves a `border-top`
               * against the previous row's `border-bottom` and the earlier cell wins.
               */
              data-band={!column && i > 0 && row.skill !== rows[i - 1]?.skill ? "skill" : undefined}
            >
              {columns.map((col) => {
                const above = rows[i - 1];
                const repeat = !column && above != null && (col.repeat?.(row, above) ?? false);
                return (
                  <TableCell
                    key={col.key}
                    className={col.numeric ? "num" : undefined}
                    data-group={col.group ? "metrics" : undefined}
                    data-repeat={repeat ? "true" : undefined}
                  >
                    {col.render(row, ctx)}
                  </TableCell>
                );
              })}
            </TableRow>
          ))
        )}
      </TableBody>
    </Table>
  );
}
