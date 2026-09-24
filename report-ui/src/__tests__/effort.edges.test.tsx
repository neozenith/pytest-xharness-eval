/**
 * The effort axis at its edges (ADR 0049): a third harness's rungs, a capture written before the
 * axis existed (no `effort` key at all, or the empty string ADR 0049 allows), and the pairing of
 * the summary with the chart above it (ADR 0042).
 */
import { cleanup, screen } from "@testing-library/react";
import { renderT as render } from "./render";
import { cell } from "./cells";
import { TooltipProvider } from "@/components/ui/tooltip";
import { SessionSummaryTable } from "@/components/SessionSummaryTable";
import { SessionTable } from "@/components/SessionTable";
import { loadIndex } from "@/lib/data";
import { compareEffort, effortSortValue } from "@/lib/effort";
import { facetOptions, filterCells } from "@/lib/facets";
import { enumeratePermutations, assertUniqueSlugs } from "@/lib/permutations";
import { parseSearch } from "@/lib/route";
import { accumulationGroups } from "@/lib/series";
import { summaryRows } from "@/lib/summary";
import type { Cell, Index, InlineData } from "@/lib/types";

afterEach(() => {
  cleanup();
  history.replaceState(null, "", "/");
  delete window.__XH_DATA__;
});

/** A cell exactly as a pre-ADR 0049 `index.json` row reads: the key is absent, not null. */
const preAxis = (over: Partial<Cell>): Cell => {
  const c = cell(over) as Partial<Cell>;
  delete c.effort;
  return c as Cell;
};

const ledger = { calls: [{ n: 1, usage: { input_tokens: 1, cache_read_tokens: 0, cache_write_tokens: 0, output_tokens: 0 } }] } as never;

describe("ordering", () => {
  test("a table's sort value ranks every rung the way compareEffort does, unknown rungs included", () => {
    // `ultra` and `turbo` are a third harness's ladder: after every known rung, lexically among
    // themselves — which is the order the chips print, so the table must agree with them.
    const rungs = ["ultra", "max", "turbo", "low", "alpha", null];
    const byValue = [...rungs].sort((a, b) => {
      const x = effortSortValue(a);
      const y = effortSortValue(b);
      if (x == null || y == null) return x == null ? (y == null ? 0 : 1) : -1;
      return x < y ? -1 : x > y ? 1 : 0;
    });
    expect(byValue).toEqual([...rungs].sort(compareEffort));
    expect(byValue).toEqual(["low", "max", "alpha", "turbo", "ultra", null]);
  });

  test("SessionTable sorted by effort puts two unknown rungs in chip order, both directions", () => {
    const cells = [cell({ session_id: "u", effort: "ultra" }), cell({ session_id: "t", effort: "turbo" }), cell({ session_id: "l", effort: "low" })];
    const column = () => [...document.querySelectorAll("#SessionTable tbody td[data-k='effort']")].map((td) => td.textContent);
    history.replaceState(null, "", "/?sort=effort&dir=asc");
    render(
      <TooltipProvider>
        <SessionTable cells={cells} />
      </TooltipProvider>,
    );
    expect(column()).toEqual(["low", "turbo", "ultra"]);
    expect(facetOptions(cells, "effort")).toEqual(["low", "turbo", "ultra"]);
    cleanup();
    history.replaceState(null, "", "/?sort=effort&dir=desc");
    render(
      <TooltipProvider>
        <SessionTable cells={cells} />
      </TooltipProvider>,
    );
    expect(column()).toEqual(["ultra", "turbo", "low"]);
  });

  test("SessionSummaryTable sorted by effort descending reverses two unknown rungs too", () => {
    const cells = [cell({ session_id: "u", effort: "ultra" }), cell({ session_id: "t", effort: "turbo" })];
    history.replaceState(null, "", "/?ssort=effort&sdir=desc");
    render(
      <TooltipProvider>
        <SessionSummaryTable cells={cells} />
      </TooltipProvider>,
    );
    const i = [...document.querySelectorAll("#SessionSummaryTable thead th")].findIndex((th) => th.getAttribute("data-k") === "effort");
    const column = [...document.querySelectorAll("#SessionSummaryTable tbody tr[data-key]")].map((tr) => tr.children[i]!.textContent);
    expect(column).toEqual(["ultra", "turbo"]);
  });

  test("a missing rung and a null rung are the same no-rung: the comparator is symmetric", () => {
    expect(compareEffort(null, undefined as unknown as null)).toBe(0);
    expect(compareEffort(undefined as unknown as null, null)).toBe(0);
  });
});

describe("a capture from before the axis", () => {
  test("the index reader hands every consumer `null` for an absent key or the empty string", async () => {
    const cells = [preAxis({ session_id: "old" }), cell({ session_id: "blank", effort: "" }), cell({ session_id: "hi", effort: "high" })];
    window.__XH_DATA__ = { index: { generated_at: "", captured: "", inline: true, cells }, results: {}, logs: {} } as unknown as InlineData;
    const loaded: Index = await loadIndex();
    expect(loaded.cells.map((c) => c.effort)).toEqual([null, null, "high"]);
    // so the empty string never becomes a blank chip, and never an unknown rung
    expect(facetOptions(loaded.cells, "effort")).toEqual(["high"]);
  });

  test("an absent key never prints `undefined` in either table, and keeps the pre-axis group key", () => {
    const cells = [preAxis({ session_id: "a" }), preAxis({ session_id: "b", harness: "codex", model: "gpt-5.6-sol" })];
    render(
      <TooltipProvider>
        <SessionSummaryTable cells={cells} />
        <SessionTable cells={cells} />
      </TooltipProvider>,
    );
    expect(document.body.textContent).not.toMatch(/undefined|null/);
    expect(summaryRows(cells).map((r) => r.key)).toEqual(["discovery|eval_case|claude|claude-opus-5", "discovery|eval_case|codex|gpt-5.6-sol"]);
    expect(screen.getAllByRole("row", { name: /claude\/claude-opus-5 · pass$/ })).toHaveLength(1);
  });
});

describe("the summary is the chart's own partition (ADR 0042)", () => {
  const results = (cells: Cell[]) => Object.fromEntries(cells.map((c) => [c.session_id, ledger]));

  test("two cases of one suite are two summary rows and two chart lines", () => {
    const cells = [cell({ session_id: "1", case: "eval_one" }), cell({ session_id: "2", case: "eval_two" })];
    const groups = accumulationGroups(cells, results(cells));
    expect(groups).toHaveLength(summaryRows(cells).length);
    // and a reader can tell the two lines apart
    expect(new Set(groups.map((g) => g.label)).size).toBe(groups.length);
  });

  test("one suite basename under two skills is two summary rows and two chart lines", () => {
    const cells = [
      cell({ session_id: "1", skill: "discovery", suite: "skills/discovery/evals/eval_case.py" }),
      cell({ session_id: "2", skill: "mermaid", suite: "skills/mermaid/evals/eval_case.py" }),
    ];
    const groups = accumulationGroups(cells, results(cells));
    expect(groups).toHaveLength(summaryRows(cells).length);
    expect(new Set(groups.map((g) => g.label)).size).toBe(groups.length);
  });

  test("an absent rung, a null rung and a rung partition the same way on both sides", () => {
    const cells = [preAxis({ session_id: "1" }), cell({ session_id: "2", effort: null }), cell({ session_id: "3", effort: "low" })];
    const groups = accumulationGroups(cells, results(cells));
    expect(groups.map((g) => g.runs)).toEqual([1, 2]);
    expect(summaryRows(cells).map((r) => r.runs)).toEqual([1, 2]);
  });
});

describe("the deeplink matrix covers the effort param", () => {
  const cells = [
    cell({ session_id: "a1111111", harness: "claude", model: "claude-opus-5", effort: "max" }),
    cell({ session_id: "b2222222", harness: "codex", model: "gpt-5.6-sol", effort: "low" }),
    cell({ session_id: "c3333333", harness: "codex", model: "gpt-5.6-sol", effort: null }),
  ];
  const perms = enumeratePermutations({ generated_at: "", captured: "", inline: false, cells }, {}, "medium");

  test("a single-rung filter, in ladder order", () => {
    assertUniqueSlugs(perms);
    expect(perms.find((p) => p.slug === "overview--filter-effort-low")?.search).toBe("?effort=low");
  });

  test("an effort empty state: a harness × rung pair no session matches", () => {
    const none = perms.find((p) => p.slug === "overview--filter-none-effort");
    expect(none?.search).toBe("?harness=claude&effort=low");
    const route = parseSearch(none!.search);
    expect(route.view === "overview" && filterCells(cells, route.facets)).toHaveLength(0);
  });

  test("each rung of one arm is its own medium-tier session, the slug naming the rung", () => {
    expect(perms.map((p) => p.slug)).toEqual(expect.arrayContaining(["eval-case--codex-gpt-5-6-sol-low--b2222222", "eval-case--codex-gpt-5-6-sol--c3333333"]));
  });
});
