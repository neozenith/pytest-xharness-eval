/**
 * The data every component spec builds on: one `Cell`, one `RunResult` with a real ledger, a
 * multi-arm sweep across the effort axis, and the inline payload that serves them to the data
 * hooks. Plain values only — they cross from the Node test runner into the browser as props.
 *
 * Shapes follow `src/lib/types.ts`, which mirrors what `emit/` writes. A field a spec needs to
 * vary is an override, never a second fixture that drifts from this one.
 */
import type { Call, Cell, DesignTokens, Index, InlineData, RunResult, Usage } from "../src/lib/types";
import tokens from "../../src/pytest_xharness_eval/assets/report.tokens.json";

export const SID = "1feb573f-ba51-4e77-845f-12c4bcb08252";

export const cell = (over: Partial<Cell> = {}): Cell => ({
  case: "eval_dual_density",
  suite: "skills/mermaidjs-diagrams/evals/eval_mermaid.py",
  skill: "mermaidjs-diagrams",
  fixture: "small-repo",
  task: "draw the architecture",
  prompt: "/mermaidjs-diagrams draw the architecture",
  harness: "claude",
  model: "claude-opus-5",
  effort: null,
  session_id: SID,
  verdict: "pass",
  at: "2026-09-23T07:18:05.537Z",
  node: null,
  wall_ms: 83_000,
  result: `${SID}.result.json`,
  log: `${SID}.jsonl`,
  estimated_cost_usd: 1.0276,
  harness_reported_cost_usd: 1.0288,
  rates_applied: {},
  accumulative_billed_tokens: 1_504_090,
  baseline_tokens: 35_599,
  context_window: 1_000_000,
  peak_context_tokens: 120_245,
  context_window_pct: 12.02,
  final_context_pct: 12.06,
  ttft_ms: 1_400,
  output_tokens_per_sec: 61.2,
  turns: 3,
  reported_turns: 23,
  subagents: 0,
  tool_calls: 14,
  duration_ms: 80_000,
  files_written: ["ARCHITECTURE.md"],
  has_ledger: true,
  record_kinds: { "claude/assistant/tool_use": 6, "claude/user/tool_result": 6 },
  skill_coverage: { files: 5, ignored: 1, docs: 2, scripts: 2, tests: 1, assets: 0, loaded: 2, run: 1 },
  ...over,
});

export const usage = (over: Partial<Usage> = {}): Usage => ({
  input_tokens: 2,
  output_tokens: 264,
  cache_read_tokens: 35_865,
  cache_write_tokens: 4_234,
  cache_write_1h_tokens: 4_234,
  cache_write_5m_tokens: 0,
  reasoning_tokens: 42,
  ...over,
});

export const call = (n: number, over: Partial<Call> = {}): Call => ({
  n,
  at: `2026-09-23T07:12:${String(10 + n).padStart(2, "0")}.549Z`,
  usage: usage({ cache_read_tokens: 35_000 * n, output_tokens: 200 * n }),
  tools: [
    { name: "Bash", input: { command: "ls" }, id: `toolu_${n}a` },
    { name: "Read", input: { file_path: "SKILL.md" }, id: `toolu_${n}b` },
  ],
  text: n === 3 ? "Both gates pass clean." : "",
  thinking: n === 1 ? "Plan the diagram first." : "",
  stop_reason: n === 3 ? "end_turn" : "tool_use",
  latency_ms: 1_716,
  context_tokens: 40_000 * n,
  context_pct: 4 * n,
  output_tokens_per_sec: 150,
  records: [3 * n - 2, 3 * n - 1, 3 * n],
  results_in: n === 1 ? [] : [{ tool: "Bash", chars: 31, content: "(Bash completed with no output)" }],
  ...over,
});

export const result = (over: Partial<RunResult> = {}): RunResult => ({
  harness: "claude",
  model: "claude-opus-5",
  effort: null,
  session_id: SID,
  turns: 3,
  reported_turns: 23,
  usage: usage({ input_tokens: 32, output_tokens: 37_009, cache_read_tokens: 1_371_238, cache_write_tokens: 95_811, cache_write_1h_tokens: 95_811 }),
  calls: [call(1), call(2), call(3)],
  context_window: 1_000_000,
  peak_context_tokens: 120_245,
  final_context_tokens: 120_631,
  context_window_pct: 12.02,
  final_context_pct: 12.06,
  baseline_tokens: 35_599,
  estimated_cost_usd: 1.027646,
  harness_reported_cost_usd: 1.0287836,
  rates_applied: { input: 5e-6, output: 2.5e-5, cache_read: 5e-7, cache_write: 6.25e-6, cache_write_1h: 1e-5, model: "claude-opus-5", source: "prices.toml" },
  final_text: "Both gates pass clean.",
  files_written: ["ARCHITECTURE.md"],
  tool_calls: { Bash: 10, Read: 4 },
  record_kinds: { "claude/assistant/tool_use": 6, "claude/user/tool_result": 6 },
  skill_coverage: {},
  case: { name: "eval_dual_density", suite: "skills/mermaidjs-diagrams/evals/eval_mermaid.py", task: "draw the architecture" },
  cost_by_tier: { cache_read: 0.685, cache_write_1h: 0.958, cache_write_5m: 0, input: 0.00016, output: 0.925 },
  ...over,
});

/** A session log whose line numbers match `call(n).records`: nine JSON lines. */
export const log = (): string[] =>
  Array.from({ length: 9 }, (_, i) =>
    JSON.stringify(
      i % 3 === 1
        ? { type: "assistant", message: { model: "claude-opus-5", content: [{ type: "text", text: `line ${i + 1}` }], usage: { input_tokens: 1 } } }
        : { type: "user", message: { content: [{ type: "tool_result", content: `result ${i + 1}` }] } },
    ),
  );

/**
 * A sweep across every axis: two harnesses, three models, and one model at three rungs plus a
 * rung-less (pre-ADR 0049) session, so ordering, grouping and the null case all show.
 */
export const sweep = (): Cell[] => [
  cell({ session_id: "aaaaaaaa-0001", effort: "max", estimated_cost_usd: 3.1, verdict: "pass" }),
  cell({ session_id: "aaaaaaaa-0002", effort: "low", estimated_cost_usd: 0.4, verdict: "fail" }),
  cell({ session_id: "aaaaaaaa-0003", effort: "high", estimated_cost_usd: 1.2, verdict: "pass" }),
  cell({ session_id: "aaaaaaaa-0004", effort: null, estimated_cost_usd: 1.0, verdict: null }),
  cell({ session_id: "bbbbbbbb-0001", model: "claude-sonnet-5", effort: "medium", estimated_cost_usd: 0.6 }),
  cell({ session_id: "cccccccc-0001", harness: "codex", model: "gpt-5.6-sol", effort: "xhigh", estimated_cost_usd: 0.9 }),
  cell({ session_id: "cccccccc-0002", harness: "codex", model: "gpt-5.6-luna", effort: "low", skill: "discovery", case: "eval_map" }),
];

export const index = (cells: Cell[] = sweep()): Index => ({ generated_at: "2026-09-24T01:00:00Z", captured: ".xharness_eval_cache", inline: true, cells });

/** The inline payload: every cell served the same result (its identity overridden) and log. */
export const inline = (cells: Cell[] = sweep()): InlineData => ({
  index: index(cells),
  results: Object.fromEntries(cells.map((c) => [c.session_id, result({ session_id: c.session_id, harness: c.harness, model: c.model, effort: c.effort })])),
  logs: Object.fromEntries(cells.map((c) => [c.session_id, log().join("\n")])),
  tokens: tokens as unknown as DesignTokens,
});
