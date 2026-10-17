import { fireEvent, screen } from "@testing-library/react";
import { renderT as render } from "./render";
import { cell } from "./cells";
import { TooltipProvider } from "@/components/ui/tooltip";
import { SessionSummaryTable } from "@/components/SessionSummaryTable";
import { NO_MATCH } from "@/lib/facets";
import type { Cell, ImportantMetricsDoc } from "@/lib/types";
import { aggregated, doc } from "./metricsDoc";

const mount = (cells: Cell[], metrics: ImportantMetricsDoc = doc()) =>
  render(
    <TooltipProvider>
      <SessionSummaryTable cells={cells} metrics={metrics} />
    </TooltipProvider>,
  );

test("one row per group, in key order, keyed by the group", () => {
  mount([
    cell({ session_id: "1", skill: "mermaidjs-diagrams", case: "eval_b", harness: "codex", model: "gpt-5.6-sol" }),
    cell({ session_id: "2", skill: "discovery", case: "eval_a", harness: "claude", model: "claude-opus-5" }),
    cell({ session_id: "3", skill: "discovery", case: "eval_a", harness: "claude", model: "claude-opus-5" }),
  ]);
  const rows = screen.getAllByRole("row").slice(1);
  expect(rows.map((r) => r.getAttribute("data-key"))).toEqual(["discovery|eval_a|claude|claude-opus-5", "mermaidjs-diagrams|eval_b|codex|gpt-5.6-sol"]);
  expect(rows[0]).toHaveTextContent("2");
});

test("a metric prints its headline in the cell and spells out every aggregate on its title", () => {
  const c = cell({ session_id: "1" });
  mount([c], doc(aggregated(c, { tokens: { median: 120_245, p25: 100_000, p75: 150_000, n: 3 } }, 3)));
  // the median is what the column shows; the spread it summarises is one hover away
  const shown = screen.getByText("120.2k");
  expect(shown).toHaveAttribute("title", "median 120.2k · p25 100.0k · p75 150.0k · n 3");
});

test("the pass rate is passes over samples, and the samples cell says how many sessions were not graded", () => {
  const sessions = [cell({ session_id: "1", verdict: "pass" }), cell({ session_id: "2", verdict: "fail" }), cell({ session_id: "3", verdict: null })];
  mount(sessions, doc(aggregated(sessions[0]!, { verdict: { pass_rate: 0.5, ci_low: 0.09, ci_high: 0.91, n: 2 } }, 2)));
  const row = screen.getAllByRole("row")[1]!;
  expect(row).toHaveTextContent("2 · 1 not graded");
  const rate = screen.getByText("1/2");
  // a cell that did not pass clean is the one the reader must not miss
  expect(rate).toHaveClass("bad");
  expect(rate.closest("[title]")).toHaveAttribute("title", "pass rate 50.0% · 95% CI low 9.0% · 95% CI high 91.0% · n 2");
});

test("a cell with no aggregates, or an aggregate no sample carried, is the muted glyph, never a zero", () => {
  const c = cell({ session_id: "1" });
  mount([c], doc(aggregated(c, { cost: { median: null, p25: null, p75: null, n: 0 } }, 1)));
  const row = screen.getAllByRole("row")[1]!;
  expect(row).not.toHaveTextContent("$0.000");
  expect(row.querySelectorAll("td .muted").length).toBeGreaterThan(10);
  expect(row).toHaveTextContent("–");
});

test("every declared metric is a column, in declaration order, after the samples rule", () => {
  mount([cell({ session_id: "1" })]);
  const heads = [...document.querySelectorAll("#SessionSummaryTable thead th")].map((th) => th.getAttribute("data-k"));
  const metrics = doc().metrics.map((m) => m.id);
  expect(heads.slice(heads.indexOf("samples") + 1)).toEqual(metrics);
});

test("every head is a sort, and its definition reaches a screen reader without costing a tab stop", () => {
  mount([cell({ session_id: "1" })]);
  const heads = [...document.querySelectorAll("#SessionSummaryTable thead th")];
  expect(heads).not.toHaveLength(0);
  for (const th of heads) {
    const button = th.querySelector("button")!;
    expect(button.tabIndex).toBe(0);
    // it promises a sort and it is one: the arrow says which way a click would leave the column
    expect(th).toHaveAttribute("aria-sort", "none");
    expect(th.querySelector(".sort-ico")).not.toBeNull();
    /*
     * The definition is described-by rather than tooltip-only. Tamagui's Tooltip opens on
     * pointer events, so a keyboard reader who tabbed here got a focus ring and nothing else
     * (WCAG 2.1.1) — and these heads are the only place `mean output_tokens_per_sec` and its
     * siblings are spelled out. The hidden span is announced with the button's own name and is
     * not itself focusable.
     */
    const described = document.getElementById(button.getAttribute("aria-describedby")!)!;
    expect(described).toHaveClass("sr-only");
    expect(described.textContent).toContain("—");
    expect(described.querySelector("[tabindex], button, a")).toBeNull();
  }
});

test("a head click sorts on ssort/sdir, and the fixed-order banding switches off when it does", () => {
  const rows = () => [...document.querySelectorAll("#SessionSummaryTable tbody tr")];
  const alpha = cell({ session_id: "1", skill: "alpha", case: "eval_a" });
  const beta = cell({ session_id: "2", skill: "beta", case: "eval_b" });
  mount([alpha, beta], doc(aggregated(alpha, { cost: { median: 9, p25: 9, p75: 9, n: 1 } }), aggregated(beta, { cost: { median: 1, p25: 1, p75: 1, n: 1 } })));
  // key order first: alpha before beta, and the change of skill opens a band
  expect(rows().map((r) => r.getAttribute("data-key"))).toEqual(["alpha|eval_a|claude|claude-opus-5", "beta|eval_b|claude|claude-opus-5"]);
  expect(rows()[1]).toHaveAttribute("data-band", "skill");

  const meanCost = document.querySelector<HTMLButtonElement>("#SessionSummaryTable thead th[data-k='cost'] button")!;
  fireEvent.click(meanCost);
  // a fresh measure opens descending — the costliest cell first, which is the question being asked
  expect(location.search).toContain("ssort=cost&sdir=desc");
  expect(rows().map((r) => r.getAttribute("data-key"))).toEqual(["alpha|eval_a|claude|claude-opus-5", "beta|eval_b|claude|claude-opus-5"]);
  // and the banding is gone: under any other order "the row above" is whatever was last clicked
  expect(rows()[1]).not.toHaveAttribute("data-band");

  fireEvent.click(meanCost);
  expect(location.search).toContain("ssort=cost&sdir=asc");
  expect(rows().map((r) => r.getAttribute("data-key"))).toEqual(["beta|eval_b|claude|claude-opus-5", "alpha|eval_a|claude|claude-opus-5"]);
});

test("the scroll box is a labelled region, because no row in the table is focusable", () => {
  mount([cell({ session_id: "1" })]);
  const table = document.getElementById("SessionSummaryTable")!;
  // no row navigates anywhere, so no row is a tab stop — unlike `SessionTable`'s
  expect(table.querySelectorAll("tbody :is([tabindex], a[href], button)")).toHaveLength(0);
  // ...which leaves the box itself as the only way to reach the columns past the clipped edge
  const box = table.closest(".table-scroll")!;
  expect(box).toHaveAttribute("role", "region");
  expect(box).toHaveAttribute("aria-label", "Summary table, scrollable");
  // and the ring is carried by an unmasked wrapper: the box masks its own left and right edges
  expect(box.parentElement).toHaveClass("table-scroll-ring");
});

test("a head answers to its headline's operation and the field it reduces", () => {
  mount([cell({ session_id: "1" })]);
  expect(screen.getByLabelText(/median accumulative_billed_tokens/)).toBeInTheDocument();
  expect(screen.getByLabelText(/median wall_ms/)).toBeInTheDocument();
  expect(screen.getByLabelText(/mean skill_files_loaded \/ skill_files/)).toBeInTheDocument();
  expect(screen.getByLabelText(/pass rate verdict/)).toBeInTheDocument();
});

test("filtered to nothing the table keeps its id and its head, and says why the body is empty", () => {
  mount([]);
  expect(document.getElementById("SessionSummaryTable")).toBeInTheDocument();
  expect(screen.getAllByRole("columnheader")).not.toHaveLength(0);
  const empty = document.querySelectorAll("td.empty");
  expect(empty).toHaveLength(1);
  expect(empty[0]).toHaveTextContent(NO_MATCH);
});

test("a control and its treated twin are two adjacent rows, the control first and named (ADR 0055)", () => {
  history.replaceState(null, "", "/");
  mount([
    cell({ session_id: "1", treatment: "lean-ci", estimated_cost_usd: 2 }),
    cell({ session_id: "2", treatment: null, estimated_cost_usd: 4 }),
    cell({ session_id: "3", treatment: null, estimated_cost_usd: 6 }),
  ]);
  const rows = screen.getAllByRole("row").slice(1);
  expect(rows.map((r) => r.getAttribute("data-key"))).toEqual(["discovery|eval_case|claude|claude-opus-5", "discovery|eval_case|claude|claude-opus-5+lean-ci"]);
  const heads = [...document.querySelectorAll("#SessionSummaryTable thead th")].map((th) => th.getAttribute("data-k"));
  expect(heads.indexOf("treatment")).toBe(heads.indexOf("effort") + 1);
  const at = heads.indexOf("treatment");
  expect(rows[0]!.querySelectorAll("td")[at]).toHaveTextContent("control");
  expect(rows[1]!.querySelectorAll("td")[at]).toHaveTextContent("lean-ci");
});

test("an untreated sweep's summary has no treatment column", () => {
  mount([cell({ session_id: "1" }), cell({ session_id: "2", harness: "codex" })]);
  expect([...document.querySelectorAll("#SessionSummaryTable thead th")].map((th) => th.getAttribute("data-k"))).not.toContain("treatment");
});
