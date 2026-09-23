/**
 * Data and page probes the `panels.*` component specs share. The ledger shapes are the ones
 * `src/__tests__/panels.test.tsx` uses (a real Claude result, a real skill catalogue), so the
 * jsdom tests and these browser tests read the same numbers.
 *
 * Why not `ct/fixtures.ts`: it imports the design-token JSON without an import attribute, and
 * the Node-side test loader refuses that (`needs an import attribute of "type: json"`), so any
 * spec importing it fails to collect. Plain values only here, nothing that pulls JSON.
 */
import type { Page } from "@playwright/test";
import type { Call, RunResult, Subagent, Usage } from "../src/lib/types";
import type { SkillCoverage } from "../src/components/panels/SkillCoveragePanel";

export const SID = "1feb573f-ba51-4e77-845f-12c4bcb08252";

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
  at: "2026-08-23T07:12:14.549Z",
  usage: usage(),
  tools: [
    { name: "Bash", input: {} },
    { name: "Read", input: {} },
  ],
  text: "",
  thinking: "",
  stop_reason: "tool_use",
  latency_ms: 1716,
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

/** A Claude result whose `cost_by_tier` sums to `estimated_cost_usd` and whose ledger matches the envelope except `turns`. */
export const result = (over: Partial<RunResult> = {}): RunResult => ({
  harness: "claude",
  effort: null,
  model: "claude-sonnet-5",
  session_id: SID,
  turns: 2,
  reported_turns: 23,
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
  context_window: 1_000_000,
  peak_context_tokens: 120_245,
  final_context_tokens: 120_631,
  context_window_pct: 12.02,
  final_context_pct: 12.06,
  baseline_tokens: 35_599,
  estimated_cost_usd: 1.027646,
  harness_reported_cost_usd: 1.0287836,
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
  final_text: "Both gates pass clean.",
  files_written: ["ARCHITECTURE.md"],
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

export const subagent = (over: Partial<Subagent> = {}): Subagent => ({
  agent: "Explore",
  id: "abcdef12-3456-7890-abcd-ef1234567890",
  log: "subagents/agent-abcdef12.jsonl",
  parent_turn: 1,
  turns: 1,
  description: "",
  usage: usage({
    input_tokens: 100,
    output_tokens: 50,
    cache_read_tokens: 0,
    cache_write_tokens: 0,
    cache_write_1h_tokens: 0,
    reasoning_tokens: 0,
    accumulative_billed_tokens: 150,
  }),
  calls: [],
  ...over,
});

/** The computed `color` a CSS colour expression resolves to on this page, e.g. `var(--xh-good)`. */
export const resolveColour = (page: Page, expr: string): Promise<string> =>
  page.evaluate((e) => {
    const probe = document.createElement("span");
    probe.style.color = e;
    document.body.append(probe);
    const c = getComputedStyle(probe).color;
    probe.remove();
    return c;
  }, expr);

/** How far the document scrolls sideways: 0 when nothing pushes the page past the viewport. */
export const pageOverflowX = (page: Page): Promise<number> => page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);

/** The phone width the page must hold at without scrolling sideways. */
export const PHONE = { width: 375, height: 800 };
