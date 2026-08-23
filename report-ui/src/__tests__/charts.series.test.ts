import {
  accumulation,
  callLine,
  callStarts,
  cumulativeByTurn,
  isCallRecord,
  lastLine,
  sessionLabel,
  stepSeries,
  waterfallByLine,
  waterfallColumns,
} from "@/lib/series";
import type { Call, RunResult, Usage } from "@/lib/types";

const usage = (over: Partial<Usage>): Usage => ({
  input_tokens: 0,
  output_tokens: 0,
  cache_read_tokens: 0,
  cache_write_tokens: 0,
  cache_write_1h_tokens: 0,
  cache_write_5m_tokens: 0,
  reasoning_tokens: 0,
  ...over,
});
const call = (n: number, records: number[], u: Partial<Usage>, context_pct: number | null = null): Call => ({
  n,
  at: "t",
  usage: usage(u),
  tools: [],
  text: "",
  thinking: "",
  stop_reason: "tool_use",
  latency_ms: null,
  context_tokens: (u.input_tokens ?? 0) + (u.cache_read_tokens ?? 0) + (u.cache_write_tokens ?? 0),
  context_pct,
  output_tokens_per_sec: null,
  records,
  results_in: [],
});

/** Three turns over nine log lines. Turn 2's first record (line 4) is a user record; its assistant record is line 5. */
export const result: RunResult = {
  harness: "claude",
  model: "m",
  session_id: "s",
  turns: 3,
  reported_turns: null,
  usage: usage({}),
  calls: [
    call(1, [1, 2, 3], { input_tokens: 100, output_tokens: 30, reasoning_tokens: 10 }, 1.0),
    call(2, [4, 5, 6], { input_tokens: 5, cache_read_tokens: 100, cache_write_tokens: 40, output_tokens: 20, reasoning_tokens: 0 }, 1.45),
    call(3, [7, 8, 9], { input_tokens: 5, cache_read_tokens: 145, cache_write_tokens: 25, output_tokens: 60, reasoning_tokens: 50 }, 1.75),
  ],
  context_window: 10_000,
  peak_context_tokens: 175,
  final_context_tokens: 235,
  context_window_pct: 1.75,
  final_context_pct: 2.35,
  baseline_tokens: 100,
  estimated_cost_usd: null,
  harness_reported_cost_usd: null,
  rates_applied: {},
  final_text: "",
  files_written: [],
  tool_calls: {},
  record_kinds: {},
  skill_coverage: {},
  case: {},
};
const assistant = JSON.stringify({ type: "assistant", message: { model: "m" } });
const user = JSON.stringify({ type: "user" });
const lines = [assistant, user, user, user, assistant, user, assistant, user, user];

test("isCallRecord recognises a Claude assistant record and a Codex token_count, not synthetic messages", () => {
  expect(isCallRecord("claude", { type: "assistant", message: { model: "m" } })).toBe(true);
  expect(isCallRecord("claude", { type: "assistant", message: { model: "<synthetic>" } })).toBe(false);
  expect(isCallRecord("claude", { type: "user" })).toBe(false);
  expect(isCallRecord("codex", { type: "event_msg", payload: { type: "token_count" } })).toBe(true);
  expect(isCallRecord("codex", { type: "response_item" })).toBe(false);
  expect(isCallRecord("codex", null)).toBe(false);
});

test("callLine is the turn's first call record, else its first record; without a log the first record", () => {
  expect(callLine(result, result.calls[1]!, lines)).toBe(5);
  expect(callLine(result, result.calls[1]!, null)).toBe(4);
  expect(callLine(result, result.calls[2]!, lines)).toBe(7);
  expect(callLine(result, call(9, [], {}), null)).toBe(1);
  expect(callStarts(result, lines)).toEqual([1, 5, 7]);
  expect(lastLine(result)).toBe(9);
});

test("stepSeries holds each turn's value from its measuring line until the next, with `before` ahead of the first", () => {
  const s = stepSeries(result, lines, (k) => k.n, 0);
  expect(s.x).toEqual([1, 2, 3, 4, 5, 6, 7, 8, 9]);
  expect(s.y).toEqual([1, 1, 1, 1, 2, 2, 3, 3, 3]);
  expect(s.starts).toEqual([1, 5, 7]);
  const late = stepSeries({ ...result, calls: [call(1, [3, 4], {})] }, null, () => "v", "before");
  expect(late.y).toEqual(["before", "before", "v", "v"]);
});

test("waterfallColumns stacks each turn on the running sum and ends at accumulative_billed_tokens", () => {
  const cols = waterfallColumns(result);
  expect(cols.map((c) => c.label)).toEqual(["baseline", "t1", "t2", "t3", "total"]);
  expect(cols[0]).toMatchObject({ baseline: 100, base: 0 });
  // turn 1: its prompt is the baseline, so only its output stacks on it; thinking split out of output
  expect(cols[1]).toMatchObject({ base: 100, read: 0, context: 0, thinking: 10, output: 20 });
  expect(cols[2]).toMatchObject({ base: 130, read: 100, context: 45, thinking: 0, output: 20 });
  expect(cols[3]).toMatchObject({ base: 295, read: 145, context: 30, thinking: 50, output: 10 });
  const billed = 100 + 30 + (100 + 45 + 20) + (145 + 30 + 60);
  expect(cols[4]).toMatchObject({ total: billed, base: 0 });
  expect(cols[4]!.total).toBe(530);
});

test("cumulativeByTurn and waterfallByLine carry cumulative categories per measuring line", () => {
  expect(cumulativeByTurn(result)).toEqual([
    { base: 100, read: 0, context: 0, thinking: 10, output: 20 },
    { base: 100, read: 100, context: 45, thinking: 10, output: 40 },
    { base: 100, read: 245, context: 75, thinking: 60, output: 50 },
  ]);
  const { rows, starts } = waterfallByLine(result, lines);
  expect(starts).toEqual([1, 5, 7]);
  expect(rows).toHaveLength(9);
  expect(rows[3]).toEqual({ line: 4, base: 100, read: 0, context: 0, thinking: 10, output: 20 });
  expect(rows[4]).toEqual({ line: 5, base: 100, read: 100, context: 45, thinking: 10, output: 40 });
  expect(rows[8]!.read).toBe(245);
});

test("accumulation is the running sum of the four priced tiers, reasoning inside output", () => {
  expect(accumulation(result.calls)).toEqual([
    { n: 1, billed: 130 },
    { n: 2, billed: 295 },
    { n: 3, billed: 530 },
  ]);
});

test("sessionLabel is case · harness/model · short id", () => {
  expect(sessionLabel({ case: "eval_x", harness: "claude", model: "claude-opus-5", session_id: "1feb573f-ba51" } as never)).toBe(
    "eval_x · claude/claude-opus-5 · 1feb573f",
  );
});
