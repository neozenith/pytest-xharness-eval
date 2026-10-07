/** The model catalogue on the page (ADR 0057): the wire fold, the tier facet, its route param and its permutation. */
import { cell } from "./cells";
import { catalogueNote, compareTier, lineOf, releasedOf, tierBadge, tierLabel, tierOf } from "@/lib/catalogue";
import { fromWire } from "@/lib/data";
import { facetCount, facetLabel, facetOptions, filterCells, toggleFacet } from "@/lib/facets";
import { assertUniqueSlugs, enumeratePermutations } from "@/lib/permutations";
import { NO_FACETS, overviewSearch, parseSearch, routeSearch } from "@/lib/route";
import { groupKey, summaryRows } from "@/lib/summary";
import type { Cell, Index } from "@/lib/types";

const index = (cells: Cell[]): Index => ({ generated_at: "", captured: "", inline: false, cells });

/** Two providers' tier 3 models, a tier 1, a tier 4, and one session captured before the catalogue. */
const lineup = (): Cell[] => [
  cell({ session_id: "opus", harness: "claude", model: "claude-opus-5", line: "opus", family_tier: 3, released: "2026-05-14" }),
  cell({ session_id: "sol", harness: "codex", model: "gpt-5.6-sol", line: "sol", family_tier: 3, released: "2026-06-10" }),
  cell({ session_id: "haiku", harness: "claude", model: "claude-haiku-5", line: "haiku", family_tier: 1, released: "2026-03-01" }),
  cell({ session_id: "astra", harness: "codex", model: "gpt-5.6-astra", line: "astra", family_tier: 4, released: "2026-07-01" }),
  cell({ session_id: "old", harness: "claude", model: "claude-opus-5" }),
];

test("the wire's spellings of an unknown fact fold to null; a real one survives", () => {
  expect(tierOf(undefined)).toBeNull();
  expect(tierOf(null)).toBeNull();
  expect(tierOf(0)).toBeNull();
  expect(tierOf(2.5)).toBeNull();
  expect(tierOf("3")).toBeNull();
  expect(tierOf(3)).toBe(3);
  expect(lineOf("")).toBeNull();
  expect(lineOf(undefined)).toBeNull();
  expect(lineOf("opus")).toBe("opus");
  expect(releasedOf("2026-05")).toBeNull();
  expect(releasedOf(undefined)).toBeNull();
  expect(releasedOf("2026-05-14")).toBe("2026-05-14");
});

test("the index reader folds a capture from before the catalogue to three nulls", () => {
  const legacy: Partial<Cell> = cell({ session_id: "legacy" });
  delete legacy.line;
  delete legacy.family_tier;
  delete legacy.released;
  const read = fromWire(index([legacy as Cell, cell({ session_id: "blank", line: "", released: "" }), lineup()[0]!]));
  expect(read.cells.map((c) => [c.line, c.family_tier, c.released])).toEqual([
    [null, null, null],
    [null, null, null],
    ["opus", 3, "2026-05-14"],
  ]);
});

test("tier options sort numerically, drop the null tier, and print as `tier n`", () => {
  const cells = [...lineup(), cell({ session_id: "ten", family_tier: 10 })];
  expect(facetOptions(cells, "tier")).toEqual(["1", "3", "4", "10"]);
  expect(["10", "9", "1"].sort(compareTier)).toEqual(["1", "9", "10"]);
  expect(facetLabel("tier", "3")).toBe("tier 3");
  expect(facetLabel("model", "3")).toBe("3");
  expect(tierLabel(3)).toBe("tier 3");
  expect(tierBadge(3)).toBe("T3");
  // a sweep captured before the catalogue offers no tier facet at all
  expect(facetOptions([cell({ session_id: "old" })], "tier")).toEqual([]);
});

test("a tier selects across providers, and an untiered session is never selected by tier", () => {
  const cells = lineup();
  expect(filterCells(cells, { ...NO_FACETS, tier: ["3"] }).map((c) => c.session_id)).toEqual(["opus", "sol"]);
  expect(filterCells(cells, { ...NO_FACETS, tier: ["3", "4"] }).map((c) => c.session_id)).toEqual(["opus", "sol", "astra"]);
  expect(filterCells(cells, NO_FACETS).map((c) => c.session_id)).toContain("old");
  expect(filterCells(cells, { ...NO_FACETS, tier: ["1", "3", "4"] }).map((c) => c.session_id)).not.toContain("old");
  // it AND-s with the other facets like any of them
  expect(filterCells(cells, { ...NO_FACETS, tier: ["3"], harness: ["codex"] }).map((c) => c.session_id)).toEqual(["sol"]);
  expect(facetCount(cells, { ...NO_FACETS, harness: ["claude"] }, "tier", "3")).toBe(1);
  expect(toggleFacet(NO_FACETS, "tier", "3")).toEqual({ ...NO_FACETS, tier: ["3"] });
});

test("&tier= parses as a list, round-trips, and serialises after treatment", () => {
  const route = parseSearch("?tier=3,4&treatment=control");
  expect(route).toMatchObject({ view: "overview", facets: { tier: ["3", "4"], treatment: ["control"] } });
  expect(routeSearch(route)).toBe("?treatment=control&tier=3,4");
  expect(parseSearch("?tier=")).toMatchObject({ facets: { tier: null } });
  expect(overviewSearch(null, null, { ...NO_FACETS, tier: ["3"] })).toBe("?tier=3");
});

test("the tier never splits a summary group; the row carries its model's catalogue facts", () => {
  const a = cell({ session_id: "a", line: "opus", family_tier: 3, released: "2026-05-14" });
  const b = cell({ session_id: "b" });
  expect(groupKey(a)).toBe(groupKey(b));
  const rows = summaryRows([a, cell({ session_id: "c", line: "opus", family_tier: 3, released: "2026-05-14" })]);
  expect(rows).toHaveLength(1);
  expect(rows[0]).toMatchObject({ line: "opus", family_tier: 3, released: "2026-05-14", runs: 2 });
});

test("the catalogue note names each fact it has, and nothing for an undescribed model", () => {
  expect(catalogueNote(lineup()[0]!)).toBe("line opus · family tier 3 · released 2026-05-14");
  expect(catalogueNote(lineup()[4]!)).toBe("");
});

test("the permutation matrix sweeps a tier that more than one harness ran, and nothing before the catalogue", () => {
  const perms = enumeratePermutations(index(lineup()), {}, "large");
  assertUniqueSlugs(perms);
  const cross = perms.find((p) => p.slug === "overview--filter-tier-3-across-harnesses");
  expect(cross?.search).toBe("?tier=3");
  expect(perms.some((p) => p.slug === "overview--filter-tier-1")).toBe(true);
  const old = enumeratePermutations(index([cell({ session_id: "x" }), cell({ session_id: "y", harness: "codex", model: "gpt-5.6-sol" })]), {}, "large");
  expect(old.some((p) => p.search.includes("tier="))).toBe(false);
});
