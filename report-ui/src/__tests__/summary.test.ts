import { cell } from "./cells";
import { accumulationGroups } from "@/lib/series";
import { summaryRows } from "@/lib/summary";
import { result } from "./charts.series.test";

test("rows group by skill × case × harness × model, in that key order, a null skill last", () => {
  const rows = summaryRows([
    cell({ session_id: "1", skill: "mermaidjs-diagrams", case: "eval_b", harness: "codex", model: "gpt-5.6-sol" }),
    cell({ session_id: "2", skill: null, case: "eval_a", harness: "claude", model: "claude-opus-5" }),
    cell({ session_id: "3", skill: "discovery", case: "eval_a", harness: "codex", model: "gpt-5.6-sol" }),
    cell({ session_id: "4", skill: "discovery", case: "eval_a", harness: "claude", model: "claude-opus-5" }),
    cell({ session_id: "5", skill: "discovery", case: "eval_a", harness: "claude", model: "claude-opus-5" }),
  ]);
  expect(rows.map((r) => [r.skill, r.case, r.harness, r.model])).toEqual([
    ["discovery", "eval_a", "claude", "claude-opus-5"],
    ["discovery", "eval_a", "codex", "gpt-5.6-sol"],
    ["mermaidjs-diagrams", "eval_b", "codex", "gpt-5.6-sol"],
    [null, "eval_a", "claude", "claude-opus-5"],
  ]);
  expect(rows[0]!.runs).toBe(2);
  expect(rows[1]!.runs).toBe(1);
});

test("a mean skips missing values and is null — never zero — when the whole group is missing", () => {
  const two = summaryRows([cell({ session_id: "1", estimated_cost_usd: 4 }), cell({ session_id: "2", estimated_cost_usd: null })]);
  // the divisor is the count of PRESENT values, not `runs`: 4, not 2
  expect(two[0]!.mean_estimated_cost_usd).toBe(4);
  const none = summaryRows([cell({ session_id: "1", estimated_cost_usd: null }), cell({ session_id: "2", estimated_cost_usd: null })]);
  expect(none[0]!.mean_estimated_cost_usd).toBeNull();
  const both = summaryRows([cell({ session_id: "1", wall_ms: 1000 }), cell({ session_id: "2", wall_ms: 3000 })]);
  expect(both[0]!.mean_wall_ms).toBe(2000);
});

test("the pass rate's denominator is the runs that carry a verdict", () => {
  const graded = summaryRows([
    cell({ session_id: "1", verdict: "pass" }),
    cell({ session_id: "2", verdict: "fail" }),
    cell({ session_id: "3", verdict: null }),
  ]);
  expect(graded[0]).toMatchObject({ runs: 3, pass: 1, graded: 2 });
  const ungraded = summaryRows([cell({ session_id: "1", verdict: null })]);
  expect(ungraded[0]).toMatchObject({ runs: 1, pass: 0, graded: 0 });
});

test("the context share is the mean of the cells' own context_window_pct, beside the first window", () => {
  const rows = summaryRows([
    cell({ session_id: "1", peak_context_tokens: 100_000, context_window_pct: 10, context_window: null }),
    cell({ session_id: "2", peak_context_tokens: 300_000, context_window_pct: 30, context_window: 1_000_000 }),
  ]);
  expect(rows[0]!.mean_peak_context_tokens).toBe(200_000);
  expect(rows[0]!.mean_context_window_pct).toBe(20);
  expect(rows[0]!.context_window).toBe(1_000_000);
});

test("the coverage share is loaded/files per run and skips a run with no catalogue", () => {
  const rows = summaryRows([cell({ session_id: "1", skill_coverage: { files: 18, loaded: 6 } }), cell({ session_id: "2", skill_coverage: {} })]);
  // 6/18, not 3/18: a missing catalogue is skipped, never counted as zero coverage
  expect(rows[0]!.mean_skill_coverage_share).toBeCloseTo(6 / 18, 12);
  expect(summaryRows([cell({ session_id: "1", skill_coverage: {} })])[0]!.mean_skill_coverage_share).toBeNull();
});

test("one summary row is one line of the chart above it", () => {
  // The pairing is the whole reason the summary groups the way it does: a future regrouping of
  // either side must break this.
  const cells = [
    cell({ session_id: "s", suite: "skills/s/evals/eval_case.py" }),
    cell({ session_id: "t", suite: "skills/s/evals/eval_case.py", harness: "codex", model: "gpt-5.6-sol" }),
  ];
  const results = { s: result, t: result };
  expect(summaryRows(cells)).toHaveLength(accumulationGroups(cells, results).length);
});
