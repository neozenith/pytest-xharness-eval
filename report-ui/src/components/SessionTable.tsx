import { useEffect, useMemo, useRef } from "react";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { ColumnHead } from "@/components/ColumnHead";
import { VerdictBadge } from "@/components/VerdictBadge";
import { caseShort, compact, coverageShare, coverageText, dec, fmt, modelShort, NONE, pct, secs, usd, usd3, when, windowLabel } from "@/lib/format";
import { NO_MATCH } from "@/lib/facets";
import { overviewWith, pushRoute, replaceRoute, useRoute, type SortDir } from "@/lib/route";
import type { Cell } from "@/lib/types";

type SortKey = keyof Cell | "coverage";

/** What a cell needs from the sweep it sits in, rather than from its own row. */
export interface RowContext {
  /** The model's short name, disambiguated over the whole sweep (`lib/format.ts`). */
  shortModel: (model: string) => string;
}

interface Column {
  key: SortKey;
  /**
   * The canonical field name. It is the tooltip's first line and the header button's
   * accessible name, so an abbreviated `label` never costs the reader (or a screen reader,
   * or the glossary) the name the JSON actually uses.
   */
  name: string;
  /** What the header prints: the shortest form that still reads at 11px. */
  label: string;
  title: string;
  numeric?: boolean;
  /** The first column of the metrics half; it draws the rule that divides the table in two. */
  group?: boolean;
  render: (c: Cell, ctx: RowContext) => React.ReactNode;
}

/** A missing value is a muted glyph, so a sparse column reads as sparse rather than as data. */
const nil = <span className="muted">{NONE}</span>;
const orNil = (v: unknown, text: string): React.ReactNode => (v == null ? nil : text);

/**
 * A token count abbreviated in the cell and exact on its `title`. Both figures come from the
 * same value, so the hover is the precision the column gave up, never a second quantity.
 */
const exact = (n: number | null | undefined): React.ReactNode => (n == null ? nil : <span title={fmt(n)}>{compact(n)}</span>);

/**
 * How far the harness's own cost figure sits from this plugin's estimate, as a signed share of
 * the estimate. The two agree to a fraction of a percent when the price table is right, so the
 * reader is looking for the row where they do not — which is a comparison, not two numbers.
 * Below 0.05% the sign is noise and the column says the two agree.
 */
const drift = (estimated: number, reported: number): string => {
  if (estimated === 0) return NONE;
  const share = (100 * (reported - estimated)) / estimated;
  return Math.abs(share) < 0.05 ? "=" : `${share > 0 ? "+" : "−"}${Math.abs(share).toFixed(1)}%`;
};

/**
 * `28 Aug 14:44`, not `28 Aug 2026, 14:44`. The year is the same on every row of a sweep and
 * already in the header's `generated` line, and the six glyphs it costs are the six the two
 * cost columns needed: at 1440px the `reported cost` values ended flush against the scroll
 * box's right edge, inside the 28px fade ramp, which reads `$2.5795` as a plausible `$2.579`.
 * The full timestamp stays on the cell's `title`, so nothing is actually lost.
 */
const AT = new Intl.DateTimeFormat("en-GB", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit", hourCycle: "h23" });
const atShort = (iso: string | null | undefined): string => {
  if (!iso) return NONE;
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : AT.format(d).replace(",", "");
};

/**
 * Two halves, left to right: who ran what (identity), then how it went (metrics). The order
 * inside each half is by how often a reader needs the column, because at eighteen columns the
 * table always scrolls and the only real decision is what earns the first screen.
 *
 * The columns carry their definitions as tooltips so a reader never has to guess what a
 * figure is. `accumulative_billed_tokens` (billed across turns) and `peak_context_tokens` (the
 * largest prompt one turn processed) are different quantities and are never shown as one.
 */
/**
 * THE COLUMN BUDGET: every metric that matters, on one screen, with no horizontal scroll.
 *
 * Eighteen columns did not fit 1440px, so the eight to the right of the fold were reachable
 * only by a scrollbar most readers never found — the table's own sorted-head auto-scroll
 * existed to paper over exactly that. Rather than cut the data, the width was taken back from
 * the ways it was *spelled*:
 *
 *   - `session_id` is gone. It identified a row without telling you anything about it, and the
 *     row already opens the session that prints it beside a `CopyId`. `data-sid` still carries
 *     it for the e2e matrix and for anyone reading the DOM.
 *   - `estimated_cost_usd` and `harness_reported_cost_usd` are one column: the estimate is the
 *     value, and the CLI's own figure is the muted *delta* from it. Two figures four decimals
 *     wide, printed side by side, were being compared by eye; the subtraction is the whole
 *     question and it is now done for the reader.
 *   - token counts are `compact` (`1.5M`, `29.4k`). Nine glyphs of thousands separators bought
 *     a precision nobody compares down a column; the exact figure is on the cell's `title`.
 *   - `model` drops the vendor prefix and `case` the `eval_` every case shares (`lib/format.ts`).
 *   - the heads print the shortest form that still reads, and carry the canonical field name in
 *     the tooltip and the accessible name, so nothing is renamed — only abbreviated.
 *
 * The order is unchanged: identity first, then metrics, each half ordered by how often a reader
 * needs the column. `accumulative_billed_tokens` (billed across turns) and `peak_context_tokens`
 * (the largest prompt one turn processed) are different quantities and are never shown as one.
 */
const COLUMNS: Column[] = [
  /*
   * The verdict leads. It is the one column a reader scans rather than reads — four of these
   * twenty-four cells are a fail — and flush at the card's left edge the pills make a rail: the
   * exceptions are found before the eye enters the table.
   */
  { key: "verdict", name: "verdict", label: "verdict", title: "the history line's verdict for this cell", render: (c) => <VerdictBadge verdict={c.verdict} /> },
  {
    key: "at",
    name: "at",
    label: "when",
    title: "when the cell started (history line); hover a cell for the year",
    render: (c) => <span title={when(c.at)}>{atShort(c.at)}</span>,
  },
  {
    key: "skill",
    name: "skill",
    label: "skill",
    title: "the skill under test (a sweep can span several)",
    render: (c) => (c.skill == null ? nil : <span title={c.skill}>{c.skill}</span>),
  },
  {
    key: "case",
    name: "case",
    label: "case",
    title: "the @evalcase function, without the eval_ prefix every case shares; hover a cell for the full name and its eval_*.py",
    render: (c) => <span title={`${c.case}${c.suite ? ` · ${c.suite}` : ""}`}>{caseShort(c.case)}</span>,
  },
  { key: "harness", name: "harness", label: "harness", title: "which CLI ran the cell", render: (c) => c.harness },
  {
    key: "model",
    name: "model",
    label: "model",
    title: "the model the harness was told to use, without its vendor prefix; hover a cell for the full id",
    render: (c, ctx) => <code title={c.model}>{ctx.shortModel(c.model)}</code>,
  },
  {
    key: "estimated_cost_usd",
    name: "estimated_cost_usd",
    label: "cost",
    title: "this plugin's estimate from rates_applied; the muted figure is how far the CLI's own harness_reported_cost_usd sits from it (Claude only)",
    numeric: true,
    group: true,
    render: (c) => {
      if (c.estimated_cost_usd == null) return nil;
      return (
        <span
          title={
            c.harness_reported_cost_usd == null ? undefined : `estimated ${usd(c.estimated_cost_usd)} · harness reported ${usd(c.harness_reported_cost_usd)}`
          }
        >
          {usd3(c.estimated_cost_usd)}
          {c.harness_reported_cost_usd == null ? null : <span className="muted qual tight">{drift(c.estimated_cost_usd, c.harness_reported_cost_usd)}</span>}
        </span>
      );
    },
  },
  {
    key: "accumulative_billed_tokens",
    name: "accumulative_billed_tokens (billed)",
    label: "billed",
    title: "every token of every call summed, the cached prefix once per turn that re-read it; a spend figure, not a context figure",
    numeric: true,
    render: (c) => exact(c.accumulative_billed_tokens),
  },
  {
    key: "context_window_pct",
    name: "peak_context_tokens",
    label: "peak ctx",
    title: "the largest prompt one turn processed, as a share of the model's context window; hover a cell for the window",
    numeric: true,
    render: (c) =>
      c.peak_context_tokens == null ? (
        nil
      ) : (
        <span title={`${fmt(c.peak_context_tokens)} of a ${windowLabel(c.context_window)} window · from a baseline_tokens of ${fmt(c.baseline_tokens)}`}>
          {compact(c.peak_context_tokens)}
          <span className="muted qual">· {pct(c.context_window_pct)}</span>
        </span>
      ),
  },
  { key: "turns", name: "turns", label: "turns", title: "model API calls", numeric: true, render: (c) => orNil(c.turns, fmt(c.turns)) },
  {
    key: "tool_calls",
    name: "tool_calls",
    label: "tools",
    title: "tool invocations issued",
    numeric: true,
    render: (c) => orNil(c.tool_calls, fmt(c.tool_calls)),
  },
  {
    key: "coverage",
    name: "skill_coverage",
    label: "coverage",
    title: "loaded/files · run/scripts, ignored files excluded",
    render: (c) => orNil(c.skill_coverage.files, coverageText(c)),
  },
  {
    key: "output_tokens_per_sec",
    name: "output_tokens_per_sec",
    label: "tok/s",
    title: "output tokens per second of API time",
    numeric: true,
    render: (c) => (c.output_tokens_per_sec == null ? nil : dec(c.output_tokens_per_sec, 2)),
  },
  {
    key: "wall_ms",
    name: "wall_ms",
    label: "wall",
    title: "wall clock around the subprocess",
    numeric: true,
    render: (c) => orNil(c.wall_ms, secs(c.wall_ms)),
  },
];

/**
 * The identity columns a constant value may collapse out of. Only these four: a *measure* that
 * happens to be equal on every row is a finding the reader wants to see repeated down the
 * column, while an identity that is equal on every row is the table's subject, not its data.
 */
const COLLAPSIBLE: readonly SortKey[] = ["skill", "case", "harness", "model"] as const;

/**
 * The identity columns whose value is the same on every visible row, and that value.
 *
 * Empty below two rows: one row is not "every row agrees", it is one row, and collapsing four
 * columns out of it would leave a caption where the data should be. A null (an ungraded skill)
 * never collapses — "they are all null" is not a fact worth a caption.
 */
function constantColumns(rows: Cell[], ctx: RowContext): { key: SortKey; name: string; text: string }[] {
  if (rows.length < 2) return [];
  const out: { key: SortKey; name: string; text: string }[] = [];
  for (const key of COLLAPSIBLE) {
    const first = rows[0]![key as keyof Cell];
    if (first == null || typeof first !== "string") continue;
    if (!rows.every((r) => r[key as keyof Cell] === first)) continue;
    const text = key === "case" ? caseShort(first) : key === "model" ? ctx.shortModel(first) : first;
    out.push({ key, name: key, text });
  }
  return out;
}

const sortValue = (c: Cell, key: SortKey): string | number | null => (key === "coverage" ? coverageShare(c) : (c[key] as string | number | null));

/**
 * One row per captured session; click a header to sort (recorded as `sort=`/`dir=`), a row to
 * open its SessionView.
 *
 * `shortModel` is derived once over the *unfiltered* sweep and passed down, so a model's printed
 * name is a property of the sweep and never changes under a filter. It defaults to the plain
 * rule for a caller that has no sweep to disambiguate against.
 */
export function SessionTable({ cells, shortModel = modelShort }: { cells: Cell[]; shortModel?: (model: string) => string }) {
  const route = useRoute();
  const routeSort = route.view === "overview" ? route.sort : null;
  const sortKey: SortKey = routeSort && COLUMNS.some((c) => c.key === routeSort.key) ? (routeSort.key as SortKey) : "at";
  const dir: 1 | -1 = routeSort ? (routeSort.dir === "asc" ? 1 : -1) : -1;
  const theme = route.theme;
  const ctx: RowContext = { shortModel };

  const rows = useMemo(
    () =>
      [...cells].sort((a, b) => {
        const x = sortValue(a, sortKey);
        const y = sortValue(b, sortKey);
        if (x == null && y == null) return 0;
        if (x == null) return 1;
        if (y == null) return -1;
        return (x < y ? -1 : x > y ? 1 : 0) * dir;
      }),
    [cells, sortKey, dir],
  );

  /*
   * Eighteen columns do not fit 1440px, so the column the table is sorted by is often one of
   * the eight off the right edge: a shared `?sort=coverage&dir=desc` link opened on an order
   * with nothing on screen to explain it — the accent wash that names the sorted head was
   * scrolled past the fade. The scroll box brings that head into view instead, horizontally
   * and only when it is actually out of view, so a sort a reader clicks (always on a visible
   * head) never moves the table under their hands.
   */
  const activeHead = useRef<HTMLTableCellElement>(null);
  useEffect(() => {
    const th = activeHead.current;
    const box = th?.closest<HTMLElement>("[data-slot='table-container']");
    if (!th || !box || box.scrollWidth <= box.clientWidth) return;
    const head = th.getBoundingClientRect();
    const view = box.getBoundingClientRect();
    // A column's width of lead-in, so the revealed head arrives with its neighbour beside it
    // rather than hard against the edge fade.
    const pad = 24;
    const past = head.right - (view.right - pad);
    const before = view.left + pad - head.left;
    const delta = past > 0 ? past : before > 0 ? -before : 0;
    if (delta === 0) return;
    const still = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    box.scrollTo({ left: box.scrollLeft + delta, behavior: still ? "auto" : "smooth" });
  }, [sortKey]);

  const constants = useMemo(() => constantColumns(rows, ctx), [rows, shortModel]);
  const columns = useMemo(() => {
    const collapsed = new Set(constants.map((c) => c.key));
    return COLUMNS.filter((col) => !collapsed.has(col.key));
  }, [constants]);

  /** What a click on this header would sort by — the direction the hint arrow promises. */
  const nextDir = (key: SortKey): SortDir => (key === sortKey ? (dir === 1 ? "desc" : "asc") : key === "at" ? "desc" : "asc");
  const sortBy = (key: SortKey) => replaceRoute(overviewWith(route, { sort: { key, dir: nextDir(key) } }));
  const open = (c: Cell) => pushRoute({ view: "session", sessionId: c.session_id, turn: null, turnView: null, axis: null, rec: null, line: null, theme });

  return (
    <Table id="SessionTable">
      {constants.length ? (
        /*
         * Announced before the table, which is what a `<caption>` is for — a screen reader reads
         * "every row: harness claude" and then the rows, instead of hearing the same cell twelve
         * times. `caption-side` is flipped to `top` for this one table in index.css.
         */
        <caption>
          every row:{" "}
          {constants.map((c, i) => (
            <span key={c.key}>
              {i ? " · " : ""}
              {c.name} <span className="const">{c.text}</span>
            </span>
          ))}
        </caption>
      ) : null}
      <TableHeader>
        <TableRow>
          {columns.map((col) => {
            const active = sortKey === col.key;
            return (
              <TableHead
                key={col.key}
                ref={active ? activeHead : undefined}
                className={col.numeric ? "num" : undefined}
                data-k={col.key}
                data-group={col.group ? "metrics" : undefined}
                aria-sort={active ? (dir === 1 ? "ascending" : "descending") : "none"}
              >
                <ColumnHead
                  defId={`SessionTable-def-${col.key}`}
                  name={col.name}
                  label={col.label}
                  title={col.title}
                  active={active}
                  ascending={active ? dir === 1 : nextDir(col.key) === "asc"}
                  onSort={() => sortBy(col.key)}
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
        ) : null}
        {rows.map((c) => (
          <TableRow
            key={c.session_id}
            className="SessionRow"
            data-sid={c.session_id}
            // A row is the only way into a SessionView, so it has to be reachable without a
            // mouse; the implicit `row` role stays, so the table still reads as a table.
            tabIndex={0}
            aria-label={`${c.case} · ${c.harness}/${c.model} · ${c.verdict ?? "no history"}`}
            // A click always targets a cell rather than the row, so the row cannot ask whether
            // the event is its own — it asks instead whether it started on a control of its
            // own. The chip's `stopPropagation` already covers today's one control; this is
            // the guard that keeps holding when a second one is added.
            onClick={(e) => {
              if (e.target instanceof Element && e.target.closest("button, a[href], input, [role='button']")) return;
              open(c);
            }}
            // A keydown, unlike a click, targets whatever holds focus — so when the target is
            // not the row itself, focus is on a child and the key belongs to the child. Without
            // this the row matched Enter/Space on a keydown bubbling up from the copy chip,
            // called `preventDefault()` (killing the click the browser was about to synthesise
            // on that button) and navigated: the chip promised "Copy <id>" and opened a
            // SessionView with the clipboard untouched.
            onKeyDown={(e) => {
              if (e.target !== e.currentTarget) return;
              if (e.key !== "Enter" && e.key !== " ") return;
              e.preventDefault();
              open(c);
            }}
          >
            {columns.map((col) => (
              <TableCell key={col.key} className={col.numeric ? "num" : undefined} data-k={col.key} data-group={col.group ? "metrics" : undefined}>
                {col.render(c, ctx)}
              </TableCell>
            ))}
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
