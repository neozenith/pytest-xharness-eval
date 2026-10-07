import { cell } from "./cells";
import { fromWire } from "@/lib/data";
import { armLabel } from "@/lib/effort";
import { facetCount, facetOptions, filterCells } from "@/lib/facets";
import { assertUniqueSlugs, enumeratePermutations, TIERS } from "@/lib/permutations";
import { NO_FACETS, overviewSearch, parseSearch, routeSearch } from "@/lib/route";
import { accumulationGroups, sessionLabel } from "@/lib/series";
import { summaryRows } from "@/lib/summary";
import { compareTreatment, CONTROL, treatmentLabel, treatmentOf, treatmentSortValue } from "@/lib/treatment";
import type { Cell, Index } from "@/lib/types";

const index = (cells: Cell[]): Index => ({ generated_at: "", captured: "", inline: false, cells });

/** A control and two treated twins of one arm, plus a second arm that only ran its control. */
const treated = (): Cell[] => [
  cell({ session_id: "t1", treatment: "lean-ci", estimated_cost_usd: 2 }),
  cell({ session_id: "c1", treatment: null, estimated_cost_usd: 5 }),
  cell({ session_id: "t2", treatment: "agents-md", estimated_cost_usd: 3 }),
  cell({ session_id: "c2", treatment: null, estimated_cost_usd: 7 }),
  cell({ session_id: "x1", harness: "codex", model: "gpt-5.6-sol", treatment: null }),
];

test("the wire's three spellings of a control fold to null; a treatment survives", () => {
  expect(treatmentOf(undefined)).toBeNull();
  expect(treatmentOf(null)).toBeNull();
  expect(treatmentOf("")).toBeNull();
  // the reserved word is never a treatment name, so it cannot reach a consumer as one
  expect(treatmentOf(CONTROL)).toBeNull();
  expect(treatmentOf("lean-ci")).toBe("lean-ci");
  // an index.json written before ADR 0055 has no key at all
  const legacy = { ...cell({ session_id: "old" }) } as Partial<Cell>;
  delete legacy.treatment;
  const read = fromWire(index([legacy as Cell, cell({ session_id: "new", treatment: "" }), cell({ session_id: "t", treatment: "lean-ci" })]));
  expect(read.cells.map((c) => c.treatment)).toEqual([null, null, "lean-ci"]);
});

test("the control is named, leads, and sorts first under a plain `<`", () => {
  expect(treatmentLabel(null)).toBe("control");
  expect(treatmentLabel("lean-ci")).toBe("lean-ci");
  expect(["zeta", null, "alpha", null].sort(compareTreatment)).toEqual([null, null, "alpha", "zeta"]);
  const values = ["zeta", null, "alpha"].map(treatmentSortValue);
  expect([...values].sort()).toEqual([treatmentSortValue(null), treatmentSortValue("alpha"), treatmentSortValue("zeta")]);
});

test("an arm label appends +treatment only when treated, so a control's label is unchanged", () => {
  expect(armLabel("claude", "claude-opus-5", "high", "lean-ci")).toBe("claude/claude-opus-5 · high +lean-ci");
  expect(armLabel("claude", "claude-opus-5", null, "lean-ci")).toBe("claude/claude-opus-5 +lean-ci");
  expect(armLabel("claude", "claude-opus-5", "high", null)).toBe("claude/claude-opus-5 · high");
  expect(sessionLabel(cell({ session_id: "abcdef123", treatment: "lean-ci" }))).toContain("+lean-ci");
});

test("a control and its treated twins are separate summary rows, control first, never one blended mean", () => {
  const rows = summaryRows(treated());
  expect(rows.map((r) => [r.harness, r.treatment, r.runs, r.mean_estimated_cost_usd])).toEqual([
    ["claude", null, 2, 6],
    ["claude", "agents-md", 1, 3],
    ["claude", "lean-ci", 1, 2],
    ["codex", null, 1, 1],
  ]);
  // a control keeps the key every group had before the axis; a twin rides the cache's `+`
  expect(rows[0]!.key).toBe("discovery|eval_case|claude|claude-opus-5");
  expect(rows[2]!.key).toBe("discovery|eval_case|claude|claude-opus-5+lean-ci");
  // a rung and a treatment together: the rung segment, then the treatment
  expect(summaryRows([cell({ effort: "high", treatment: "lean-ci" })])[0]!.key).toBe("discovery|eval_case|claude|claude-opus-5|high+lean-ci");
});

test("a rung's control sits directly above its treated twin, before the next rung", () => {
  const rows = summaryRows([
    cell({ session_id: "1", effort: "max", treatment: "lean-ci" }),
    cell({ session_id: "2", effort: "low", treatment: "lean-ci" }),
    cell({ session_id: "3", effort: "max", treatment: null }),
    cell({ session_id: "4", effort: "low", treatment: null }),
  ]);
  expect(rows.map((r) => `${r.effort}${r.treatment ? `+${r.treatment}` : ""}`)).toEqual(["low", "low+lean-ci", "max", "max+lean-ci"]);
});

test("the accumulation chart draws a treated twin as its own line, distinctly labelled, paired 1:1 with the summary", () => {
  const run = (billed: number) =>
    ({ calls: [{ n: 1, usage: { input_tokens: billed, cache_read_tokens: 0, cache_write_tokens: 0, output_tokens: 0 } }] }) as never;
  const cells = [cell({ session_id: "t", treatment: "lean-ci" }), cell({ session_id: "c", treatment: null })];
  const groups = accumulationGroups(cells, { t: run(1), c: run(2) });
  expect(groups.map((g) => g.label)).toEqual(["eval_case.py · claude/claude-opus-5 · n=1", "eval_case.py · claude/claude-opus-5 +lean-ci · n=1"]);
  expect(new Set(groups.map((g) => g.key)).size).toBe(2);
  expect(groups).toHaveLength(summaryRows(cells).length);
});

test("treatment is a facet whose control is selectable by name, and an untreated sweep offers none", () => {
  const cells = treated();
  expect(facetOptions(cells, "treatment")).toEqual(["control", "agents-md", "lean-ci"]);
  // every sweep before ADR 0055 is all control: no choice, so no chip row
  expect(facetOptions([cell({ session_id: "a" }), cell({ session_id: "b" })], "treatment")).toEqual([]);
  expect(filterCells(cells, { ...NO_FACETS, treatment: ["control"] }).map((c) => c.session_id)).toEqual(["c1", "c2", "x1"]);
  expect(filterCells(cells, { ...NO_FACETS, treatment: ["control", "lean-ci"] }).map((c) => c.session_id)).toEqual(["t1", "c1", "c2", "x1"]);
  expect(filterCells(cells, { ...NO_FACETS, treatment: ["lean-ci"], harness: ["codex"] })).toHaveLength(0);
  expect(facetCount(cells, { ...NO_FACETS, harness: ["codex"] }, "treatment", "control")).toBe(1);
  expect(facetCount(cells, { ...NO_FACETS, harness: ["codex"] }, "treatment", "lean-ci")).toBe(0);
});

test("&treatment= parses as a list, round-trips, and serialises after effort", () => {
  const route = parseSearch("?treatment=control,lean-ci&effort=high");
  expect(route).toMatchObject({ view: "overview", facets: { treatment: ["control", "lean-ci"], effort: ["high"] } });
  expect(routeSearch(route)).toBe("?effort=high&treatment=control,lean-ci");
  expect(parseSearch("?treatment=")).toMatchObject({ facets: { treatment: null } });
  expect(overviewSearch(null, null, { ...NO_FACETS, treatment: ["control"] })).toBe("?treatment=control");
});

test("the permutation matrix sweeps the control beside a treatment, and a treated cell's slug names it", () => {
  const cells = treated();
  const perms = enumeratePermutations(index(cells), {}, "large");
  assertUniqueSlugs(perms);
  const search = (slug: string) => perms.find((p) => p.slug === slug)?.search;
  expect(search("overview--filter-treatment-control")).toBe("?treatment=control");
  expect(search("overview--filter-treatment-vs-control")).toBe("?treatment=control,agents-md");
  // a treated cell's slug carries its treatment; a control's is the slug it always had
  expect(perms.some((p) => p.slug.startsWith("eval-case--claude-claude-opus-5-lean-ci--t1"))).toBe(true);
  expect(perms.some((p) => p.slug.startsWith("eval-case--claude-claude-opus-5--c1"))).toBe(true);
  // medium breadth: one session per arm *and* treatment, so a twin is never shadowed by its control
  expect(TIERS.medium.cells(cells).map((c) => c.session_id)).toEqual(["t1", "c1", "t2", "x1"]);
  // an untreated sweep enumerates no treatment state at all
  const plain = enumeratePermutations(index([cell({ session_id: "a" }), cell({ session_id: "b", harness: "codex" })]), {}, "large");
  expect(plain.filter((p) => p.slug.includes("treatment"))).toEqual([]);
});
