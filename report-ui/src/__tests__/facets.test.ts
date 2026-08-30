import { cell, sweep } from "./cells";
import { facetCount, facetOptions, filterCells, toggleFacet } from "@/lib/facets";
import { NO_FACETS } from "@/lib/route";

test("facetOptions is the sweep's distinct values, sorted, with nulls dropped", () => {
  const cells = sweep();
  expect(facetOptions(cells, "skill")).toEqual(["discovery", "mermaidjs-diagrams"]);
  expect(facetOptions(cells, "harness")).toEqual(["claude", "codex"]);
  expect(facetOptions(cells, "model")).toEqual(["claude-opus-5", "claude-sonnet-5", "gpt-5.6-sol", "gpt-5.6-terra"]);
  // a skill-less sweep offers no skill facet at all: null is not an option
  expect(facetOptions([cell({ skill: null })], "skill")).toEqual([]);
});

test("filterCells: null is every value, OR within a facet, AND across facets", () => {
  const cells = sweep();
  expect(filterCells(cells, NO_FACETS)).toHaveLength(cells.length);
  expect(filterCells(cells, { ...NO_FACETS, harness: ["claude"] }).map((c) => c.session_id)).toEqual(["a", "b", "d"]);
  expect(filterCells(cells, { ...NO_FACETS, harness: ["claude", "codex"] })).toHaveLength(6);
  expect(filterCells(cells, { ...NO_FACETS, skill: ["discovery"], harness: ["codex"] }).map((c) => c.session_id)).toEqual(["c"]);
  // models nest under a harness, so this pair is legal, reachable and empty
  expect(filterCells(cells, { ...NO_FACETS, harness: ["claude"], model: ["gpt-5.6-sol"] })).toHaveLength(0);
  // a value the data does not carry selects zero, never everything
  expect(filterCells(cells, { ...NO_FACETS, skill: ["gone"] })).toHaveLength(0);
});

test("a null skill survives only while the skill facet is null", () => {
  const cells = [...sweep(), cell({ session_id: "z", skill: null })];
  expect(filterCells(cells, NO_FACETS)).toHaveLength(7);
  expect(filterCells(cells, { ...NO_FACETS, skill: ["discovery"] }).map((c) => c.session_id)).not.toContain("z");
  expect(filterCells(cells, { ...NO_FACETS, harness: ["claude"] }).map((c) => c.session_id)).toContain("z");
});

test("facetCount cross-filters by the other two facets, never by its own", () => {
  const cells = sweep();
  const facets = { ...NO_FACETS, harness: ["claude"] };
  // claude never ran gpt-5.6-sol: the chip says so rather than disappearing
  expect(facetCount(cells, facets, "model", "gpt-5.6-sol")).toBe(0);
  expect(facetCount(cells, facets, "model", "claude-opus-5")).toBe(2);
  // the harness facet does not filter itself, so codex still reports its own three
  expect(facetCount(cells, facets, "harness", "codex")).toBe(3);
  expect(facetCount(cells, NO_FACETS, "skill", "discovery")).toBe(3);
});

test("toggleFacet adds at the end, removes in place, and clears the facet with its last value", () => {
  const one = toggleFacet(NO_FACETS, "harness", "claude");
  expect(one.harness).toEqual(["claude"]);
  const two = toggleFacet(one, "harness", "codex");
  expect(two.harness).toEqual(["claude", "codex"]);
  expect(toggleFacet(two, "harness", "claude").harness).toEqual(["codex"]);
  expect(toggleFacet(one, "harness", "claude").harness).toBeNull();
  // the other facets are untouched
  expect(toggleFacet(two, "skill", "discovery")).toMatchObject({ harness: ["claude", "codex"], skill: ["discovery"], model: null });
});
