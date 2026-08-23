/**
 * The pure math behind the per-session charts (ADR 0019, 0024, 0025): which log line measured
 * each turn, the step series that hold a value from one measurement to the next, and the
 * token-waterfall decomposition. No rendering here, so every number is unit-testable.
 */
import { short } from "./format";
import type { Call, Cell, RunResult } from "./types";

export type AxisMode = "turn" | "line";

/** A Claude assistant record from a model call, or a Codex `token_count` event: the record that carries a turn's usage. */
export function isCallRecord(harness: string, rec: unknown): boolean {
  const r = rec as { type?: string; message?: { model?: unknown }; payload?: { type?: string } } | null;
  if (!r || typeof r !== "object") return false;
  if (harness === "claude") return r.type === "assistant" && !String(r.message?.model ?? "").startsWith("<");
  return r.type === "event_msg" && r.payload?.type === "token_count";
}

/** The log line at which a turn's usage was measured: its first assistant record (Claude) or its `token_count` (Codex). */
export function callLine(result: RunResult, call: Call, lines: string[] | null): number {
  const records = call.records?.length ? call.records : [1];
  if (!lines) return Math.min(...records);
  for (const n of records) {
    try {
      if (isCallRecord(result.harness, JSON.parse(lines[n - 1] ?? ""))) return n;
    } catch {
      /* not JSON: not a call record */
    }
  }
  return Math.min(...records);
}

/** The last log line any turn claims; the x-extent of every per-line chart. */
export const lastLine = (result: RunResult): number => Math.max(1, ...(result.calls ?? []).flatMap((k) => (k.records?.length ? k.records : [1])));

/** The measuring line of every turn, in turn order. */
export const callStarts = (result: RunResult, lines: string[] | null): number[] => result.calls.map((k) => callLine(result, k, lines));

export interface StepSeries<T> {
  /** log lines 1..N */
  x: number[];
  /** value(line): the latest turn measured at or before that line, else `before` */
  y: T[];
  /** the measuring line of each turn */
  starts: number[];
}

/** A step series over lines 1..N: each line carries the value of the latest turn measured at or before it. */
export function stepSeries<T>(result: RunResult, lines: string[] | null, valueOf: (call: Call, index: number) => T, before: T): StepSeries<T> {
  const N = lastLine(result);
  const starts = callStarts(result, lines);
  const y: T[] = [];
  let t = -1;
  for (let n = 1; n <= N; n++) {
    while (t + 1 < starts.length && (starts[t + 1] ?? Infinity) <= n) t++;
    y.push(t < 0 ? before : valueOf(result.calls[t]!, t));
  }
  return { x: Array.from({ length: N }, (_, i) => i + 1), y, starts };
}

export const visibleOutput = (call: Call): number => Math.max(call.usage.output_tokens - call.usage.reasoning_tokens, 0);

/** One column of the per-turn token waterfall. `base` is the invisible riser the visible segments sit on. */
export interface WaterfallColumn {
  label: string;
  base: number;
  baseline: number;
  read: number;
  context: number;
  thinking: number;
  output: number;
  total: number;
}

/**
 * Per turn: a `baseline` column, one column per turn (cache read re-read, new context = input +
 * cache write, thinking, visible output, each stacked on the running sum), and a `total` column
 * that ends at `accumulative_billed_tokens`. Turn 1's prompt is the baseline, so its column carries
 * only its output.
 */
export function waterfallColumns(result: RunResult): WaterfallColumn[] {
  const zero = (label: string): WaterfallColumn => ({ label, base: 0, baseline: 0, read: 0, context: 0, thinking: 0, output: 0, total: 0 });
  const columns: WaterfallColumn[] = [{ ...zero("baseline"), baseline: result.baseline_tokens }];
  let run = result.baseline_tokens;
  result.calls.forEach((k, i) => {
    const u = k.usage;
    const col = zero(`t${k.n}`);
    col.base = run;
    if (i > 0) {
      col.read = u.cache_read_tokens;
      col.context = u.input_tokens + u.cache_write_tokens;
    }
    col.thinking = u.reasoning_tokens;
    col.output = visibleOutput(k);
    run += (i > 0 ? u.cache_read_tokens + u.input_tokens + u.cache_write_tokens : 0) + u.output_tokens;
    columns.push(col);
  });
  columns.push({ ...zero("total"), total: run });
  return columns;
}

export interface CumulativeTokens {
  base: number;
  read: number;
  context: number;
  thinking: number;
  output: number;
}

/** Cumulative tokens by category after each turn's measurement, in turn order. */
export function cumulativeByTurn(result: RunResult): CumulativeTokens[] {
  const out: CumulativeTokens[] = [];
  let base = 0;
  let read = 0;
  let context = 0;
  let thinking = 0;
  let output = 0;
  result.calls.forEach((k, i) => {
    const u = k.usage;
    if (i === 0) base = result.baseline_tokens;
    else {
      read += u.cache_read_tokens;
      context += u.input_tokens + u.cache_write_tokens;
    }
    thinking += u.reasoning_tokens;
    output += visibleOutput(k);
    out.push({ base, read, context, thinking, output });
  });
  return out;
}

/** One row per log line for the per-line waterfall: the cumulative categories held from the last measurement. */
export function waterfallByLine(result: RunResult, lines: string[] | null): { rows: (CumulativeTokens & { line: number })[]; starts: number[] } {
  const cum = cumulativeByTurn(result);
  const empty: CumulativeTokens = { base: 0, read: 0, context: 0, thinking: 0, output: 0 };
  const s = stepSeries(result, lines, (_k, t) => cum[t] ?? empty, empty);
  return { rows: s.x.map((line, i) => ({ line, ...(s.y[i] ?? empty) })), starts: s.starts };
}

/** The running `accumulative_billed_tokens` after each turn: the overview's accumulation line. */
export function accumulation(calls: Call[]): { n: number; billed: number }[] {
  let run = 0;
  return calls.map((k) => {
    const u = k.usage;
    run += u.input_tokens + u.cache_read_tokens + u.cache_write_tokens + u.output_tokens;
    return { n: k.n, billed: run };
  });
}

/** The legend / hover label of a session: case · harness/model · short id. */
export const sessionLabel = (c: Cell): string => `${c.case} · ${c.harness}/${c.model} · ${short(c.session_id)}`;
