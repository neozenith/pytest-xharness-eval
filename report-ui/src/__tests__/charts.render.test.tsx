import { render, screen } from "@testing-library/react";
import { ChartAxisToggle, ContextWindowChart, OutputPerTurnChart, TokenAccumulationChart, TokenWaterfallChart, TurnTiersChart } from "@/components/charts";
import type { Cell } from "@/lib/types";
import { result } from "./charts.series.test";

// Recharts' ResponsiveContainer measures itself; jsdom has no layout, so give it a stub observer.
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
beforeAll(() => {
  (globalThis as unknown as { ResizeObserver: typeof ResizeObserverStub }).ResizeObserver = ResizeObserverStub;
});

const cell: Cell = {
  case: "eval_x",
  suite: null,
  skill: null,
  fixture: null,
  prompt: null,
  harness: "claude",
  model: "m",
  session_id: "s",
  verdict: "pass",
  at: null,
  node: null,
  wall_ms: null,
  result: "x/claude-s.result.json",
  log: null,
  estimated_cost_usd: null,
  harness_reported_cost_usd: null,
  rates_applied: {},
  accumulative_billed_tokens: null,
  baseline_tokens: null,
  context_window: null,
  peak_context_tokens: null,
  context_window_pct: null,
  final_context_pct: null,
  ttft_ms: null,
  output_tokens_per_sec: null,
  turns: 3,
  reported_turns: null,
  tool_calls: 0,
  duration_ms: null,
  files_written: [],
  has_ledger: true,
  record_kinds: {},
  skill_coverage: {},
};

test("ChartAxisToggle offers the two axes and reports a change", () => {
  const onChange = vi.fn();
  render(<ChartAxisToggle mode="turn" onChange={onChange} />);
  expect(document.getElementById("ChartAxisToggle")).toHaveAttribute("data-el", "ChartAxisToggle");
  screen.getByRole("radio", { name: "per session-log line" }).click();
  expect(onChange).toHaveBeenCalledWith("line");
});

test("TokenAccumulationChart mounts with its glossary id and one series per ledgered session", () => {
  const { container } = render(<TokenAccumulationChart cells={[cell, { ...cell, session_id: "other", has_ledger: false }]} results={{ s: result }} />);
  expect(document.getElementById("TokenAccumulationChart")).toHaveAttribute("data-el", "TokenAccumulationChart");
  expect(container.querySelector("[data-chart]")).toBeInTheDocument();
  expect(screen.getByText("accumulative_billed_tokens accumulating per turn")).toBeInTheDocument();
});

test("TokenAccumulationChart says so when no session has a ledger", () => {
  render(<TokenAccumulationChart cells={[{ ...cell, has_ledger: false }]} results={{}} />);
  expect(screen.getByText(/No session with a per-call ledger/)).toBeInTheDocument();
});

test("TokenWaterfallChart renders per turn and per line with the legacy note", () => {
  const { rerender } = render(<TokenWaterfallChart result={result} lines={null} mode="turn" />);
  expect(document.getElementById("TokenWaterfallChart")).toBeInTheDocument();
  expect(screen.getByText(/The last bar is accumulative_billed_tokens/)).toBeInTheDocument();
  rerender(<TokenWaterfallChart result={result} lines={null} mode="line" />);
  expect(document.getElementById("TokenWaterfallChart")).toHaveAttribute("data-el", "TokenWaterfallChart");
});

test("ContextWindowChart carries the three note variants", () => {
  const { rerender } = render(<ContextWindowChart result={result} lines={null} mode="turn" />);
  expect(screen.getByText(/Each point is the prompt that turn processed/)).toBeInTheDocument();
  expect(screen.getByText("1.8%")).toBeInTheDocument();
  rerender(<ContextWindowChart result={result} lines={null} mode="line" />);
  expect(screen.getByText(/Per session-log line: the prompt size/)).toBeInTheDocument();
  rerender(<ContextWindowChart result={{ ...result, context_window: null }} lines={null} mode="line" />);
  expect(screen.getByText(/The harness reported no context window/)).toBeInTheDocument();
});

test("OutputPerTurnChart and TurnTiersChart mount under their glossary ids in both axis modes", () => {
  render(<OutputPerTurnChart result={result} lines={null} mode="turn" />);
  render(<TurnTiersChart result={result} lines={null} mode="line" />);
  expect(document.getElementById("OutputPerTurnChart")).toHaveAttribute("data-el", "OutputPerTurnChart");
  expect(document.getElementById("TurnTiersChart")).toHaveAttribute("data-el", "TurnTiersChart");
  expect(screen.getByText("Output and thinking")).toBeInTheDocument();
  expect(screen.getByText("Billing tiers")).toBeInTheDocument();
});
