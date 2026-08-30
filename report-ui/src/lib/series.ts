/**
 * The pure math behind the per-session charts (ADR 0019, 0024, 0025): which log line measured
 * each turn, the step series that hold a value from one measurement to the next, and the
 * token-waterfall decomposition. No rendering here, so every number is unit-testable.
 */
import { short } from "./format";
import type { Call, Cell, RunResult, Usage } from "./types";

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

const billedOf = (u: Usage): number => u.accumulative_billed_tokens ?? u.input_tokens + u.output_tokens + u.cache_read_tokens + u.cache_write_tokens;

/**
 * Each subagent's billed tokens attributed to the primary turn that spawned it
 * (`parent_turn`; an unattributed thread lands on turn 1). Their usage is already inside
 * the run's `usage`, so this is the split that lets the waterfall still reconcile to
 * `accumulative_billed_tokens`.
 */
export function subagentsByTurn(result: RunResult): Map<number, number> {
  const map = new Map<number, number>();
  for (const sub of result.subagents ?? []) {
    const turn = sub.parent_turn ?? 1;
    map.set(turn, (map.get(turn) ?? 0) + billedOf(sub.usage));
  }
  return map;
}

/** One column of the per-turn token waterfall. `base` is the invisible riser the visible segments sit on. */
export interface WaterfallColumn {
  label: string;
  base: number;
  baseline: number;
  read: number;
  context: number;
  thinking: number;
  output: number;
  sub: number;
  total: number;
}

/**
 * Per turn: a `baseline` column, one column per turn (cache read re-read, new context = input +
 * cache write, thinking, visible output, each stacked on the running sum), and a `total` column
 * that ends at `accumulative_billed_tokens`. Turn 1's prompt is the baseline, so its column carries
 * only its output.
 */
export function waterfallColumns(result: RunResult): WaterfallColumn[] {
  const zero = (label: string): WaterfallColumn => ({ label, base: 0, baseline: 0, read: 0, context: 0, thinking: 0, output: 0, sub: 0, total: 0 });
  const bySub = subagentsByTurn(result);
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
    col.sub = bySub.get(k.n) ?? 0;
    run += (i > 0 ? u.cache_read_tokens + u.input_tokens + u.cache_write_tokens : 0) + u.output_tokens + col.sub;
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
  sub: number;
}

/** Cumulative tokens by category after each turn's measurement, in turn order. */
export function cumulativeByTurn(result: RunResult): CumulativeTokens[] {
  const out: CumulativeTokens[] = [];
  const bySub = subagentsByTurn(result);
  let base = 0;
  let read = 0;
  let context = 0;
  let thinking = 0;
  let output = 0;
  let sub = 0;
  result.calls.forEach((k, i) => {
    const u = k.usage;
    if (i === 0) base = result.baseline_tokens;
    else {
      read += u.cache_read_tokens;
      context += u.input_tokens + u.cache_write_tokens;
    }
    thinking += u.reasoning_tokens;
    output += visibleOutput(k);
    sub += bySub.get(k.n) ?? 0;
    out.push({ base, read, context, thinking, output, sub });
  });
  return out;
}

/** One row per log line for the per-line waterfall: the cumulative categories held from the last measurement. */
export function waterfallByLine(result: RunResult, lines: string[] | null): { rows: (CumulativeTokens & { line: number })[]; starts: number[] } {
  const cum = cumulativeByTurn(result);
  const empty: CumulativeTokens = { base: 0, read: 0, context: 0, thinking: 0, output: 0, sub: 0 };
  const s = stepSeries(result, lines, (_k, t) => cum[t] ?? empty, empty);
  return { rows: s.x.map((line, i) => ({ line, ...(s.y[i] ?? empty) })), starts: s.starts };
}

/**
 * Cumulative estimated USD after each turn's call, priced with the result's own
 * `rates_applied` exactly as the plugin's `pricing.breakdown` does (per-token rates; an
 * untagged cache write bills at the 5-minute rate, ADR 0019). `null` when the result
 * carries no usable rates, so an unpriced run never draws a zero-cost line.
 */
export function cumulativeCostByTurn(result: RunResult): number[] | null {
  const rates = result.rates_applied as Record<string, unknown>;
  const rate = (key: string): number => (typeof rates?.[key] === "number" ? (rates[key] as number) : 0);
  if (!rates || typeof rates.input !== "number" || typeof rates.output !== "number") return null;
  const usageCost = (u: Usage): number => {
    const tagged = u.cache_write_1h_tokens + u.cache_write_5m_tokens;
    const untagged = Math.max(u.cache_write_tokens - tagged, 0);
    return (
      u.input_tokens * rate("input") +
      u.output_tokens * rate("output") +
      u.cache_read_tokens * rate("cache_read") +
      (u.cache_write_5m_tokens + untagged) * rate("cache_write") +
      u.cache_write_1h_tokens * rate("cache_write_1h")
    );
  };
  // A subagent's spend lands on the turn that spawned it, priced at the run's own rates
  // (the plugin folds subagent usage into `usage` and prices it the same way).
  const subCost = new Map<number, number>();
  for (const sub of result.subagents ?? []) {
    const turn = sub.parent_turn ?? 1;
    subCost.set(turn, (subCost.get(turn) ?? 0) + usageCost(sub.usage));
  }
  let run = 0;
  return result.calls.map((k) => {
    run += usageCost(k.usage) + (subCost.get(k.n) ?? 0);
    return run;
  });
}

/** The running `accumulative_billed_tokens` after each turn: the overview's accumulation line.
 *  `bySub` (see `subagentsByTurn`) adds each spawned thread's bill at its spawning turn, so
 *  the line ends at the session's whole `accumulative_billed_tokens`. */
export function accumulation(calls: Call[], bySub?: Map<number, number>): { n: number; billed: number }[] {
  let run = 0;
  return calls.map((k) => {
    const u = k.usage;
    run += u.input_tokens + u.cache_read_tokens + u.cache_write_tokens + u.output_tokens + (bySub?.get(k.n) ?? 0);
    return { n: k.n, billed: run };
  });
}

/** The legend / hover label of a session: case · harness/model · short id. */
export const sessionLabel = (c: Cell): string => `${c.case} · ${c.harness}/${c.model} · ${short(c.session_id)}`;

/** One aggregated line of the overview accumulation chart: every run of a suite × harness × model cell. */
export interface AccumulationGroup {
  key: string;
  label: string;
  runs: number;
  /** turn numbers 1..N, N = the longest run in the group */
  turns: number[];
  /** per turn, over the runs that reached it */
  mean: number[];
  min: number[];
  max: number[];
}

const suiteName = (c: Cell): string => (c.suite ? (c.suite.split("/").pop() ?? c.suite) : c.case);

/**
 * Group the ledgered sessions by suite × harness × model and aggregate their per-turn
 * `accumulative_billed_tokens`: the mean line with a min–max envelope. A turn only some
 * runs reached aggregates over the runs that did.
 */
export function accumulationGroups(cells: Cell[], results: Record<string, RunResult | null | undefined>): AccumulationGroup[] {
  const byKey = new Map<string, { label: string; series: number[][] }>();
  for (const c of cells) {
    const result = results[c.session_id];
    if (!c.has_ledger || !result?.calls?.length) continue;
    const key = `${suiteName(c)}|${c.harness}|${c.model}`;
    const entry = byKey.get(key) ?? { label: `${suiteName(c)} · ${c.harness}/${c.model}`, series: [] };
    entry.series.push(accumulation(result.calls, subagentsByTurn(result)).map((p) => p.billed));
    byKey.set(key, entry);
  }
  return [...byKey.entries()].map(([key, { label, series }]) => {
    const turnCount = Math.max(...series.map((s) => s.length));
    const turns: number[] = [];
    const mean: number[] = [];
    const min: number[] = [];
    const max: number[] = [];
    for (let t = 0; t < turnCount; t++) {
      const at = series.filter((s) => t < s.length).map((s) => s[t]!);
      turns.push(t + 1);
      mean.push(Math.round(at.reduce((sum, v) => sum + v, 0) / at.length));
      min.push(Math.min(...at));
      max.push(Math.max(...at));
    }
    return { key, label: `${label} · n=${series.length}`, runs: series.length, turns, mean, min, max };
  });
}

/** One column of the overview's aggregate waterfall: the mean of a category over the runs that reached it. */
export interface AggregateWaterfall {
  /** ledgered runs that contributed at all */
  runs: number;
  /** `baseline`, `t1`..`tN`, `total`; every field is a mean over `n[i]` runs */
  columns: WaterfallColumn[];
  /** per column, how many runs reached it — the last turns of a long run are a thinner mean */
  n: number[];
  /** per column, the min and max of the *running total* across the runs that reached it */
  min: number[];
  max: number[];
}

/**
 * The `TokenWaterfallChart`'s decomposition, averaged across many runs (glossary:
 * `TokenWaterfallAggregateChart`).
 *
 * Runs are aligned by turn index — turn 3 of one run against turn 3 of another — and each
 * column is the arithmetic mean over the runs that *reached* that turn, never over all of them:
 * a category is missing from a short run, not zero in it, and the divisor is `n[i]`. Because the
 * mean of each run's running base and the mean of its segments are taken over that same subset,
 * the top of a stacked column is the mean running total, which is what the whiskers bracket.
 *
 * The `total` column is the mean of each run's OWN final total, so on a group of unequal lengths
 * it sits above the last turn's column rather than level with it: the last turn is a mean over
 * the runs that got that far, and the total is a mean over all of them. That is the honest
 * reading of "these runs, on average", and it is why `n` is reported per column.
 */
export function aggregateWaterfall(cells: Cell[], results: Record<string, RunResult | null | undefined>): AggregateWaterfall {
  const perRun: WaterfallColumn[][] = [];
  for (const c of cells) {
    const result = results[c.session_id];
    if (!c.has_ledger || !result?.calls?.length) continue;
    perRun.push(waterfallColumns(result));
  }
  if (perRun.length === 0) return { runs: 0, columns: [], n: [], min: [], max: [] };

  const KEYS = ["baseline", "read", "context", "thinking", "output", "sub", "total"] as const;
  const turns = Math.max(...perRun.map((cols) => cols.length - 2));
  const running = (col: WaterfallColumn): number => col.base + col.baseline + col.read + col.context + col.thinking + col.output + col.sub + col.total;

  const columns: WaterfallColumn[] = [];
  const n: number[] = [];
  const min: number[] = [];
  const max: number[] = [];

  // `baseline`, then one column per turn index, then `total` — each run contributing its own
  // column at that index, and its LAST column to `total`.
  const at = (i: number): WaterfallColumn[] =>
    i <= turns ? perRun.filter((cols) => i < cols.length - 1).map((cols) => cols[i]!) : perRun.map((cols) => cols[cols.length - 1]!);

  for (let i = 0; i <= turns + 1; i++) {
    const group = at(i);
    const mean = (pick: (col: WaterfallColumn) => number): number => group.reduce((sum, col) => sum + pick(col), 0) / group.length;
    const column = { label: i === 0 ? "baseline" : i > turns ? "total" : `t${i}`, base: mean((col) => col.base) } as WaterfallColumn;
    for (const key of KEYS) column[key] = mean((col) => col[key]);
    const totals = group.map(running);
    columns.push(column);
    n.push(group.length);
    min.push(Math.min(...totals));
    max.push(Math.max(...totals));
  }
  return { runs: perRun.length, columns, n, min, max };
}
