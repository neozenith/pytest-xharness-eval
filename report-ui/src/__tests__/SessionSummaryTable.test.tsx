import { fireEvent, screen } from "@testing-library/react";
import { renderT as render } from "./render";
import { cell } from "./cells";
import { TooltipProvider } from "@/components/ui/tooltip";
import { SessionSummaryTable } from "@/components/SessionSummaryTable";
import { NO_MATCH } from "@/lib/facets";
import type { Cell } from "@/lib/types";

const mount = (cells: Cell[]) =>
  render(
    <TooltipProvider>
      <SessionSummaryTable cells={cells} />
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

test("a token figure is abbreviated in the cell and exact on its title, with the window named there too", () => {
  mount([cell({ session_id: "1", peak_context_tokens: 120_245, context_window_pct: 12.02, context_window: 1_000_000 })]);
  // the abbreviation is what the column shows; the precision it gave up is one hover away, and
  // the window label moved to the same place rather than being dropped
  const shown = screen.getByText("120.2k");
  // The gap between a figure and its qualifier is a margin on `.qual`, not a character: an
  // inline-block collapses leading white space, so the markup carries none and jsdom (which
  // applies no stylesheet) sees the two runs adjacent. The spacing is asserted in the e2e pass.
  expect(shown.closest("td")).toHaveTextContent("120.2k· 12.0%");
  expect(shown.closest("span")).toHaveAttribute("title", "120,245 of a 1M window");
});

test("the pass rate is over the runs that carry a verdict, and says how many do not", () => {
  mount([cell({ session_id: "1", verdict: "pass" }), cell({ session_id: "2", verdict: "fail" }), cell({ session_id: "3", verdict: null })]);
  const row = screen.getAllByRole("row")[1]!;
  expect(row).toHaveTextContent("1/2 · 50.0%");
  expect(row).toHaveTextContent("1 no history");
});

test("a null aggregate is the muted glyph, never a zero", () => {
  mount([cell({ session_id: "1", estimated_cost_usd: null, output_tokens_per_sec: null, skill_coverage: {} })]);
  const row = screen.getAllByRole("row")[1]!;
  expect(row).not.toHaveTextContent("$0.0000");
  expect(row.querySelectorAll("td .muted")).not.toHaveLength(0);
  expect(row).toHaveTextContent("–");
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
  mount([
    cell({ session_id: "1", skill: "alpha", case: "eval_a", estimated_cost_usd: 9 }),
    cell({ session_id: "2", skill: "beta", case: "eval_b", estimated_cost_usd: 1 }),
  ]);
  // key order first: alpha before beta, and the change of skill opens a band
  expect(rows().map((r) => r.getAttribute("data-key"))).toEqual(["alpha|eval_a|claude|claude-opus-5", "beta|eval_b|claude|claude-opus-5"]);
  expect(rows()[1]).toHaveAttribute("data-band", "skill");

  const meanCost = document.querySelector<HTMLButtonElement>("#SessionSummaryTable thead th[data-k='cost'] button")!;
  fireEvent.click(meanCost);
  // a fresh measure opens descending — the largest mean first, which is the question being asked
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

test("a head answers to its canonical `mean <field>` name", () => {
  mount([cell({ session_id: "1" })]);
  expect(screen.getByLabelText(/mean accumulative_billed_tokens/)).toBeInTheDocument();
  expect(screen.getByLabelText(/mean wall_ms/)).toBeInTheDocument();
});

test("filtered to nothing the table keeps its id and its head, and says why the body is empty", () => {
  mount([]);
  expect(document.getElementById("SessionSummaryTable")).toBeInTheDocument();
  expect(screen.getAllByRole("columnheader")).not.toHaveLength(0);
  const empty = document.querySelectorAll("td.empty");
  expect(empty).toHaveLength(1);
  expect(empty[0]).toHaveTextContent(NO_MATCH);
});
