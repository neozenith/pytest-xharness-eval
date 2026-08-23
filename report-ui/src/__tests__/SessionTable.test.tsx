import { render, screen } from "@testing-library/react";
import { TooltipProvider } from "@/components/ui/tooltip";
import { SessionTable } from "@/components/SessionTable";
import type { Cell } from "@/lib/types";

const cell = (over: Partial<Cell>): Cell => ({
  case: "eval_dual_density",
  suite: "skills/mermaidjs-diagrams/evals/eval_dual_density.py",
  skill: "mermaidjs-diagrams",
  fixture: "complex_diagram",
  prompt: "go",
  harness: "claude",
  model: "claude-sonnet-5",
  session_id: "1feb573f-ba51-4e77-845f-12c4bcb08252",
  verdict: "pass",
  at: "2026-08-23T07:18:05.537Z",
  node: "n",
  wall_ms: 123_456,
  result: "eval_dual_density/claude-1feb573f.result.json",
  log: null,
  estimated_cost_usd: 1.0276,
  harness_reported_cost_usd: 1.0288,
  rates_applied: {},
  accumulative_billed_tokens: 1_504_090,
  baseline_tokens: 22_956,
  context_window: 1_000_000,
  peak_context_tokens: 120_245,
  context_window_pct: 12.02,
  final_context_pct: 12.06,
  ttft_ms: null,
  output_tokens_per_sec: 72,
  turns: 16,
  reported_turns: null,
  tool_calls: 22,
  duration_ms: null,
  files_written: [],
  has_ledger: true,
  record_kinds: {},
  skill_coverage: { files: 18, loaded: 6, scripts: 4, run: 2 },
  ...over,
});

const mount = (cells: Cell[]) =>
  render(
    <TooltipProvider>
      <SessionTable cells={cells} />
    </TooltipProvider>,
  );

test("the billed total and the peak context are two cells, and the context cell names its window", () => {
  mount([cell({})]);
  expect(screen.getByText("1,504,090")).toBeInTheDocument();
  const peak = screen.getByText("120,245").closest("td");
  expect(peak).toHaveTextContent("120,245 · 12.0% of 1M");
  expect(screen.getByRole("button", { name: /accumulative_billed_tokens \(billed\)/ })).toBeInTheDocument();
});

test("skill coverage reads loaded/files · run/scripts and a missing catalogue is a dash", () => {
  mount([cell({}), cell({ session_id: "other", skill_coverage: {} })]);
  expect(screen.getByText("6/18 · 2/4")).toBeInTheDocument();
  expect(screen.getAllByRole("row")).toHaveLength(3);
});

test("rows are sorted newest first and a row links to its session", () => {
  mount([cell({ session_id: "old", at: "2026-01-01T00:00:00Z" }), cell({})]);
  const rows = screen.getAllByRole("row").slice(1);
  expect(rows[0]).toHaveAttribute("data-sid", "1feb573f-ba51-4e77-845f-12c4bcb08252");
  expect(rows[1]).toHaveAttribute("data-sid", "old");
});
