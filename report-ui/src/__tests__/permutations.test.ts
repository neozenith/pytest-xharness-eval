import { assertUniqueSlugs, enumeratePermutations, slugify, TIERS } from "@/lib/permutations";
import { filterCells } from "@/lib/facets";
import { parseSearch } from "@/lib/route";
import type { Cell, Index, RunResult } from "@/lib/types";

const cell = (over: Partial<Cell>): Cell =>
  ({
    case: "eval_case",
    suite: null,
    skill: null,
    fixture: null,
    prompt: null,
    harness: "claude",
    model: "claude-opus-5",
    session_id: "abcd1234-5678",
    verdict: null,
    at: null,
    node: null,
    wall_ms: null,
    result: "eval_case/x.result.json",
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
    turns: 2,
    reported_turns: null,
    tool_calls: 0,
    duration_ms: null,
    files_written: [],
    has_ledger: true,
    record_kinds: {},
    skill_coverage: {},
    ...over,
  }) as Cell;

const index = (cells: Cell[]): Index => ({ generated_at: "", captured: "", inline: false, cells });

test("slugify is lowercase, dash-joined and filesystem-safe", () => {
  expect(slugify("Eval Case", "claude/claude-opus-5", "ab.cd")).toBe("eval-case--claude-claude-opus-5--ab-cd");
  expect(slugify("x", null, undefined, "", 3)).toBe("x--3");
});

test("every permutation slug is unique and every turn is enumerated in both views", () => {
  const perms = enumeratePermutations(index([cell({})]), {});
  assertUniqueSlugs(perms);
  // 5 overview states (plain, dark, and the three sorts: SessionTable, SessionSummaryTable, both
  // at once) + 4 session states (landing, per-line axis, dark, raw records) + 2 views × (1
  // landing + 2 turns). No filter permutation: this fixture's skill is null and it has one
  // harness and one model, so no facet has two options — there is no choice to cover.
  expect(perms).toHaveLength(5 + 4 + 2 * 3);
  expect(perms[0]).toEqual({ slug: "overview", search: "?", description: "SweepOverview: 1 sessions" });
  expect(perms.map((p) => p.slug)).toContain("overview--dark");
  // the two tables sort on their own param pairs, and one URL carries both orders at once
  expect(perms.find((p) => p.slug === "overview--summary-sort-billed")?.search).toBe("?ssort=billed&sdir=desc");
  expect(perms.find((p) => p.slug === "overview--sort-both")?.search).toBe("?sort=turns&dir=asc&ssort=cost&sdir=desc");
  expect(perms.find((p) => p.slug.endsWith("--axis-line"))?.search).toContain("axis=line");
  expect(perms.find((p) => p.slug.endsWith("--rec-raw"))?.search).toContain("view=detailed&rec=raw");
  const detailedTurn2 = perms.find((p) => p.slug.endsWith("detailed--turn-02"));
  expect(detailedTurn2?.search).toBe("?session=abcd1234-5678&turn=2&view=detailed");
});

test("the ledger's call count wins over the cell's turn count", () => {
  const result = { calls: [{}, {}, {}, {}] } as unknown as RunResult;
  const perms = enumeratePermutations(index([cell({})]), { "abcd1234-5678": result });
  expect(perms.filter((p) => p.slug.includes("--turn-"))).toHaveLength(8);
});

test("a ledger with record lines yields one record-level deeplink", () => {
  const result = { calls: [{ records: [1, 2] }, { records: [3, 4] }] } as unknown as RunResult;
  const perms = enumeratePermutations(index([cell({})]), { "abcd1234-5678": result });
  const line = perms.find((p) => p.slug.endsWith("--line-003"));
  expect(line?.search).toBe("?session=abcd1234-5678&line=3");
});

test("two captures of the same cell stay distinct via the session-id prefix", () => {
  const perms = enumeratePermutations(index([cell({}), cell({ session_id: "efgh5678-1234" })]), {});
  expect(() => assertUniqueSlugs(perms)).not.toThrow();
});

test("a slug collision is an error, not a silent overwrite", () => {
  expect(() =>
    assertUniqueSlugs([
      { slug: "a", search: "?1", description: "" },
      { slug: "a", search: "?2", description: "" },
    ]),
  ).toThrow(/duplicate slug/);
});

test("tiers nest: every small slug is in medium, every medium slug is in large", () => {
  const cells = [
    cell({}),
    cell({ session_id: "efgh5678-1234", model: "claude-sonnet-5" }),
    cell({ session_id: "ijkl9012-3456", harness: "codex", model: "gpt-5.6-sol" }),
    // same harness/model as the first: in large only, so medium < large strictly
    cell({ session_id: "mnop3456-7890", turns: 5 }),
  ];
  const results = { "abcd1234-5678": { calls: [{ records: [1] }, { records: [2, 3] }] } as never };
  const slugs = (tier: "small" | "medium" | "large") => new Set(enumeratePermutations(index(cells), results, tier).map((p) => p.slug));
  const small = slugs("small");
  const medium = slugs("medium");
  const large = slugs("large");
  for (const s of small) expect(medium, `small slug ${s} missing from medium`).toContain(s);
  for (const s of medium) expect(large, `medium slug ${s} missing from large`).toContain(s);
  expect(small.size).toBeLessThan(medium.size);
  expect(medium.size).toBeLessThan(large.size);
});

test("small constrains every dimension: one session per harness, one mid turn, detailed only", () => {
  const cells = [cell({}), cell({ session_id: "efgh5678-1234", model: "other-model" }), cell({ session_id: "ijkl9012-3456", harness: "codex" })];
  const perms = enumeratePermutations(index(cells), {}, TIERS.small);
  expect(perms.filter((p) => p.slug.startsWith("overview"))).toHaveLength(1);
  expect(perms.filter((p) => p.slug.includes("--summary"))).toHaveLength(0);
  expect(perms.filter((p) => p.slug.includes("efgh5678"))).toHaveLength(0); // second claude cell excluded
  expect(perms.filter((p) => p.slug.includes("--turn-"))).toHaveLength(2); // one mid turn per harness
});

test("a multi-valued sweep enumerates the filter states, and small enumerates none of them", () => {
  const cells = [
    cell({ session_id: "a", skill: "discovery", harness: "claude", model: "claude-opus-5" }),
    cell({ session_id: "b", skill: "discovery", harness: "codex", model: "gpt-5.6-sol" }),
    cell({ session_id: "c", skill: "mermaidjs-diagrams", harness: "codex", model: "gpt-5.6-terra" }),
  ];
  const perms = enumeratePermutations(index(cells), {}, "large");
  assertUniqueSlugs(perms);
  const search = (slug: string) => perms.find((p) => p.slug === slug)?.search;
  expect(search("overview--filter-skill-discovery")).toBe("?skill=discovery");
  expect(search("overview--filter-harness-claude")).toBe("?harness=claude");
  expect(search("overview--filter-model-claude-opus-5")).toBe("?model=claude-opus-5");
  // the multi-select is the comma serialisation, and is not the same URL as the param being absent
  expect(search("overview--filter-multi")).toBe("?skill=discovery,mermaidjs-diagrams");
  // the empty state the matrix must sweep: a legal, reachable harness × model pair with no session
  const none = search("overview--filter-none");
  expect(none).toBe("?harness=claude&model=gpt-5.6-sol");
  const route = parseSearch(none!);
  expect(route.view === "overview" && filterCells(cells, route.facets)).toHaveLength(0);

  const small = new Set(enumeratePermutations(index(cells), {}, "small").map((p) => p.slug));
  for (const slug of [...small]) expect(slug).not.toMatch(/^overview--filter-/);
  const medium = new Set(enumeratePermutations(index(cells), {}, "medium").map((p) => p.slug));
  expect(medium).toContain("overview--filter-none");
});
