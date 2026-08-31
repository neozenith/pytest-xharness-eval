import { cleanup, fireEvent, screen } from "@testing-library/react";
import { renderT as render } from "./render";
import { TooltipProvider } from "@/components/ui/tooltip";
import { SessionTable } from "@/components/SessionTable";
import { NO_MATCH } from "@/lib/facets";
import type { Cell } from "@/lib/types";

const cell = (over: Partial<Cell>): Cell => ({
  case: "eval_dual_density",
  suite: "skills/mermaidjs-diagrams/evals/eval_dual_density.py",
  skill: "mermaidjs-diagrams",
  fixture: "complex_diagram",
  task: "go",
  prompt: "/mermaidjs-diagrams go",
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

test("the billed total and the peak context are two cells, abbreviated in the cell and exact on the title", () => {
  mount([cell({})]);
  // the column budget spends its width on the figures, not on their thousands separators; the
  // precision is on the title, so nothing is lost — only moved
  expect(screen.getByText("1.5M")).toHaveAttribute("title", "1,504,090");
  const peak = screen.getByText("120.2k");
  // The gap between a figure and its qualifier is a margin on `.qual`, not a character: an
  // inline-block collapses leading white space, so the markup carries none and jsdom (which
  // applies no stylesheet) sees the two runs adjacent. The spacing is asserted in the e2e pass.
  expect(peak.closest("td")).toHaveTextContent("120.2k· 12.0%");
  // baseline_tokens lost its own column and lives here, beside the context quantity a reader
  // reaches for it next to — the same "move the precision to the title" trade as the figures
  expect(peak.closest("span")).toHaveAttribute("title", "120,245 of a 1M window · from a baseline_tokens of 22,956");
  expect(screen.getByRole("button", { name: /accumulative_billed_tokens \(billed\)/ })).toBeInTheDocument();
});

test("the column budget: no session id, one cost column, and short case and model names", () => {
  mount([cell({})]);
  const keys = [...document.querySelectorAll("#SessionTable thead th")].map((th) => th.getAttribute("data-k"));
  // the id identified a row without telling you anything about it, and the row opens the session
  // that prints it beside a CopyId; `data-sid` still carries it for anyone reading the DOM
  expect(keys).not.toContain("session_id");
  expect(document.querySelector("#SessionTable tbody tr")).toHaveAttribute("data-sid", "1feb573f-ba51-4e77-845f-12c4bcb08252");
  // one cost column, not two: the estimate is the value and the CLI's own figure is the drift
  expect(keys).toContain("estimated_cost_usd");
  expect(keys).not.toContain("harness_reported_cost_usd");
  // three decimals in this table, not four: a tenth of a cent is below the resolution anyone
  // ranks a sweep by, and the fourth digit was the widest glyph in the densest column
  const cost = screen.getByText("$1.028").closest("td")!;
  expect(cost).toHaveTextContent("$1.028+0.1%");
  // the prefixes every row shares are dropped from the ink and kept on the title
  expect(screen.getByText("dual_density")).toHaveAttribute("title", expect.stringContaining("eval_dual_density"));
  expect(screen.getByText("sonnet-5")).toHaveAttribute("title", "claude-sonnet-5");
});

test("an abbreviated head still answers to the canonical field name", () => {
  mount([cell({})]);
  // WCAG 2.5.3: what you can say has to be what you can see, so `tools` accepts `tool_calls`
  expect(screen.getByRole("button", { name: "tools — tool_calls" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "peak ctx — peak_context_tokens" })).toBeInTheDocument();
});

test("skill coverage reads loaded/files · run/scripts and a missing catalogue is a dash", () => {
  mount([cell({}), cell({ session_id: "other", skill_coverage: {} })]);
  expect(screen.getByText("6/18 · 2/4")).toBeInTheDocument();
  expect(screen.getAllByRole("row")).toHaveLength(3);
});

test("skill coverage sorts on the share it prints, not on the raw loaded count", () => {
  // Two skills, two catalogue sizes: sorting on `loaded` put 6/18 (33%) above 5/5 (100%).
  history.replaceState(null, "", "/?sort=coverage&dir=desc");
  try {
    mount([
      cell({ session_id: "third-of-eighteen", skill_coverage: { files: 18, loaded: 6, scripts: 4, run: 2 } }),
      cell({ session_id: "all-five", skill_coverage: { files: 5, loaded: 5, scripts: 2, run: 2 } }),
      cell({ session_id: "no-catalogue", skill_coverage: {} }),
    ]);
    const order = screen
      .getAllByRole("row")
      .slice(1)
      .map((r) => r.getAttribute("data-sid"));
    expect(order).toEqual(["all-five", "third-of-eighteen", "no-catalogue"]);
  } finally {
    history.replaceState(null, "", "/");
  }
});

test("rows are sorted newest first and a row links to its session", () => {
  mount([cell({ session_id: "old", at: "2026-01-01T00:00:00Z" }), cell({})]);
  const rows = screen.getAllByRole("row").slice(1);
  expect(rows[0]).toHaveAttribute("data-sid", "1feb573f-ba51-4e77-845f-12c4bcb08252");
  expect(rows[1]).toHaveAttribute("data-sid", "old");
});

test("filtered to nothing the header survives and the body says why it is empty", () => {
  mount([]);
  expect(document.getElementById("SessionTable")).toBeInTheDocument();
  expect(screen.getAllByRole("columnheader")).not.toHaveLength(0);
  const empty = document.querySelectorAll("td.empty");
  expect(empty).toHaveLength(1);
  expect(empty[0]).toHaveTextContent(NO_MATCH);
});

test("a sort click preserves the reader's filter instead of silently clearing it", () => {
  history.replaceState(null, "", "/?skill=discovery&harness=claude,codex");
  try {
    mount([cell({})]);
    fireEvent.click(screen.getByRole("button", { name: /turns/ }));
    expect(location.search).toContain("sort=turns");
    expect(location.search).toContain("dir=asc");
    expect(location.search).toContain("skill=discovery");
    expect(location.search).toContain("harness=claude,codex");
  } finally {
    history.replaceState(null, "", "/");
  }
});

test("an identity column that is the same on every row collapses into the caption", () => {
  const cols = () => [...document.querySelectorAll("#SessionTable thead th")].map((th) => th.getAttribute("data-k"));
  // two harnesses: that column is carrying information, so it stays and the caption never names it
  mount([cell({ session_id: "1" }), cell({ session_id: "2", harness: "codex", model: "gpt-5.6-sol" })]);
  expect(cols()).toContain("harness");
  expect(cols()).toContain("model");
  expect(document.querySelector("#SessionTable caption")).not.toHaveTextContent("harness");
  cleanup();

  /*
   * One harness: the column is a fact about the table rather than about a row, so it is stated
   * once above it and the width goes back to the data. This is the common case under a filter.
   */
  mount([cell({ session_id: "1" }), cell({ session_id: "2" })]);
  expect(cols()).not.toContain("harness");
  expect(cols()).not.toContain("model");
  const caption = document.querySelector("#SessionTable caption")!;
  expect(caption).toHaveTextContent("harness claude");
  // the caption prints the same short model name the column would have
  expect(caption).toHaveTextContent("model sonnet-5");
  // every remaining head still has a body cell under it
  expect(document.querySelectorAll("#SessionTable tbody tr")[0]!.querySelectorAll("td")).toHaveLength(cols().length);
});

test("one row is not 'every row agrees': nothing collapses out of a single-row table", () => {
  // collapsing four columns out of a one-row table would leave a caption where the data should be
  mount([cell({})]);
  expect(document.querySelector("#SessionTable caption")).toBeNull();
  expect([...document.querySelectorAll("#SessionTable thead th")].map((th) => th.getAttribute("data-k"))).toContain("harness");
});
