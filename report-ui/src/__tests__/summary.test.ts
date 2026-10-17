import { cell } from "./cells";
import { accumulationGroups } from "@/lib/series";
import { summaryRows } from "@/lib/summary";
import type { ImportantMetricsDoc } from "@/lib/types";
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

test("a row reads its cell's aggregates from index.json by the same key, and has none when the doc lacks the cell", () => {
  const sessions = [cell({ session_id: "1", effort: "high" }), cell({ session_id: "2", effort: "high", verdict: null }), cell({ session_id: "3" })];
  const doc: ImportantMetricsDoc = {
    metrics: [],
    cells: [
      {
        skill: sessions[0]!.skill,
        case: sessions[0]!.case,
        harness: sessions[0]!.harness,
        model: sessions[0]!.model,
        effort: "high",
        treatment: null,
        samples: 1,
        metrics: { cost: { median: 2, p25: 2, p75: 2, n: 1 } },
      },
    ],
  };
  const [high, defaulted] = summaryRows(sessions, doc);
  // Two sessions listed, one of them graded: the aggregates are over the one sample.
  expect(high).toMatchObject({ effort: "high", runs: 2, samples: 1, metrics: { cost: { median: 2 } } });
  // The rung-less cell has no aggregated twin: zero samples and no metrics, never borrowed ones.
  expect(defaulted).toMatchObject({ effort: null, runs: 1, samples: 0, metrics: {} });
});

test("with no Important Metrics document at all, every group still lists, with nothing aggregated", () => {
  expect(summaryRows([cell({ session_id: "1" })])).toMatchObject([{ runs: 1, samples: 0, metrics: {} }]);
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
