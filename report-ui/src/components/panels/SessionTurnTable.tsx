import { Fragment, type ReactNode } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { CopyId } from "@/components/CopyId";
import { El } from "@/components/El";
import { fmt, pct, short } from "@/lib/format";
import { sessionHash } from "@/lib/route";
import type { Call, Cell, RunResult } from "@/lib/types";
import { cn } from "@/lib/utils";
import { clock, ms, ranges, turnId } from "./helpers";

import type { RecordView, TurnView } from "./helpers";
export type { RecordView, TurnView };

/** Local alias kept for the column renderer; the shape is `ResultIn` in @/lib/types. */
interface ResultIn {
  tool?: string;
  chars?: number;
  content?: string;
}

const COLUMNS = 16;

interface Props {
  result: RunResult;
  cell: Cell;
  view: TurnView;
  onViewChange: (v: TurnView) => void;
  /** The turn whose details row is open from the `turn=` hash param, or null. */
  openTurn: number | null;
  onOpenTurn: (n: number | null) => void;
  recordView: RecordView;
  onRecordViewChange?: (v: RecordView) => void;
  /** Renders a turn's TurnRawRecords; wired by the integrator so this file needs no records import. */
  renderTurnRecords?: (call: Call) => ReactNode;
  /** Extra toolbar content, where the integrator places RecordViewToggle. */
  toolbarExtra?: ReactNode;
}

/** ViewToggle: summary hides every details row, detailed shows them all. */
export function ViewToggle({ view, onChange }: { view: TurnView; onChange: (v: TurnView) => void }) {
  return (
    <ToggleGroup
      id="ViewToggle"
      type="single"
      variant="outline"
      size="sm"
      value={view}
      onValueChange={(v) => v && onChange(v as TurnView)}
      aria-label="turn table view"
    >
      <ToggleGroupItem value="summary" data-view="summary">
        Summary view
      </ToggleGroupItem>
      <ToggleGroupItem value="detailed" data-view="detailed">
        Detailed view
      </ToggleGroupItem>
    </ToggleGroup>
  );
}

/**
 * One row per model API call (a SessionTurn), with the ledger's per-call columns; clicking a
 * row toggles its details row (the turn's TurnRawRecords) and records `turn=<n>` in the hash.
 * In the detailed view every details row is open.
 */
export function SessionTurnTable({ result, cell, view, onViewChange, openTurn, onOpenTurn, renderTurnRecords, toolbarExtra }: Props) {
  const calls = result.calls ?? [];
  const toggle = (n: number) => {
    const next = openTurn === n ? null : n;
    onOpenTurn(next);
    history.replaceState(null, "", `${sessionHash(cell.session_id, next)}${view ? `&view=${view}` : ""}`);
  };
  return (
    <Card id="SessionTurnTablePanel" data-el="SessionTurnTable">
      <CardHeader>
        <CardTitle>
          Turns
          <El name="SessionTurnTable" />
        </CardTitle>
        <div className="flex flex-wrap items-center gap-3">
          <span className="text-muted-foreground text-sm">
            One row per model API call (a SessionTurn). A turn's records are its own blocks, the results of the tools it issued, and the harness records written
            before the next turn began.
          </span>
          <span className="flex-1" />
          <ViewToggle view={view} onChange={onViewChange} />
          {toolbarExtra}
        </div>
      </CardHeader>
      <CardContent>
        <div className="overflow-x-auto">
          <Table id="SessionTurnTable" className="text-sm">
            <TableHeader>
              <TableRow>
                <TableHead>SessionTurnId</TableHead>
                <TableHead>time</TableHead>
                <TableHead>log lines</TableHead>
                <TableHead>tools issued</TableHead>
                <TableHead className="text-right">results in</TableHead>
                <TableHead className="text-right">cache_read</TableHead>
                <TableHead className="text-right">cache_write</TableHead>
                <TableHead className="text-right">1h</TableHead>
                <TableHead className="text-right">input</TableHead>
                <TableHead className="text-right" title="context_tokens: the prompt this call processed (input + cache read + cache write)">
                  context
                </TableHead>
                <TableHead className="text-right">ctx %</TableHead>
                <TableHead className="text-right">output</TableHead>
                <TableHead className="text-right">thinking</TableHead>
                <TableHead className="text-right">latency</TableHead>
                <TableHead className="text-right">tok/s</TableHead>
                <TableHead>stop</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {!calls.length ? (
                <TableRow>
                  <TableCell colSpan={COLUMNS} className="text-warn">
                    This result has no per-turn ledger (it predates ADR 0019). Replay the captured directory to build one.
                  </TableCell>
                </TableRow>
              ) : (
                calls.map((k) => {
                  const open = view === "detailed" || openTurn === k.n;
                  const resultsIn: ResultIn[] = k.results_in ?? [];
                  return (
                    <Fragment key={k.n}>
                      <TableRow
                        className={cn("SessionTurnRow cursor-pointer", open && "bg-muted/60")}
                        data-n={k.n}
                        data-el="SessionTurnRow"
                        onClick={() => toggle(k.n)}
                      >
                        <TableCell className="whitespace-nowrap">
                          <CopyId id={turnId(result.session_id, k.n)} label={`${short(result.session_id)}/t${k.n}`} />
                        </TableCell>
                        <TableCell className="whitespace-nowrap tabular-nums">{clock(k.at)}</TableCell>
                        <TableCell>
                          <code className="font-mono text-xs">{ranges(k.records ?? [])}</code>
                        </TableCell>
                        <TableCell>
                          {k.tools?.length ? (
                            k.tools.map((t, i) => (
                              <code key={i} className="bg-muted mr-1 rounded px-1 font-mono text-xs">
                                {t.name}
                              </code>
                            ))
                          ) : (
                            <span className="text-muted-foreground">(final reply)</span>
                          )}
                        </TableCell>
                        <TableCell className="text-right whitespace-nowrap tabular-nums">
                          {resultsIn.length} · {fmt(resultsIn.reduce((s, x) => s + (x.chars ?? 0), 0))} ch
                        </TableCell>
                        <TableCell className="text-right tabular-nums">{fmt(k.usage.cache_read_tokens)}</TableCell>
                        <TableCell className="text-right tabular-nums">{fmt(k.usage.cache_write_tokens)}</TableCell>
                        <TableCell className="text-right tabular-nums">{fmt(k.usage.cache_write_1h_tokens)}</TableCell>
                        <TableCell className="text-right tabular-nums">{fmt(k.usage.input_tokens)}</TableCell>
                        <TableCell className="text-right font-semibold tabular-nums">{fmt(k.context_tokens)}</TableCell>
                        <TableCell className="text-right tabular-nums">{pct(k.context_pct)}</TableCell>
                        <TableCell className="text-right tabular-nums">{fmt(k.usage.output_tokens)}</TableCell>
                        <TableCell className="text-right tabular-nums">{fmt(k.usage.reasoning_tokens)}</TableCell>
                        <TableCell className="text-right whitespace-nowrap tabular-nums">{ms(k.latency_ms)}</TableCell>
                        <TableCell className="text-right tabular-nums">{fmt(k.output_tokens_per_sec)}</TableCell>
                        <TableCell>{k.stop_reason ?? "–"}</TableCell>
                      </TableRow>
                      {open ? (
                        <TableRow className="detail-row hover:bg-transparent" data-n={k.n}>
                          <TableCell colSpan={COLUMNS} className="p-2">
                            {renderTurnRecords ? (
                              renderTurnRecords(k)
                            ) : (
                              <div id={turnId(result.session_id, k.n)} className="text-muted-foreground text-sm">
                                no record renderer wired
                              </div>
                            )}
                          </TableCell>
                        </TableRow>
                      ) : null}
                    </Fragment>
                  );
                })
              )}
            </TableBody>
          </Table>
        </div>
      </CardContent>
    </Card>
  );
}
