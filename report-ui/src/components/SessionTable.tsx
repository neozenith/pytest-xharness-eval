import { useEffect, useMemo, useRef } from "react";
import { ArrowDown, ArrowUp } from "lucide-react";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { CopyId } from "@/components/CopyId";
import { VerdictBadge } from "@/components/VerdictBadge";
import { coverageText, fmt, NONE, pct, secs, usd, when, windowLabel } from "@/lib/format";
import { pushRoute, replaceRoute, useRoute, type SortDir } from "@/lib/route";
import type { Cell } from "@/lib/types";

type SortKey = keyof Cell | "coverage";

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
  render: (c: Cell) => React.ReactNode;
}

/** A missing value is a muted glyph, so a sparse column reads as sparse rather than as data. */
const nil = <span className="muted">{NONE}</span>;
const orNil = (v: unknown, text: string): React.ReactNode => (v == null ? nil : text);

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
 * Two decimals, always. `fmt` drops a trailing zero, so `86.8` and `32.8` sat one glyph right
 * of the other twenty-two values and the decimal points walked — which is the whole of what a
 * right-aligned tabular-numeral column buys you.
 */
const dec2 = (n: number): string => n.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

/**
 * Two halves, left to right: who ran what (identity), then how it went (metrics). The order
 * inside each half is by how often a reader needs the column, because at eighteen columns the
 * table always scrolls and the only real decision is what earns the first screen.
 *
 * The columns carry their definitions as tooltips so a reader never has to guess what a
 * figure is. `accumulative_billed_tokens` (billed across turns) and `peak_context_tokens` (the
 * largest prompt one turn processed) are different quantities and are never shown as one.
 */
const COLUMNS: Column[] = [
  /*
   * The verdict leads. It is the one column a reader scans rather than reads — four of these
   * twenty-four cells are a fail — and it was sitting second, behind thirteen characters of
   * hex that identify a row without telling you anything about it. Flush at the card's left
   * edge the pills make a rail: the exceptions are found before the eye enters the table.
   */
  { key: "verdict", name: "verdict", label: "verdict", title: "the history line's verdict for this cell", render: (c) => <VerdictBadge verdict={c.verdict} /> },
  {
    key: "session_id",
    name: "session_id",
    label: "session",
    // Eight characters is not enough: four codex sessions in this sweep share `01a046ae`, so
    // the column showed one id four times. Thirteen reaches into the random half of a UUID.
    title: "the harness's session id; click to copy the whole of it",
    render: (c) => <CopyId id={c.session_id} label={c.session_id.slice(0, 13)} />,
  },
  {
    key: "at",
    name: "at",
    label: "when",
    title: "when the cell started (history line); hover a cell for the year",
    render: (c) => <span title={when(c.at)}>{atShort(c.at)}</span>,
  },
  { key: "skill", name: "skill", label: "skill", title: "the skill under test (a sweep can span several)", render: (c) => orNil(c.skill, c.skill ?? "") },
  {
    key: "case",
    name: "case",
    // `suite` used to sit beside this as its own column, printing the same string with `.py`
    // on the end — two hundred pixels of the first screen spent saying `case` twice. The file
    // it lives in is the cell's title instead, and the width went to the cost columns.
    label: "case",
    title: "the @evalcase function; hover a cell for the eval_*.py that defines it",
    // Every case in a sweep is named `eval_*`, so on twenty-four rows those five glyphs are a
    // column of noise the eye has to step over to reach the word that differs. The prefix is
    // still printed — it is part of the function's name, and of what you copy — but muted, so
    // the row reads as `discovery_refresh` at a glance and as `eval_discovery_refresh` when
    // you look at it.
    render: (c) => {
      const shared = c.case.startsWith("eval_");
      return (
        <span title={c.suite ?? undefined}>
          {shared ? <span className="muted">eval_</span> : null}
          {shared ? c.case.slice(5) : c.case}
        </span>
      );
    },
  },
  { key: "harness", name: "harness", label: "harness", title: "which CLI ran the cell", render: (c) => c.harness },
  { key: "model", name: "model", label: "model", title: "the model the harness was told to use", render: (c) => <code>{c.model}</code> },
  {
    key: "estimated_cost_usd",
    name: "estimated_cost_usd",
    label: "est. cost",
    title: "this plugin's estimate from rates_applied",
    numeric: true,
    group: true,
    render: (c) => orNil(c.estimated_cost_usd, usd(c.estimated_cost_usd)),
  },
  {
    key: "harness_reported_cost_usd",
    name: "harness_reported_cost_usd",
    label: "reported cost",
    title: "what the CLI itself said the run cost (Claude only)",
    numeric: true,
    render: (c) => orNil(c.harness_reported_cost_usd, usd(c.harness_reported_cost_usd)),
  },
  {
    key: "accumulative_billed_tokens",
    name: "accumulative_billed_tokens (billed)",
    label: "billed tokens",
    title: "every token of every call summed, the cached prefix once per turn that re-read it; a spend figure, not a context figure",
    numeric: true,
    render: (c) => orNil(c.accumulative_billed_tokens, fmt(c.accumulative_billed_tokens)),
  },
  {
    key: "baseline_tokens",
    name: "baseline_tokens",
    label: "baseline",
    title: "the prompt of the first call, before the agent acted",
    numeric: true,
    render: (c) => orNil(c.baseline_tokens, fmt(c.baseline_tokens)),
  },
  {
    key: "context_window_pct",
    name: "peak_context_tokens",
    label: "peak context",
    title: "the largest prompt one turn processed, as a share of the model's context window",
    numeric: true,
    render: (c) =>
      c.peak_context_tokens == null ? (
        nil
      ) : (
        <>
          {fmt(c.peak_context_tokens)}
          <span className="muted">
            {" "}
            · {pct(c.context_window_pct)} of {windowLabel(c.context_window)}
          </span>
        </>
      ),
  },
  { key: "turns", name: "turns", label: "turns", title: "model API calls", numeric: true, render: (c) => orNil(c.turns, fmt(c.turns)) },
  {
    key: "tool_calls",
    name: "tool_calls",
    label: "tool calls",
    title: "tool invocations issued",
    numeric: true,
    render: (c) => orNil(c.tool_calls, fmt(c.tool_calls)),
  },
  {
    key: "coverage",
    name: "skill_coverage",
    label: "skill coverage",
    title: "loaded/files · run/scripts, ignored files excluded",
    render: (c) => orNil(c.skill_coverage.files, coverageText(c)),
  },
  {
    key: "output_tokens_per_sec",
    name: "output_tokens_per_sec",
    label: "tok/s",
    title: "output tokens per second of API time",
    numeric: true,
    render: (c) => (c.output_tokens_per_sec == null ? nil : dec2(c.output_tokens_per_sec)),
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
 * The share the `skill coverage` cell prints, not the raw `loaded` count behind it. A sweep
 * spanning two skills has two catalogue sizes (discovery has 5 files, mermaidjs-diagrams 18),
 * so sorting on the count inverted the column's own meaning: `6/18` (33%) ranked above `5/5`
 * (100%). This is the same normalisation the neighbouring `peak context` column makes by
 * sorting on `context_window_pct` rather than `peak_context_tokens`. A cell with no catalogue
 * stays null, so it keeps going last in both directions.
 */
const coverageShare = (c: Cell): number | null => {
  const { files, loaded } = c.skill_coverage;
  return files != null && files > 0 ? (loaded ?? 0) / files : null;
};

const sortValue = (c: Cell, key: SortKey): string | number | null => (key === "coverage" ? coverageShare(c) : (c[key] as string | number | null));

/** One row per captured session; click a header to sort (recorded as `sort=`/`dir=` in the hash), a row to open its SessionView. */
export function SessionTable({ cells }: { cells: Cell[] }) {
  const route = useRoute();
  const routeSort = route.view === "overview" ? route.sort : null;
  const sortKey: SortKey = routeSort && COLUMNS.some((c) => c.key === routeSort.key) ? (routeSort.key as SortKey) : "at";
  const dir: 1 | -1 = routeSort ? (routeSort.dir === "asc" ? 1 : -1) : -1;
  const theme = route.theme;

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

  /** What a click on this header would sort by — the direction the hint arrow promises. */
  const nextDir = (key: SortKey): SortDir => (key === sortKey ? (dir === 1 ? "desc" : "asc") : key === "at" ? "desc" : "asc");
  const sortBy = (key: SortKey) => replaceRoute({ view: "overview", sort: { key, dir: nextDir(key) }, theme });
  const open = (c: Cell) => pushRoute({ view: "session", sessionId: c.session_id, turn: null, turnView: null, axis: null, rec: null, line: null, theme });

  return (
    <Table id="SessionTable">
      <TableHeader>
        <TableRow>
          {COLUMNS.map((col) => {
            const active = sortKey === col.key;
            // The arrow is always in the DOM: an active column that grew one on click shifted
            // every column to its right, and a sortable column that showed nothing until you
            // hovered it never said it was sortable. Inactive arrows point where a click goes.
            const Arrow = (active ? dir === 1 : nextDir(col.key) === "asc") ? ArrowUp : ArrowDown;
            return (
              <TableHead
                key={col.key}
                ref={active ? activeHead : undefined}
                className={col.numeric ? "num" : undefined}
                data-k={col.key}
                data-group={col.group ? "metrics" : undefined}
                aria-sort={active ? (dir === 1 ? "ascending" : "descending") : "none"}
              >
                <Tooltip>
                  <TooltipTrigger asChild>
                    {/*
                     * The accessible name keeps the printed label *and* the canonical field
                     * name (WCAG 2.5.3: what you can say has to be what you can see), so an
                     * abbreviated head still answers to `estimated_cost_usd`.
                     */}
                    <button type="button" aria-label={col.label === col.name ? undefined : `${col.label} — ${col.name}`} onClick={() => sortBy(col.key)}>
                      {col.label}
                      <Arrow className="sort-ico" data-active={active || undefined} size={12} aria-hidden />
                    </button>
                  </TooltipTrigger>
                  <TooltipContent>
                    <span className="mono">{col.name}</span> — {col.title}
                  </TooltipContent>
                </Tooltip>
              </TableHead>
            );
          })}
        </TableRow>
      </TableHeader>
      <TableBody>
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
            {COLUMNS.map((col) => (
              <TableCell key={col.key} className={col.numeric ? "num" : undefined} data-group={col.group ? "metrics" : undefined}>
                {col.render(c)}
              </TableCell>
            ))}
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
