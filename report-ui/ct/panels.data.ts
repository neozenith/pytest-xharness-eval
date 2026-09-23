/**
 * The panel-specific data the `panels.*` component specs share, built on `ct/fixtures.ts`.
 * The ledger values are the ones `src/__tests__/panels.test.tsx` uses (a real Claude result, a
 * real skill catalogue), so the jsdom tests and these browser tests read the same numbers: each
 * builder here is the shared one with those values as overrides, never a second shape.
 */
import type { Call, RunResult } from "../src/lib/types";
import type { SkillCoverage } from "../src/components/panels/SkillCoveragePanel";
import { call as baseCall, result as baseResult, usage } from "./fixtures";

export { PHONE, SID, pageOverflowX, resolveColour, subagent, usage } from "./fixtures";

/** One call as the panels' jsdom tests pin it: every turn at the same clock, usage and ledger lines. */
export const call = (n: number, over: Partial<Call> = {}): Call =>
  baseCall(n, {
    at: "2026-08-23T07:12:14.549Z",
    usage: usage(),
    tools: [
      { name: "Bash", input: {} },
      { name: "Read", input: {} },
    ],
    text: "",
    thinking: "",
    stop_reason: "tool_use",
    context_tokens: 40_101,
    context_pct: 4.01,
    output_tokens_per_sec: 153.85,
    records: [19, 21, 23, 24, 25, 26, 27, 28, 29],
    results_in: [
      { tool: "Bash", chars: 31, content: "(Bash completed with no output)" },
      { tool: "Bash", chars: 7005, content: "..." },
    ],
    ...over,
  });

export const coverage = (): SkillCoverage => ({
  skill: "mermaidjs-diagrams",
  files: [
    { path: "README.md", kind: "doc", bytes: 4424, ignored: true, loaded: [], run: [] },
    { path: "SKILL.md", kind: "doc", bytes: 9000, ignored: false, loaded: [1], run: [] },
    { path: "resources/contrast_tooling.md", kind: "doc", bytes: 500, ignored: false, loaded: [], run: [] },
    { path: "scripts/mermaid_contrast.ts", kind: "script", bytes: 12_000, ignored: false, loaded: [3], run: [7, 9] },
    { path: "scripts/render_mermaid.sh", kind: "script", bytes: 800, ignored: false, loaded: [], run: [] },
    { path: "scripts/x.test.ts", kind: "test", bytes: 100, ignored: false, loaded: [], run: [] },
  ],
  loaded: ["SKILL.md", "scripts/mermaid_contrast.ts"],
  run: ["scripts/mermaid_contrast.ts"],
  not_loaded: ["resources/contrast_tooling.md", "scripts/render_mermaid.sh", "scripts/x.test.ts"],
  not_run: ["scripts/render_mermaid.sh"],
  summary: { files: 5, ignored: 1, docs: 2, scripts: 2, tests: 1, assets: 0, loaded: 2, run: 1 },
});

/** A Claude sonnet result whose `cost_by_tier` sums to `estimated_cost_usd` and whose ledger matches the envelope except `turns`. */
export const result = (over: Partial<RunResult> = {}): RunResult =>
  baseResult({
    model: "claude-sonnet-5",
    turns: 2,
    usage: usage({
      input_tokens: 32,
      output_tokens: 37_009,
      cache_read_tokens: 1_371_238,
      cache_write_tokens: 95_811,
      cache_write_1h_tokens: 95_811,
      reasoning_tokens: 28_719,
      accumulative_billed_tokens: 1_504_090,
    }),
    calls: [call(1, { records: [1, 2, 3], results_in: [] }), call(2)],
    rates_applied: {
      applied_at: "2026-08-23T11:47:31+00:00",
      cache_read: 2e-7,
      cache_write: 2.5e-6,
      cache_write_1h: 4e-6,
      input: 2e-6,
      model: "claude-sonnet-5",
      output: 1e-5,
      source: "prices.toml",
    },
    tool_calls: { Bash: 10, Edit: 4 },
    record_kinds: { "claude/assistant/tool_use": 22, "claude/user/tool_result": 22, "codex/event_msg/token_count": 3, "claude/made-up": 1 },
    skill_coverage: coverage() as unknown as Record<string, unknown>,
    case: { name: "eval_dual_density" },
    cost_by_tier: { cache_read: 0.274248, cache_write_1h: 0.383244, cache_write_5m: 0, input: 6.4e-5, output: 0.37009 },
    reported_usage: { cache_creation_input_tokens: 95_811, cache_read_input_tokens: 1_371_238, input_tokens: 32, output_tokens: 37_009 },
    reported_model_usage: {
      "claude-haiku-4-5-20251001": { costUSD: 0.001138, inputTokens: 1063, outputTokens: 15, cacheReadInputTokens: 0, cacheCreationInputTokens: 0 },
    },
    ...over,
  });
