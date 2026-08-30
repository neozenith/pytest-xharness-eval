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
    { base: 100, read: 0, context: 0, thinking: 10, output: 20, sub: 0 },
    { base: 100, read: 100, context: 45, thinking: 10, output: 40, sub: 0 },
    { base: 100, read: 245, context: 75, thinking: 60, output: 50, sub: 0 },
  ]);
  const { rows, starts } = waterfallByLine(result, lines);
  expect(starts).toEqual([1, 5, 7]);
  expect(rows).toHaveLength(9);
  expect(rows[3]).toEqual({ line: 4, base: 100, read: 0, context: 0, thinking: 10, output: 20, sub: 0 });
  expect(rows[4]).toEqual({ line: 5, base: 100, read: 100, context: 45, thinking: 10, output: 40, sub: 0 });
  expect(rows[8]!.read).toBe(245);
});

test("accumulation is the running sum of the four priced tiers, reasoning inside output", () => {
  expect(accumulation(result.calls)).toEqual([
    { n: 1, billed: 130 },
    { n: 2, billed: 295 },
    { n: 3, billed: 530 },
  ]);
});

test("subagent bills land on the spawning turn: the waterfall, accumulation and cost still reconcile", async () => {
  const { subagentsByTurn } = await import("@/lib/series");
  const sub = (agent: string, parent_turn: number | null, u: Partial<Usage>) => ({
    agent,
    id: `${agent}-id`,
    log: `subagents/${agent}.jsonl`,
    parent_turn,
    turns: 1,
    description: "",
    usage: usage(u),
    calls: [call(1, [1], u)],
  });
  const withSubs: RunResult = {
    ...result,
    subagents: [
      sub("Explore", 2, { input_tokens: 500, output_tokens: 100 }),
      sub("Curie", 2, { cache_read_tokens: 300, output_tokens: 50 }),
      sub("orphan", null, { output_tokens: 10 }), // unattributed: lands on turn 1
    ],
  };
  expect(subagentsByTurn(withSubs)).toEqual(
    new Map([
      [2, 950],
      [1, 10],
    ]),
  );
  const cols = waterfallColumns(withSubs);
  expect(cols[1]).toMatchObject({ sub: 10 });
  expect(cols[2]).toMatchObject({ sub: 950 });
  // the total column still closes the bridge: primary 530 plus every spawned thread's bill
  expect(cols[4]!.total).toBe(530 + 960);
  expect(accumulation(withSubs.calls, subagentsByTurn(withSubs)).at(-1)!.billed).toBe(530 + 960);
  expect(cumulativeByTurn(withSubs).map((c) => c.sub)).toEqual([10, 960, 960]);
  // cost: rates of $1/MTok everywhere makes each tier's cost its token count
  const rates = { input: 1e-6, output: 1e-6, cache_read: 1e-6, cache_write: 1e-6, cache_write_1h: 1e-6 };
  const { cumulativeCostByTurn } = await import("@/lib/series");
  const costs = cumulativeCostByTurn({ ...withSubs, rates_applied: rates })!;
  expect(Math.round(costs.at(-1)! * 1e6)).toBe(530 + 960);
});

test("sessionLabel is case · harness/model · short id", () => {
  expect(sessionLabel({ case: "eval_x", harness: "claude", model: "claude-opus-5", session_id: "1feb573f-ba51" } as never)).toBe(
    "eval_x · claude/claude-opus-5 · 1feb573f",
  );
});

test("accumulationGroups aggregates runs by suite, harness and model with a min-max envelope", async () => {
  const { accumulationGroups } = await import("@/lib/series");
  const cell = (session_id: string, over: object = {}) =>
    ({ session_id, suite: "skills/x/evals/eval_a.py", case: "eval_a", harness: "claude", model: "m", has_ledger: true, ...over }) as never;
  const run = (billed: number[]) =>
    ({ calls: billed.map((b, i) => ({ n: i + 1, usage: { input_tokens: b, cache_read_tokens: 0, cache_write_tokens: 0, output_tokens: 0 } })) }) as never;
  const groups = accumulationGroups([cell("s1"), cell("s2"), cell("s3", { harness: "codex" })], {
    s1: run([100, 100, 100]),
    s2: run([200, 200]),
    s3: run([50]),
  });
  expect(groups).toHaveLength(2);
  const claude = groups.find((g) => g.key.includes("claude"))!;
  expect(claude.runs).toBe(2);
  expect(claude.label).toBe("eval_a.py · claude/m · n=2");
  // turn 1: mean(100, 200); turn 2: mean(200, 400); turn 3: only s1 reached it
  expect(claude.mean).toEqual([150, 300, 300]);
  expect(claude.min).toEqual([100, 200, 300]);
  expect(claude.max).toEqual([200, 400, 300]);
});

test("cumulativeCostByTurn mirrors pricing.breakdown, including the untagged-cache-write TTL rule", async () => {
  const { cumulativeCostByTurn } = await import("@/lib/series");
  const call = (usage: object) => ({
    n: 1,
    at: "t",
    usage: {
      input_tokens: 0,
      output_tokens: 0,
      cache_read_tokens: 0,
      cache_write_tokens: 0,
      cache_write_1h_tokens: 0,
      cache_write_5m_tokens: 0,
      reasoning_tokens: 0,
      ...usage,
    },
  });
  const r = {
    rates_applied: { input: 2e-6, output: 1e-5, cache_read: 2e-7, cache_write: 2.5e-6, cache_write_1h: 4e-6 },
    calls: [
      call({ input_tokens: 100, output_tokens: 10 }),
      // 50 tagged 1h + 30 untagged (bills at the 5m rate) + 20 read
      call({ cache_write_tokens: 80, cache_write_1h_tokens: 50, cache_read_tokens: 20 }),
    ],
  } as never;
  const cost = cumulativeCostByTurn(r)!;
  expect(cost[0]).toBeCloseTo(100 * 2e-6 + 10 * 1e-5, 10);
  expect(cost[1]! - cost[0]!).toBeCloseTo(20 * 2e-7 + 30 * 2.5e-6 + 50 * 4e-6, 10);
  expect(cumulativeCostByTurn({ rates_applied: {}, calls: [] } as never)).toBeNull();
});

test("aggregateWaterfall averages the decomposition over the runs that reached each turn", async () => {
  const { aggregateWaterfall } = await import("@/lib/series");
  const cell = (session_id: string) => ({ session_id, has_ledger: true }) as never;
  /*
   * Two runs, deliberately unequal: one of three turns and one of two. Turn 3 exists in one run
   * only, so its column must average over that ONE run rather than dividing a single run's
   * tokens by two — a category is missing from a short run, never zero in it.
   */
  const run = (baseline: number, outputs: number[]) =>
    ({
      baseline_tokens: baseline,
      calls: outputs.map((out, i) => ({
        n: i + 1,
        usage: { input_tokens: 0, cache_read_tokens: 0, cache_write_tokens: 0, output_tokens: out, reasoning_tokens: 0 },
      })),
    }) as never;
  const agg = aggregateWaterfall([cell("a"), cell("b")], { a: run(100, [10, 20, 30]), b: run(200, [40, 60]) });

  expect(agg.runs).toBe(2);
  // baseline, t1, t2, t3, total
  expect(agg.columns.map((c) => c.label)).toEqual(["baseline", "t1", "t2", "t3", "total"]);
  expect(agg.n).toEqual([2, 2, 2, 1, 2]);
  expect(agg.columns[0]!.baseline).toBe(150);
  expect(agg.columns[1]!.output).toBe(25);
  expect(agg.columns[3]!.output).toBe(30);

  /*
   * The stack's top is the mean running total, because the mean base and the mean segments are
   * taken over the same subset of runs. Run a: 100/110/130/160; run b: 200/240/300.
   */
  const top = (i: number) => agg.columns[i]!.base + agg.columns[i]!.baseline + agg.columns[i]!.output + agg.columns[i]!.total;
  expect(top(1)).toBe(175);
  expect(agg.min).toEqual([100, 110, 130, 160, 160]);
  expect(agg.max).toEqual([200, 240, 300, 160, 300]);
  // the `total` column is each run's OWN final total, so it sits above a last turn only one run reached
  expect(agg.columns[4]!.total).toBe(230);
});

test("aggregateWaterfall reports nothing rather than dividing by zero when no run has a ledger", async () => {
  const { aggregateWaterfall } = await import("@/lib/series");
  expect(aggregateWaterfall([{ session_id: "a", has_ledger: false } as never], {})).toEqual({ runs: 0, columns: [], n: [], min: [], max: [] });
});
