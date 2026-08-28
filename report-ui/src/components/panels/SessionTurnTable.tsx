/**
 * One row per model API call (a SessionTurn), with the ledger's per-call columns; clicking a
 * row toggles its details row (the turn's TurnRawRecords) and records `turn=<n>` in the URL.
 * In the detailed view every details row is open.
 *
 * The two harnesses keep different session-log schemas, so each gets its own table:
 * `SessionTurnTableClaude` carries Claude's explicit cache-write billing tiers
 * (`cache_write`, `1h`); `SessionTurnTableCodex` drops them — Codex's caching is implicit
 * and those tiers are never populated — and names its read tier in Codex's own vocabulary
 * (`cached input`). `SessionTurnTable` dispatches on `result.harness`.
 */
import { Fragment, useMemo, type ReactNode } from "react";
import { Text, XStack } from "tamagui";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { CopyId } from "@/components/CopyId";
import { El } from "@/components/El";
import { fmt, pct, short } from "@/lib/format";
import type { Call, RunResult, Subagent } from "@/lib/types";
import { clock, ms, ranges, turnId } from "./helpers";

import type { RecordView, TurnView } from "./helpers";
export type { RecordView, TurnView };

/** Local alias kept for the column renderer; the shape is `ResultIn` in @/lib/types. */
interface ResultIn {
  tool?: string;
  chars?: number;
  content?: string;
}

/** One ledger column: header text, numeric alignment, and how a call renders into it. */
interface TurnColumn {
  key: string;
  head: string;
  num?: boolean;
  title?: string;
  render: (k: Call, result: RunResult) => ReactNode;
}

const CORE_LEFT: TurnColumn[] = [
  {
    key: "id",
    head: "SessionTurnId",
    render: (k, result) => <CopyId id={turnId(result.session_id, k.n)} label={`${short(result.session_id)}/t${k.n}`} />,
  },
  { key: "time", head: "time", render: (k) => <span style={{ fontVariantNumeric: "tabular-nums" }}>{clock(k.at)}</span> },
  { key: "lines", head: "log lines", render: (k) => <code>{ranges(k.records ?? [])}</code> },
  {
    key: "tools",
    head: "tools issued",
    render: (k) =>
      k.tools?.length ? (
        k.tools.map((t, i) => (
          <code key={i} className="code-chip">
            {t.name}
          </code>
        ))
      ) : (
        <span className="muted">(final reply)</span>
      ),
  },
  {
    key: "results_in",
    head: "results in",
    num: true,
    render: (k) => {
      const resultsIn: ResultIn[] = k.results_in ?? [];
      return (
        <>
          {resultsIn.length} · {fmt(resultsIn.reduce((s, x) => s + (x.chars ?? 0), 0))} ch
        </>
      );
    },
  },
];

const CORE_RIGHT: TurnColumn[] = [
  {
    key: "context",
    head: "context",
    num: true,
    title: "context_tokens: the prompt this call processed (input + cache read + cache write)",
    render: (k) => <span className="strong">{fmt(k.context_tokens)}</span>,
  },
  { key: "ctx_pct", head: "ctx %", num: true, render: (k) => pct(k.context_pct) },
  { key: "output", head: "output", num: true, render: (k) => fmt(k.usage.output_tokens) },
  { key: "thinking", head: "thinking", num: true, render: (k) => fmt(k.usage.reasoning_tokens) },
  { key: "latency", head: "latency", num: true, render: (k) => ms(k.latency_ms) },
  { key: "tok_s", head: "tok/s", num: true, render: (k) => fmt(k.output_tokens_per_sec) },
  { key: "stop", head: "stop", render: (k) => k.stop_reason ?? "–" },
];

/** Claude bills cache writes explicitly, by TTL (ADR 0019): all four tiers are columns. */
const CLAUDE_USAGE: TurnColumn[] = [
  { key: "cache_read", head: "cache_read", num: true, render: (k) => fmt(k.usage.cache_read_tokens) },
  { key: "cache_write", head: "cache_write", num: true, render: (k) => fmt(k.usage.cache_write_tokens) },
  { key: "cache_1h", head: "1h", num: true, render: (k) => fmt(k.usage.cache_write_1h_tokens) },
  { key: "input", head: "input", num: true, render: (k) => fmt(k.usage.input_tokens) },
];

/** Codex caches implicitly: no write tiers exist, and the read tier is `cached_input_tokens`. */
const CODEX_USAGE: TurnColumn[] = [
  {
    key: "cached_input",
    head: "cached input",
    num: true,
    title: "cached_input_tokens: the prompt prefix the provider re-read from its implicit cache",
    render: (k) => fmt(k.usage.cache_read_tokens),
  },
  { key: "input", head: "input (uncached)", num: true, render: (k) => fmt(k.usage.input_tokens) },
];

interface Props {
  result: RunResult;
  view: TurnView;
  onViewChange: (v: TurnView) => void;
  /** The turn whose details row is open from the `turn=` URL param, or null. */
  openTurn: number | null;
  onOpenTurn: (n: number | null) => void;
  recordView: RecordView;
  onRecordViewChange?: (v: RecordView) => void;
  /** Renders a turn's TurnRawRecords; wired by the integrator so this file needs no records import. */
  renderTurnRecords?: (call: Call) => ReactNode;
  /** Extra toolbar content, where the integrator places RecordViewToggle. */
  toolbarExtra?: ReactNode;
}

interface BaseProps extends Props {
  harness: string;
  columns: TurnColumn[];
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

const billedOf = (s: Subagent): number =>
  s.usage.accumulative_billed_tokens ?? s.usage.input_tokens + s.usage.output_tokens + s.usage.cache_read_tokens + s.usage.cache_write_tokens;

/**
 * The parallel threads a turn spawned, rendered beneath it: each subagent's own per-call
 * ledger, indented and bordered in the waterfall's `sub` colour so the band reads as a
 * fork off the primary thread (glossary: `SubagentBand`).
 */
function SubagentBand({ result, subs }: { result: RunResult; subs: Subagent[] }) {
  return (
    <div data-el="SubagentBand" style={{ display: "grid", gap: 12, padding: "4px 0 4px 24px", borderLeft: "3px solid var(--xh-waterfall-sub)" }}>
      {subs.map((s) => (
        <div key={s.id} data-agent={s.agent} style={{ display: "grid", gap: 6 }}>
          <XStack alignItems="center" flexWrap="wrap" gap={10}>
            <span className="pill" style={{ background: "var(--xh-waterfall-sub)", color: "#fff" }}>
              ⑂ {s.agent}
            </span>
            <CopyId id={s.id} label={short(s.id)} />
            {s.description ? (
              <Text color="$muted" fontSize={13} fontFamily="$body">
                {s.description}
              </Text>
            ) : null}
            <span className="num muted" style={{ marginLeft: "auto", fontVariantNumeric: "tabular-nums" }}>
              {s.turns} turn{s.turns === 1 ? "" : "s"} · {fmt(billedOf(s))} billed tokens
            </span>
          </XStack>
          {s.calls.length ? (
            <Table className="subagent-turns">
              <TableHeader>
                <TableRow>
                  <TableHead>turn</TableHead>
                  <TableHead>time</TableHead>
                  <TableHead>tools issued</TableHead>
                  <TableHead className="num">cache_read</TableHead>
                  <TableHead className="num">input</TableHead>
                  <TableHead className="num" title="context_tokens: the prompt this call processed">
                    context
                  </TableHead>
                  <TableHead className="num">output</TableHead>
                  <TableHead className="num">thinking</TableHead>
                  <TableHead className="num">latency</TableHead>
                  <TableHead>stop</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {s.calls.map((k) => (
                  <TableRow key={k.n} data-el="SubagentTurnRow" data-agent={s.agent} data-n={k.n}>
                    <TableCell>
                      <code>{`${short(s.id)}/t${k.n}`}</code>
                    </TableCell>
                    <TableCell>
                      <span style={{ fontVariantNumeric: "tabular-nums" }}>{clock(k.at)}</span>
                    </TableCell>
                    <TableCell>
                      {k.tools?.length ? (
                        k.tools.map((t, i) => (
                          <code key={i} className="code-chip">
                            {t.name}
                          </code>
                        ))
                      ) : (
                        <span className="muted">(final reply)</span>
                      )}
                    </TableCell>
                    <TableCell className="num">{fmt(k.usage.cache_read_tokens)}</TableCell>
                    <TableCell className="num">{fmt(k.usage.input_tokens)}</TableCell>
                    <TableCell className="num">
                      <span className="strong">{fmt(k.context_tokens)}</span>
                    </TableCell>
                    <TableCell className="num">{fmt(k.usage.output_tokens)}</TableCell>
                    <TableCell className="num">{fmt(k.usage.reasoning_tokens)}</TableCell>
                    <TableCell className="num">{ms(k.latency_ms)}</TableCell>
                    <TableCell>{k.stop_reason ?? "–"}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <span className="muted">no per-call ledger in this transcript</span>
          )}
        </div>
      ))}
      <span className="muted" style={{ fontSize: 12 }}>
        Spawned by turn {subs[0]?.parent_turn ?? "?"} of {short(result.session_id)}; each thread's bill is inside the session's accumulative_billed_tokens.
      </span>
    </div>
  );
}

function SessionTurnTableBase({ result, harness, columns, view, onViewChange, openTurn, onOpenTurn, renderTurnRecords, toolbarExtra }: BaseProps) {
  const calls = result.calls ?? [];
  const subsByTurn = useMemo(() => {
    const map = new Map<number, Subagent[]>();
    for (const s of result.subagents ?? []) {
      const turn = s.parent_turn ?? 1;
      map.set(turn, [...(map.get(turn) ?? []), s]);
    }
    return map;
  }, [result]);
  const toggle = (n: number) => {
    onOpenTurn(openTurn === n ? null : n);
  };
  return (
    <Card id="SessionTurnTablePanel" data-el="SessionTurnTable" data-harness={harness}>
      <CardHeader>
        <CardTitle>
          Turns
          <El name="SessionTurnTable" />
        </CardTitle>
        <XStack flexWrap="wrap" alignItems="center" gap={12}>
          <Text color="$muted" fontSize={14} fontFamily="$body" flexShrink={1} maxWidth="100%">
            One row per model API call (a SessionTurn). A turn's records are its own blocks, the results of the tools it issued, and the harness records written
            before the next turn began.
            {result.subagents?.length
              ? ` This session spawned ${result.subagents.length} parallel subagent${result.subagents.length === 1 ? "" : "s"}; each appears under the turn that spawned it.`
              : ""}
          </Text>
          <XStack flexGrow={1} />
          <ViewToggle view={view} onChange={onViewChange} />
          {toolbarExtra}
        </XStack>
      </CardHeader>
      <CardContent>
        <Table id="SessionTurnTable">
          <TableHeader>
            <TableRow>
              {columns.map((col) => (
                <TableHead key={col.key} className={col.num ? "num" : undefined} title={col.title}>
                  {col.head}
                </TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {!calls.length ? (
              <TableRow>
                <TableCell colSpan={columns.length} className="warn">
                  This result has no per-turn ledger (it predates ADR 0019). Replay the cache to build one.
                </TableCell>
              </TableRow>
            ) : (
              calls.map((k) => {
                const open = view === "detailed" || openTurn === k.n;
                const spawned = subsByTurn.get(k.n) ?? [];
                return (
                  <Fragment key={k.n}>
                    <TableRow
                      className={`SessionTurnRow ${open ? "row-open" : ""}`}
                      style={{ cursor: "pointer" }}
                      data-n={k.n}
                      data-el="SessionTurnRow"
                      onClick={() => toggle(k.n)}
                    >
                      {columns.map((col) => (
                        <TableCell key={col.key} className={col.num ? "num" : undefined}>
                          {col.render(k, result)}
                        </TableCell>
                      ))}
                    </TableRow>
                    {open ? (
                      <TableRow className="detail-row" data-n={k.n}>
                        <TableCell colSpan={columns.length} style={{ whiteSpace: "normal" }}>
                          {renderTurnRecords ? (
                            renderTurnRecords(k)
                          ) : (
                            <div id={turnId(result.session_id, k.n)} className="muted">
                              no record renderer wired
                            </div>
                          )}
                        </TableCell>
                      </TableRow>
                    ) : null}
                    {spawned.length ? (
                      <TableRow className="subagent-band-row" data-n={k.n}>
                        <TableCell colSpan={columns.length} style={{ whiteSpace: "normal" }}>
                          <SubagentBand result={result} subs={spawned} />
                        </TableCell>
                      </TableRow>
                    ) : null}
                  </Fragment>
                );
              })
            )}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}

/** The Claude ledger table: explicit cache-write tiers between the row core and the context columns. */
export function SessionTurnTableClaude(props: Props) {
  return <SessionTurnTableBase {...props} harness="claude" columns={[...CORE_LEFT, ...CLAUDE_USAGE, ...CORE_RIGHT]} />;
}

/** The Codex ledger table: implicit caching, so only `cached input` and uncached `input`. */
export function SessionTurnTableCodex(props: Props) {
  return <SessionTurnTableBase {...props} harness="codex" columns={[...CORE_LEFT, ...CODEX_USAGE, ...CORE_RIGHT]} />;
}

/** Dispatch by the result's harness; an unknown harness gets the full Claude column set. */
export function SessionTurnTable(props: Props) {
  return props.result.harness === "codex" ? <SessionTurnTableCodex {...props} /> : <SessionTurnTableClaude {...props} />;
}
