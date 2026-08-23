import { useMemo, useState } from "react";
import { ArrowDown, ArrowUp } from "lucide-react";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { CopyId } from "@/components/CopyId";
import { VerdictBadge } from "@/components/VerdictBadge";
import { coverageText, fmt, pct, secs, short, usd, when, windowLabel } from "@/lib/format";
import { sessionHash } from "@/lib/route";
import type { Cell } from "@/lib/types";
import { cn } from "@/lib/utils";

type SortKey = keyof Cell | "coverage";

interface Column {
  key: SortKey;
  label: string;
  title: string;
  numeric?: boolean;
  render: (c: Cell) => React.ReactNode;
}

/**
 * The columns carry their definitions as tooltips so a reader never has to guess what a
 * figure is. `accumulative_billed_tokens` (billed across turns) and `peak context` (the largest prompt
 * one turn processed) are different quantities and are never shown as one.
 */
const COLUMNS: Column[] = [
  {
    key: "session_id",
    label: "SessionId",
    title: "the harness's session id; click to copy",
    render: (c) => <CopyId id={c.session_id} label={short(c.session_id)} />,
  },
  { key: "verdict", label: "verdict", title: "the history line's verdict for this cell", render: (c) => <VerdictBadge verdict={c.verdict} /> },
  { key: "at", label: "when", title: "when the cell started (history line)", render: (c) => when(c.at) },
  {
    key: "suite",
    label: "suite",
    title: "the eval_*.py that defines the case",
    render: (c) => <code className="font-mono text-xs">{c.suite ? c.suite.split("/").pop() : "–"}</code>,
  },
  { key: "case", label: "case", title: "the @evalcase function", render: (c) => c.case },
  { key: "harness", label: "harness", title: "which CLI ran the cell", render: (c) => c.harness },
  { key: "model", label: "model", title: "the model the harness was told to use", render: (c) => <code className="font-mono text-xs">{c.model}</code> },
  {
    key: "estimated_cost_usd",
    label: "estimated_cost_usd",
    title: "this plugin's estimate from rates_applied",
    numeric: true,
    render: (c) => usd(c.estimated_cost_usd),
  },
  {
    key: "harness_reported_cost_usd",
    label: "harness_reported_cost_usd",
    title: "what the CLI itself said the run cost (Claude only)",
    numeric: true,
    render: (c) => usd(c.harness_reported_cost_usd),
  },
  {
    key: "baseline_tokens",
    label: "baseline_tokens",
    title: "the prompt of the first call, before the agent acted",
    numeric: true,
    render: (c) => fmt(c.baseline_tokens),
  },
  {
    key: "accumulative_billed_tokens",
    label: "accumulative_billed_tokens (billed)",
    title: "every token of every call summed, the cached prefix once per turn that re-read it; a spend figure, not a context figure",
    numeric: true,
    render: (c) => fmt(c.accumulative_billed_tokens),
  },
  {
    key: "context_window_pct",
    label: "peak context",
    title: "peak_context_tokens: the largest prompt one turn processed, as a share of the model's context window",
    numeric: true,
    render: (c) => (
      <>
        {fmt(c.peak_context_tokens)}
        <span className="text-muted-foreground">
          {" "}
          · {pct(c.context_window_pct)} of {windowLabel(c.context_window)}
        </span>
      </>
    ),
  },
  { key: "turns", label: "turns", title: "model API calls", numeric: true, render: (c) => fmt(c.turns) },
  { key: "tool_calls", label: "tool_calls", title: "tool invocations issued", numeric: true, render: (c) => fmt(c.tool_calls) },
  { key: "coverage", label: "skill coverage", title: "loaded/files · run/scripts, ignored files excluded", render: (c) => coverageText(c) },
  { key: "output_tokens_per_sec", label: "tok/s", title: "output tokens per second of API time", numeric: true, render: (c) => fmt(c.output_tokens_per_sec) },
  { key: "wall_ms", label: "wall", title: "wall clock around the subprocess", numeric: true, render: (c) => secs(c.wall_ms) },
];

const sortValue = (c: Cell, key: SortKey): string | number | null =>
  key === "coverage" ? (c.skill_coverage.loaded ?? null) : (c[key] as string | number | null);

/** One row per captured session; click a header to sort, a row to open its SessionView. */
export function SessionTable({ cells }: { cells: Cell[] }) {
  const [sortKey, setSortKey] = useState<SortKey>("at");
  const [dir, setDir] = useState<1 | -1>(-1);

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

  const sortBy = (key: SortKey) => {
    if (key === sortKey) setDir((d) => (d === 1 ? -1 : 1));
    else {
      setSortKey(key);
      setDir(key === "at" ? -1 : 1);
    }
  };

  return (
    <div className="overflow-x-auto">
      <Table id="SessionTable" className="text-sm">
        <TableHeader>
          <TableRow>
            {COLUMNS.map((col) => (
              <TableHead key={col.key} className={cn("whitespace-nowrap", col.numeric && "text-right")} data-k={col.key}>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <button type="button" className="inline-flex items-center gap-1 font-medium hover:underline" onClick={() => sortBy(col.key)}>
                      {col.label}
                      {sortKey === col.key ? dir === 1 ? <ArrowUp className="size-3" /> : <ArrowDown className="size-3" /> : null}
                    </button>
                  </TooltipTrigger>
                  <TooltipContent className="max-w-xs">{col.title}</TooltipContent>
                </Tooltip>
              </TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((c) => (
            <TableRow
              key={c.session_id}
              className="SessionRow cursor-pointer"
              data-sid={c.session_id}
              onClick={() => {
                location.hash = sessionHash(c.session_id);
              }}
            >
              {COLUMNS.map((col) => (
                <TableCell key={col.key} className={cn("whitespace-nowrap", col.numeric && "text-right tabular-nums")}>
                  {col.render(c)}
                </TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
