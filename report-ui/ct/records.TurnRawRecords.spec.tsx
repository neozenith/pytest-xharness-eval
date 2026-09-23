/**
 * `TurnRawRecords`: one turn's session-log lines as cards, under the turn's id. The heading
 * names the line ranges and the turn's context; each card is the harness's own card, anchored
 * at `L<line>`, annotated with its context and deep-linked with `line=`.
 */
import { expect, test } from "@playwright/experimental-ct-react";
import { TurnRawRecords } from "../src/components/records/TurnRawRecords";
import type { HooksConfig } from "../playwright/index";
import {
  SID,
  UNBROKEN,
  call,
  claudeAssistant,
  claudeToolResult,
  claudeToolUse,
  claudeUser,
  codexResponse,
  codexTokenCount,
  codexTurnContext,
  result,
} from "./fixtures";

const claudeLines = (): string[] => [
  JSON.stringify(claudeUser("draw the architecture")),
  JSON.stringify(claudeToolUse("Bash", { command: "ls" })),
  JSON.stringify(claudeToolResult("README.md")),
  JSON.stringify(claudeToolUse("Read", { file_path: "SKILL.md" })),
  JSON.stringify(claudeToolResult("# Skill")),
  JSON.stringify(claudeAssistant([{ type: "text", text: "done" }])),
  "{broken",
];

test("the turn's block carries its id, heading, and one anchored card per line", async ({ mount }) => {
  const r = result({ calls: [call(1, { records: [1, 2, 3] }), call(2, { records: [4, 5, 7] }), call(3, { records: [6] })] });
  const c = await mount(<TurnRawRecords result={r} call={r.calls[1]!} lines={claudeLines()} view="nice" />);
  await expect(c.locator(`[id="${SID}/t2"]`)).toHaveAttribute("data-el", "TurnRawRecords");
  await expect(c.locator('div.detail[data-el="TurnRawRecords"]')).toHaveCount(1);
  await expect(c.locator("h4")).toContainText("lines 4-5, 7 · context 8.0% of 1M");
  const cards = c.locator('.rec[data-el="RecordCard"]');
  await expect(cards).toHaveCount(3);
  expect(await cards.evaluateAll((els) => els.map((e) => e.id))).toEqual(["L4", "L5", "L7"]);
  await expect(c.locator("#L4")).toHaveAttribute("data-kind", "claude/assistant/tool_use");
  await expect(c.locator("#L5")).toHaveAttribute("data-kind", "claude/user/tool_result");
  await expect(c.locator("#L7")).toHaveAttribute("data-kind", "claude/unparseable");
  await expect(c.locator("#L7 .rec-nice")).toContainText("{broken");
});

test("a call is annotated with its own context; a result with the next turn's", async ({ mount }) => {
  const r = result({ calls: [call(1, { records: [1, 2, 3] }), call(2, { records: [4, 5] })] });
  const c = await mount(<TurnRawRecords result={r} call={r.calls[0]!} lines={claudeLines()} view="nice" />);
  await expect(c.locator("#L2 .ctx")).toHaveText("ctx 4.0%");
  await expect(c.locator("#L2 .ctx")).toHaveAttribute("title", "turn 1 processed 40,000 of a 1M window");
  await expect(c.locator("#L3 .ctx")).toHaveText("→ t2 8.0%");
  await expect(c.locator("#L3 .ctx")).toHaveAttribute("title", "this result enters turn 2's context, measured at 80,000 tokens");
});

test("a turn with no context measurement carries no annotation", async ({ mount }) => {
  const r = result({ calls: [call(1, { records: [1, 2], context_pct: null })] });
  const c = await mount(<TurnRawRecords result={r} call={r.calls[0]!} lines={claudeLines()} view="nice" />);
  await expect(c.locator(".rec")).toHaveCount(2);
  await expect(c.locator(".ctx")).toHaveCount(0);
});

test("each card's permalink points at its own line of this session", async ({ mount, page }) => {
  const r = result({ calls: [call(1, { records: [2, 3] })] });
  const c = await mount(<TurnRawRecords result={r} call={r.calls[0]!} lines={claudeLines()} view="nice" />);
  await c.getByRole("button", { name: "link to log line 3" }).click();
  await expect.poll(() => new URL(page.url()).searchParams.get("line")).toBe("3");
  expect(new URL(page.url()).searchParams.get("session")).toBe(SID);
});

test("view=raw puts every card in raw JSON; a card's own flip is its own", async ({ mount }) => {
  const r = result({ calls: [call(1, { records: [1, 2, 3] })] });
  const c = await mount(<TurnRawRecords result={r} call={r.calls[0]!} lines={claudeLines()} view="raw" />);
  await expect(c.locator(".rec-raw")).toHaveCount(3);
  await c.locator("#L2").getByRole("button", { name: "nice" }).click();
  await expect(c.locator(".rec-raw")).toHaveCount(2);
  await expect(c.locator("#L2 .rec-nice")).toBeVisible();
  await c.update(<TurnRawRecords result={r} call={r.calls[0]!} lines={claudeLines()} view="nice" />);
  await expect(c.locator(".rec-nice")).toHaveCount(3);
});

test("a Codex turn uses the Codex card, and its token_count is the call's measurement", async ({ mount }) => {
  const lines = [
    JSON.stringify(codexTurnContext("high")),
    JSON.stringify(codexResponse({ type: "custom_tool_call", name: "exec", call_id: "c1", input: 'tools.exec_command({ cmd: "ls" })' })),
    JSON.stringify(codexResponse({ type: "custom_tool_call_output", call_id: "c1", output: "README.md" })),
    JSON.stringify(codexTokenCount()),
  ];
  const r = result({ harness: "codex", model: "gpt-5.6-sol", calls: [call(1, { records: [1, 2, 3, 4] }), call(2, { records: [] })] });
  const c = await mount(<TurnRawRecords result={r} call={r.calls[0]!} lines={lines} view="nice" />);
  await expect(c.locator('.rec[data-harness="codex"]')).toHaveCount(4);
  await expect(c.locator("#L1")).toHaveAttribute("data-kind", "codex/turn_context");
  await expect(c.locator("#L3 .ctx")).toHaveText("→ t2 8.0%");
  await expect(c.locator("#L4")).toHaveAttribute("data-kind", "codex/event_msg/token_count");
  await expect(c.locator("#L4 .ctx")).toHaveText("ctx 4.0%");
});

test("no captured log says so", async ({ mount }) => {
  const r = result();
  const c = await mount(<TurnRawRecords result={r} call={r.calls[0]!} lines={null} view="nice" />);
  await expect(c).toContainText("no captured log beside this result");
  await expect(c.locator(".rec")).toHaveCount(0);
});

test("a turn with no attributed records says so", async ({ mount }) => {
  const r = result({ calls: [call(1, { records: [] })] });
  const c = await mount(<TurnRawRecords result={r} call={r.calls[0]!} lines={claudeLines()} view="nice" />);
  await expect(c).toContainText("no records attributed to this turn");
});

test("a record line past the end of the log still gets a visible, anchored card that says it is missing", async ({ mount }) => {
  const r = result({ calls: [call(1, { records: [99] })] });
  const c = await mount(<TurnRawRecords result={r} call={r.calls[0]!} lines={claudeLines()} view="nice" />);
  await expect(c.locator("#L99")).toBeVisible();
  await expect(c.locator("#L99")).toHaveText("line 99 is not in the captured log (it has 7 lines)");
  await expect(c.locator("#L99")).not.toHaveAttribute("data-kind", /unparseable/);
});

test("dark mode tints the block on the dark page and keeps the cards on the dark panel", async ({ mount }) => {
  const r = result({ calls: [call(1, { records: [1] })] });
  const c = await mount<HooksConfig>(<TurnRawRecords result={r} call={r.calls[0]!} lines={claudeLines()} view="nice" />, { hooksConfig: { mode: "dark" } });
  await expect(c.locator("#L1")).toHaveCSS("background-color", "rgb(23, 26, 35)");
});

test("a very long unbroken line does not scroll the page sideways", async ({ mount, page }) => {
  const lines = [JSON.stringify(claudeUser(UNBROKEN)), JSON.stringify(claudeToolUse("Bash", { command: UNBROKEN }))];
  const r = result({ calls: [call(1, { records: [1, 2] })] });
  const c = await mount(<TurnRawRecords result={r} call={r.calls[0]!} lines={lines} view="nice" />);
  await expect(c.locator("#L2")).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(0);
});

// Finding: a ledger line past the end of the captured log (a log truncated after the result
// was written) became `lines[n - 1] ?? ""`: a card classed `unparseable`, "0 chars", and an
// empty code box, i.e. it read as a corrupt line rather than a missing one.
test("a line the captured log does not have is named as missing, not drawn as an empty unparseable record", async ({ mount }) => {
  const r = result({ calls: [call(1, { records: [1, 2, 9] })] });
  const c = await mount(<TurnRawRecords result={r} call={r.calls[0]!} lines={claudeLines().slice(0, 2)} view="nice" />);
  await expect(c.locator('.rec[data-el="RecordCard"]')).toHaveCount(2);
  const missing = c.locator("#L9");
  await expect(missing).toContainText("line 9 is not in the captured log (it has 2 lines)");
  await expect(missing.locator(".xh-pre")).toHaveCount(0);
});
