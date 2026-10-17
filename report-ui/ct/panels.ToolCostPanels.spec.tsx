/**
 * ToolCostTable and SkillUsePanel: each tool call's time and two costs with its per-turn trace,
 * and the skill under test's span with every access beneath it (ADR 0073). Python attributes
 * every figure; these tests pin what the page prints and what it says when a figure is absent.
 */
import { expect, test } from "./test";
import { SkillUsePanel, ToolCostTable } from "../src/components/panels/ToolCostPanels";
import type { SkillUse, ToolCost } from "../src/lib/types";
import { result } from "./panels.data";

// `clock()` prints local time; pin the zone so the stamps read the same everywhere.
test.use({ timezoneId: "UTC" });

const cost = (over: Partial<ToolCost> = {}): ToolCost => ({
  thread: "",
  turn: 2,
  id: "toolu_01",
  name: "Read",
  summary: "read SKILL.md",
  started_at: "2026-10-18T07:00:01.000Z",
  ended_at: "2026-10-18T07:00:01.120Z",
  duration_ms: 120,
  issuing_cost_usd: 0.004,
  result_tokens: 4000,
  context_cost_usd: 0.033,
  cache_rereads: 2,
  trace: [
    { turn: 3, cached: false, usd: 0.015 },
    { turn: 4, cached: true, usd: 0.009 },
    { turn: 5, cached: true, usd: 0.009 },
  ],
  ...over,
});

const use = (over: Partial<SkillUse> = {}): SkillUse => ({
  skill: "mermaidjs-diagrams",
  trigger: "prompt",
  triggered_turn: 1,
  triggered_at: "2026-10-18T07:00:00.000Z",
  last_turn: 12,
  last_at: "2026-10-18T07:01:17.000Z",
  duration_ms: 77000,
  tool_calls: 2,
  issuing_cost_usd: 0.021,
  context_cost_usd: 0.184,
  cache_rereads: 61,
  events: [
    {
      thread: "",
      turn: 2,
      tool_id: "toolu_01",
      tool: "Read",
      path: "SKILL.md",
      access: "loaded",
      started_at: "2026-10-18T07:00:01.000Z",
      duration_ms: 120,
      issuing_cost_usd: 0.004,
      context_cost_usd: 0.09,
    },
    {
      thread: "a6bbeeaf1e9f6d011",
      turn: 12,
      tool_id: "",
      tool: "CommandExecution",
      path: "scripts/contrast.ts",
      access: "run",
      started_at: "",
      duration_ms: null,
      issuing_cost_usd: null,
      context_cost_usd: null,
    },
  ],
  ...over,
});

const cells = async (row: ReturnType<import("@playwright/test").Locator["nth"]>) => row.locator("td").allInnerTexts();

test("a tool call prints its thread, time, both costs, re-reads and a folded trace", async ({ mount }) => {
  const c = await mount(<ToolCostTable result={result({ tool_costs: [cost(), cost({ thread: "a6bbeeaf1e9f6d011", id: "t2", name: "Bash", trace: [] })] })} />);
  const rows = c.locator('[data-el="ToolCostRow"]');
  await expect(rows).toHaveCount(2);
  const first = await cells(rows.nth(0));
  expect(first.slice(0, 9)).toEqual(["primary", "2", "Read", "07:00:01.000", "120 ms", "$0.0040", "4,000", "$0.0330", "2"]);
  const trace = rows.nth(0).locator('[data-el="ToolCostTrace"]');
  await expect(trace.locator("summary")).toHaveText("3 turns");
  await trace.locator("summary").click();
  await expect(trace).toContainText("t3 $0.0150 · t4c $0.0090 · t5c $0.0090");
  // A subagent's call names its thread; a result nothing read has no trace to open.
  const second = await cells(rows.nth(1));
  expect([second[0], second[9]]).toEqual(["a6bbeeaf", "–"]);
});

test("the tool table says why it is empty", async ({ mount }) => {
  const before = await mount(<ToolCostTable result={result({ tool_costs: undefined })} />);
  await expect(before).toContainText("This result predates ADR 0073");
  await before.unmount();
  const none = await mount(<ToolCostTable result={result({ tool_costs: [] })} />);
  await expect(none).toContainText("This session issued no tool calls.");
});

test("a skill's use shows its span and totals, then each access with its call's figures", async ({ mount }) => {
  const c = await mount(<SkillUsePanel result={result({ skill_use: use() })} />);
  const span = c.locator("#SkillUseSpan");
  await expect(span).toContainText("triggered");
  await expect(span).toContainText("turn 1 · 07:00:00.000");
  await expect(span).toContainText("turn 12 · 07:01:17.000");
  await expect(span).toContainText("77,000 ms");
  await expect(span).toContainText("$0.1840");
  const events = c.locator('[data-el="SkillUseEvent"]');
  await expect(events).toHaveCount(2);
  expect(await cells(events.nth(0))).toEqual(["2", "primary", "Read", "SKILL.md", "loaded", "120 ms", "$0.0040", "$0.0900"]);
  // A command the shell reported, which no single tool call owns, has no figures to show.
  expect((await cells(events.nth(1))).slice(1)).toEqual(["a6bbeeaf", "CommandExecution", "scripts/contrast.ts", "run", "–", "–", "–"]);
});

test("the skill panel says when the skill was never triggered, and when the result predates the trace", async ({ mount }) => {
  const never = await mount(<SkillUsePanel result={result({ skill_use: {} })} />);
  await expect(never).toContainText("The skill was never triggered");
  await never.unmount();
  const before = await mount(<SkillUsePanel result={result({ skill_use: undefined })} />);
  await expect(before).toContainText("This result predates ADR 0073");
});
