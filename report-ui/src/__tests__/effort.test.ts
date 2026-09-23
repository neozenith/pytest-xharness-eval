import { cell } from "./cells";
import { armLabel, compareEffort, effortSortValue, LADDER } from "@/lib/effort";
import { accumulationGroups, sessionLabel } from "@/lib/series";
import { summaryRows } from "@/lib/summary";

test("rungs order by ladder position, an unknown rung after the ladder, null last", () => {
  const rungs = ["max", null, "high", "zeta", "low", "alpha", "xhigh", "medium"];
  expect([...rungs].sort(compareEffort)).toEqual(["low", "medium", "high", "xhigh", "max", "alpha", "zeta", null]);
  // the ladder mirrors model/effort.py's native rungs, lowest first
  expect(LADDER).toEqual(["low", "medium", "high", "xhigh", "max"]);
});

test("a rung's sort value is numeric, so a `<` comparator ranks the ladder, and null stays null", () => {
  expect(effortSortValue("low")! < effortSortValue("high")!).toBe(true);
  expect(effortSortValue("max")! < effortSortValue("never-heard-of-it")!).toBe(true);
  expect(effortSortValue(null)).toBeNull();
});

test("an arm label names the rung only when one was sent", () => {
  expect(armLabel("claude", "claude-opus-5", "high")).toBe("claude/claude-opus-5 · high");
  expect(armLabel("claude", "claude-opus-5", null)).toBe("claude/claude-opus-5");
  expect(sessionLabel(cell({ case: "eval_x", effort: "low", session_id: "1feb573f-ba51" }))).toBe("eval_x · claude/claude-opus-5 · low · 1feb573f");
});

test("two rungs of one model are two summary rows, in ladder order, never one averaged row", () => {
  const rows = summaryRows([
    cell({ session_id: "1", effort: "max", estimated_cost_usd: 9 }),
    cell({ session_id: "2", effort: "low", estimated_cost_usd: 1 }),
    cell({ session_id: "3", effort: null, estimated_cost_usd: 5 }),
    cell({ session_id: "4", effort: "low", estimated_cost_usd: 3 }),
  ]);
  expect(rows.map((r) => [r.effort, r.runs, r.mean_estimated_cost_usd])).toEqual([
    ["low", 2, 2],
    ["max", 1, 9],
    [null, 1, 5],
  ]);
  // a rung-less group keeps the key it had before the axis existed
  expect(rows[2]!.key).toBe("discovery|eval_case|claude|claude-opus-5");
  expect(rows[0]!.key).toBe("discovery|eval_case|claude|claude-opus-5|low");
});

test("the accumulation chart draws one line per rung, labelled with it, still paired 1:1 with the summary", () => {
  const run = (billed: number) =>
    ({ calls: [{ n: 1, usage: { input_tokens: billed, cache_read_tokens: 0, cache_write_tokens: 0, output_tokens: 0 } }] }) as never;
  const cells = [cell({ session_id: "a", effort: "low" }), cell({ session_id: "b", effort: "high" }), cell({ session_id: "c", effort: null })];
  const groups = accumulationGroups(cells, { a: run(1), b: run(2), c: run(3) });
  expect(groups.map((g) => g.label)).toEqual([
    "eval_case.py · claude/claude-opus-5 · low · n=1",
    "eval_case.py · claude/claude-opus-5 · high · n=1",
    "eval_case.py · claude/claude-opus-5 · n=1",
  ]);
  expect(groups).toHaveLength(summaryRows(cells).length);
});
