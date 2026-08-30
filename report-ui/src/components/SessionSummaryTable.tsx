/**
 * The aggregate view of exactly the runs `SessionTable` lists (glossary: `SessionSummaryTable`,
 * ADR 0042): one row per skill × case × harness × model, which is one line of the
 * `TokenAccumulationChart` above it, so the two read as a pair.
 *
 * It takes the cells it is given and knows nothing about filters; its arithmetic is in
 * `lib/summary.ts`. It sorts on its OWN param pair (`ssort`/`sdir`), because the reader ranks
 * groups by mean cost while ranking sessions by when they ran, and a shared pair would have made
 * every click here silently reorder the table below. Unsorted, the rows come out in the fixed
 * `skill|case|harness|model` key order — the only order in which the banding and the repeat
 * muting below tell the truth, which is why both switch off the moment a column is sorted.
 *
 * Every aggregate is named `mean <field>` in full (ADR 0021) in its tooltip and its accessible
 * name — but not in its printed label. Eight heads reading `mean …` spent 264px saying the same
 * word eight times, in the table that most needed the width; the caption says it once, for every
 * measure column at once, and each head still answers to `mean output_tokens_per_sec` when a
 * reader or a screen reader asks it. It is the same trade as dropping the `eval_` prefix: the
 * glyphs every row (or every head) shares carry no signal, and the full name never leaves.
 */
import { useMemo } from "react";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { ColumnHead } from "@/components/ColumnHead";
import { caseShort, compact, dec, fmt, modelShort, NONE, pct, secs, usd, windowLabel } from "@/lib/format";
import { NO_MATCH } from "@/lib/facets";
import { overviewWith, replaceRoute, useRoute, type SortDir } from "@/lib/route";
import { summaryRows, type SummaryRow } from "@/lib/summary";
import type { RowContext } from "@/components/SessionTable";
import type { Cell } from "@/lib/types";

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

/** A token count abbreviated in the cell and exact on its `title`, exactly as `SessionTable` prints one. */
const exact = (n: number | null | undefined): React.ReactNode => (n == null ? nil : <span title={fmt(Math.round(n))}>{compact(Math.round(n))}</span>);

const COLUMNS: Column[] = [
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
    render: (r, ctx) => <code title={r.model}>{ctx.shortModel(r.model)}</code>,
  },
  {
    key: "runs",
    name: "runs",
    label: "runs",
    title: "captured sessions in this group; every mean below is over these runs",
    numeric: true,
    group: true,
    sortValue: (r) => r.runs,
    render: (r) => fmt(r.runs),
  },
  {
    key: "pass",
    name: "verdict pass rate",
    label: "pass rate",
    title: "runs whose history verdict is pass, over the runs that carry a verdict",
    /*
     * This is the aggregate's verdict, and it is the one cell in the table a reader scans
     * rather than reads — so it answers the `VerdictBadge` rail one table below in the same
     * key: a group that did not pass clean takes `bad` ink and 600 weight, a clean one stays
     * quiet. Grey `0/1` among twelve grey `1/1`s was the single worst thing on this page: the
     * only failing group in the sweep was indistinguishable from its neighbours.
     *
     * The fraction is the value and the percentage is derived from it, so only the fraction
     * is coloured and the percentage stays a muted qualifier — the same value/qualifier split
     * the `peak context` cells make either side of their `·`.
     */
    // Ranked by the share, not by the numerator: `1/1` outranks `1/2`, and an ungraded group
    // has no rate at all rather than a rate of zero.
    sortValue: (r) => (r.graded === 0 ? null : r.pass / r.graded),
    render: (r) => {
      if (r.graded === 0) return nil;
      const ungraded = r.runs - r.graded;
      const clean = r.pass === r.graded;
      return (
        <>
          <span className={clean ? undefined : "bad strong"}>
            {r.pass}/{r.graded}
          </span>
          <span className="muted"> · {pct((100 * r.pass) / r.graded)}</span>
          {ungraded ? <span className="muted"> · {ungraded} no history</span> : null}
        </>
      );
    },
  },
  {
    key: "cost",
    name: "mean estimated_cost_usd",
    label: "cost",
    title: "arithmetic mean of estimated_cost_usd over the runs that carry one",
    numeric: true,
    sortValue: (r) => r.mean_estimated_cost_usd,
    render: (r) => orNil(r.mean_estimated_cost_usd, usd(r.mean_estimated_cost_usd)),
  },
  {
    key: "billed",
    name: "mean accumulative_billed_tokens",
    label: "billed",
    title: "arithmetic mean of the cross-turn billed sum; a spend figure, not a context figure",
    numeric: true,
    sortValue: (r) => r.mean_accumulative_billed_tokens,
    render: (r) => exact(r.mean_accumulative_billed_tokens),
  },
  {
    key: "peak",
    name: "mean peak_context_tokens",
    label: "peak ctx",
    title: "arithmetic mean of the largest prompt one turn processed, with the mean share of the window; hover a cell for the window",
    numeric: true,
    // Ranked by the share, like `SessionTable`'s own peak-context column: a sweep spanning two
    // window sizes ranks a 6% prompt above a 34% one on raw tokens alone.
    sortValue: (r) => r.mean_context_window_pct,
    render: (r) =>
      r.mean_peak_context_tokens == null ? (
        nil
      ) : (
        <span title={`${fmt(Math.round(r.mean_peak_context_tokens))} of a ${windowLabel(r.context_window)} window`}>
          {compact(Math.round(r.mean_peak_context_tokens))}
          <span className="muted qual">· {pct(r.mean_context_window_pct)}</span>
        </span>
      ),
  },
  {
    key: "turns",
    name: "mean turns",
    label: "turns",
    title: "arithmetic mean of model API calls",
    numeric: true,
    sortValue: (r) => r.mean_turns,
    render: (r) => (r.mean_turns == null ? nil : dec(r.mean_turns, 1)),
  },
  {
    key: "tools",
    name: "mean tool_calls",
    label: "tools",
    title: "arithmetic mean of tool invocations issued",
    numeric: true,
    sortValue: (r) => r.mean_tool_calls,
    render: (r) => (r.mean_tool_calls == null ? nil : dec(r.mean_tool_calls, 1)),
  },
  {
    key: "coverage",
    name: "mean skill_coverage loaded share",
    label: "coverage",
    title: "arithmetic mean of loaded/files per run, ignored files excluded",
    numeric: true,
    sortValue: (r) => r.mean_skill_coverage_share,
    render: (r) => (r.mean_skill_coverage_share == null ? nil : pct(100 * r.mean_skill_coverage_share)),
  },
  {
    key: "tps",
    name: "mean output_tokens_per_sec",
    label: "tok/s",
    title: "arithmetic mean of output tokens per second of API time",
    numeric: true,
    sortValue: (r) => r.mean_output_tokens_per_sec,
    render: (r) => (r.mean_output_tokens_per_sec == null ? nil : dec(r.mean_output_tokens_per_sec, 2)),
  },
  {
    key: "wall",
    name: "mean wall_ms",
    label: "wall",
    title: "arithmetic mean of wall clock around the subprocess",
    numeric: true,
    sortValue: (r) => r.mean_wall_ms,
    render: (r) => orNil(r.mean_wall_ms, secs(r.mean_wall_ms)),
  },
];

/**
 * One row per skill × case × harness × model group of the cells it is given, in the fixed key
 * order until a head is clicked.
 */
export function SessionSummaryTable({ cells, shortModel = modelShort }: { cells: Cell[]; shortModel?: (model: string) => string }) {
  const route = useRoute();
  const routeSort = route.view === "overview" ? route.summarySort : null;
  const column = routeSort ? (COLUMNS.find((c) => c.key === routeSort.key) ?? null) : null;
  const dir: 1 | -1 = routeSort?.dir === "desc" ? -1 : 1;
  const ctx: RowContext = { shortModel };

  const rows = useMemo(() => {
    const grouped = summaryRows(cells);
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
  }, [cells, column, dir]);

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
        every measure is the <span className="const">arithmetic mean</span> over the runs in its group that carry that field
      </caption>
      <TableHeader>
        <TableRow>
          {COLUMNS.map((col) => {
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
            <TableCell className="empty" colSpan={COLUMNS.length}>
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
              {COLUMNS.map((col) => {
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
