import { fireEvent, screen, within } from "@testing-library/react";
import { renderT as render } from "./render";
import { TooltipProvider } from "@/components/ui/tooltip";
import {
  CostByTierPanel,
  FinalMessagePanel,
  ReconciliationPanel,
  RecordKindsPanel,
  SessionTurnTable,
  SkillCoveragePanel,
  categoryOfKind,
  ranges,
  turnId,
  type SkillCoverage,
} from "@/components/panels";
import type { Call, RunResult, Usage } from "@/lib/types";

const usage = (over: Partial<Usage> = {}): Usage => ({
  input_tokens: 2,
  output_tokens: 264,
  cache_read_tokens: 35_865,
  cache_write_tokens: 4_234,
  cache_write_1h_tokens: 4_234,
  cache_write_5m_tokens: 0,
  reasoning_tokens: 42,
  ...over,
});

const call = (n: number, over: Partial<Call> = {}): Call => ({
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

const coverage: SkillCoverage = {
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
};

const result: RunResult = {
  harness: "claude",
  model: "claude-sonnet-5",
  session_id: "1feb573f-ba51-4e77-845f-12c4bcb08252",
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
  skill_coverage: coverage as unknown as Record<string, unknown>,
  case: { name: "eval_dual_density" },
  cost_by_tier: { cache_read: 0.274248, cache_write_1h: 0.383244, cache_write_5m: 0, input: 6.4e-5, output: 0.37009 },
  reported_usage: { cache_creation_input_tokens: 95_811, cache_read_input_tokens: 1_371_238, input_tokens: 32, output_tokens: 37_009 },
  reported_model_usage: {
    "claude-haiku-4-5-20251001": { costUSD: 0.001138, inputTokens: 1063, outputTokens: 15, cacheReadInputTokens: 0, cacheCreationInputTokens: 0 },
  },
};

const mount = (node: React.ReactNode) => render(<TooltipProvider>{node}</TooltipProvider>);

test("ranges and turnId match the legacy page", () => {
  expect(ranges([1, 2, 3, 5, 7, 8])).toBe("1-3, 5, 7-8");
  expect(ranges([])).toBe("");
  expect(turnId("abc", 3)).toBe("abc/t3");
  expect(categoryOfKind("claude/assistant/tool_use")).toBe("tool_call");
  expect(categoryOfKind("claude/attachment/whatever")).toBe("harness_meta");
  expect(categoryOfKind("nope")).toBe("unknown");
});

test("SessionTurnTable: one row per call, summary hides details, a click opens a turn and the hash records it", () => {
  const onOpenTurn = vi.fn();
  const records = vi.fn((k: Call) => <div id={turnId(result.session_id, k.n)}>records of t{k.n}</div>);
  const { rerender } = mount(
    <SessionTurnTable
      result={result}
      view="summary"
      onViewChange={() => {}}
      openTurn={null}
      onOpenTurn={onOpenTurn}
      recordView="nice"
      renderTurnRecords={records}
    />,
  );
  const table = document.getElementById("SessionTurnTable")!;
  expect(table.querySelectorAll("tr.SessionTurnRow")).toHaveLength(2);
  expect(screen.queryByText("records of t2")).not.toBeInTheDocument();
  const row2 = table.querySelector('tr.SessionTurnRow[data-n="2"]')!;
  expect(row2).toHaveTextContent("1feb573f/t2");
  expect(row2).toHaveTextContent("19, 21, 23-29");
  expect(row2).toHaveTextContent("2 · 7,036 ch");
  expect(row2).toHaveTextContent("40,101");
  expect(row2).toHaveTextContent("4.0%");
  expect(row2).toHaveTextContent("1,716 ms");
  fireEvent.click(row2);
  // the open turn is reported upward; SessionView owns writing it into the hash (lib/route.ts)
  expect(onOpenTurn).toHaveBeenCalledWith(2);
  rerender(
    <TooltipProvider>
      <SessionTurnTable
        result={result}
        view="summary"
        onViewChange={() => {}}
        openTurn={2}
        onOpenTurn={onOpenTurn}
        recordView="nice"
        renderTurnRecords={records}
      />
    </TooltipProvider>,
  );
  expect(screen.getByText("records of t2")).toBeInTheDocument();
  expect(document.getElementById(turnId(result.session_id, 2))).toBeInTheDocument();
  rerender(
    <TooltipProvider>
      <SessionTurnTable
        result={result}
        view="detailed"
        onViewChange={() => {}}
        openTurn={null}
        onOpenTurn={onOpenTurn}
        recordView="nice"
        renderTurnRecords={records}
      />
    </TooltipProvider>,
  );
  expect(screen.getByText("records of t1")).toBeInTheDocument();
  expect(screen.getByText("records of t2")).toBeInTheDocument();
  expect(document.getElementById("ViewToggle")).toBeInTheDocument();
});

test("SessionTurnTable without a ledger says so", () => {
  mount(<SessionTurnTable result={{ ...result, calls: [] }} view="summary" onViewChange={() => {}} openTurn={null} onOpenTurn={() => {}} recordView="nice" />);
  expect(screen.getByText(/no per-turn ledger/)).toBeInTheDocument();
});

test("SkillCoveragePanel: summary chips, ignored files hidden until ShowIgnored, chips filter the table", () => {
  mount(<SkillCoveragePanel coverage={coverage} />);
  const summary = document.getElementById("SkillCoverageSummary")!;
  expect(summary).toHaveTextContent("mermaidjs-diagrams");
  expect(within(summary).getByText("not_loaded").parentElement).toHaveTextContent("3");
  const table = document.getElementById("SkillCoveragePanel")!;
  expect(table.querySelectorAll("tbody tr")).toHaveLength(5);
  expect(screen.queryByText("README.md")).not.toBeInTheDocument();
  fireEvent.click(document.getElementById("ShowIgnored")!);
  expect(table.querySelectorAll("tbody tr")).toHaveLength(6);
  expect(screen.getByText("README.md").closest("tr")).toHaveTextContent("ignored");
  fireEvent.click(within(summary).getByText("not_run").closest("button")!);
  expect(table.querySelectorAll("tbody tr")).toHaveLength(1);
  expect(table).toHaveTextContent("scripts/render_mermaid.sh");
  expect(table).toHaveTextContent("not run · not loaded");
  fireEvent.click(within(summary).getByText("run").closest("button")!);
  expect(table.querySelectorAll("tbody tr")).toHaveLength(1);
  expect(table).toHaveTextContent("scripts/mermaid_contrast.ts");
  expect(table).toHaveTextContent("t7");
});

test("SkillCoveragePanel without a catalogue points at the replay", () => {
  mount(<SkillCoveragePanel coverage={{}} />);
  expect(screen.getByText(/no skill coverage on this result/)).toBeInTheDocument();
});

test("RecordKindsPanel: one chip per kind with its count and a category-coloured pill", () => {
  mount(<RecordKindsPanel recordKinds={result.record_kinds} />);
  const panel = document.getElementById("RecordKindsPanel")!;
  expect(panel.querySelectorAll("span[title]")).toHaveLength(4);
  const pill = within(panel).getByText("claude/assistant/tool_use");
  expect(pill).toHaveAttribute("title", "tool_call");
  expect(pill.style.background).toBe("var(--xh-category-tool_call)");
  expect(pill.parentElement).toHaveTextContent("22");
  expect(within(panel).getByText("claude/made-up")).toHaveAttribute("title", "unknown");
});

test("CostByTierPanel: tiers, the estimate, the harness per-model line, and the rates block", () => {
  mount(<CostByTierPanel result={result} />);
  const cost = document.getElementById("CostByTierPanel")!;
  expect(cost).toHaveTextContent("cache_read");
  expect(cost).toHaveTextContent("$0.2742");
  expect(cost).toHaveTextContent("estimated_cost_usd");
  expect(cost).toHaveTextContent("$1.0276");
  expect(cost).toHaveTextContent("harness estimate · claude-haiku-4-5-20251001");
  expect(cost).toHaveTextContent("1,063 in · 15 out");
  expect(cost).toHaveTextContent("harness_reported_cost_usd");
  const rates = document.getElementById("RatesApplied")!;
  expect(rates).toHaveTextContent("claude-sonnet-5");
  expect(rates).toHaveTextContent("prices.toml");
  expect(rates).toHaveTextContent("$2.000 /M");
  expect(rates).toHaveTextContent("$0.200 /M");
  expect(rates).toHaveTextContent("$4.000 /M");
});

test("CostByTierPanel on a result from before the ledger points at the replay", () => {
  mount(<CostByTierPanel result={{ ...result, cost_by_tier: undefined, rates_applied: {}, reported_model_usage: undefined }} />);
  expect(screen.getByText(/no cost_by_tier/)).toBeInTheDocument();
  expect(screen.getByText(/no rates_applied/)).toBeInTheDocument();
});

test("ReconciliationPanel: ledger vs harness with = and Δ, the billed sum beside the vendor's total_tokens", () => {
  mount(<ReconciliationPanel result={result} />);
  const panel = document.getElementById("ReconciliationPanel")!;
  const row = (label: string) => within(panel).getByText(label).closest("tr")!;
  expect(row("input (uncached)")).toHaveTextContent("32");
  expect(row("input (uncached)").querySelectorAll("td")[3]).toHaveTextContent("=");
  expect(row("turns (model calls)")).toHaveTextContent("Δ 21");
  expect(row("accumulative_billed_tokens")).toHaveTextContent("1,504,090");
  expect(row("estimated / harness reported cost")).toHaveTextContent("Δ $0.0011");
});

test("ReconciliationPanel splits a spawning run: tier rows show the primary share, the subagents' bill is its own row", () => {
  const withSub: RunResult = {
    ...result,
    // the whole bill: the fixture usage plus the spawned thread's 100 input / 50 output
    usage: usage({ input_tokens: 132, output_tokens: 314, accumulative_billed_tokens: undefined }),
    subagents: [
      {
        agent: "Explore",
        id: "abc",
        log: "subagents/agent-abc.jsonl",
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
      },
    ],
  };
  mount(<ReconciliationPanel result={withSub} />);
  const panel = document.getElementById("ReconciliationPanel")!;
  const row = (label: string) => within(panel).getByText(label).closest("tr")!;
  // primary share = whole bill minus the thread's tiers, so the harness comparison still holds
  expect(row("input (uncached)")).toHaveTextContent("32");
  expect(row("output")).toHaveTextContent("264");
  const subRow = row("subagents (1 spawned thread)");
  expect(subRow).toHaveTextContent("150");
  expect(subRow).toHaveTextContent("not in the harness figure");
});

test("ReconciliationPanel on Codex subtracts cached from the vendor's inclusive input", () => {
  const codex = {
    ...result,
    harness: "codex",
    reported_usage: { input_tokens: 517_418, cached_input_tokens: 471_552, output_tokens: 10_383, reasoning_output_tokens: 3006, total_tokens: 527_801 },
  };
  mount(<ReconciliationPanel result={codex} />);
  const panel = document.getElementById("ReconciliationPanel")!;
  expect(within(panel).getByText("input (uncached)").closest("tr")).toHaveTextContent("45,866");
  expect(within(panel).getByText("accumulative_billed_tokens").closest("tr")).toHaveTextContent("527,801");
});

test("FinalMessagePanel shows the text or (empty)", () => {
  mount(<FinalMessagePanel text={result.final_text} />);
  expect(document.getElementById("FinalMessage")).toHaveTextContent("Both gates pass clean.");
  mount(<FinalMessagePanel text="" />);
  expect(screen.getByText("(empty)")).toBeInTheDocument();
});
