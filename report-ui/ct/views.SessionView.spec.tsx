/**
 * `SessionView`: one captured session. Its route arrives as a prop (App parses it), its result and
 * log arrive through the data hooks from `hooksConfig.inline`, and every control writes the whole
 * route back with `replaceRoute` — so a control is asserted against `location.search`.
 */
import { expect, test } from "./test";
import type { Page } from "@playwright/test";
import { SessionView } from "../src/views/SessionView";
import { EFFORT_DEFAULT } from "../src/lib/effort";
import type { SessionRoute } from "../src/lib/route";
import type { Cell } from "../src/lib/types";
import { cell, inline, SID } from "./fixtures";

const route = (over: Partial<SessionRoute> = {}): SessionRoute => ({
  view: "session",
  sessionId: SID,
  turn: null,
  turnView: null,
  axis: null,
  rec: null,
  line: null,
  theme: null,
  ...over,
});

const search = (page: Page) => page.evaluate(() => location.search);

/** The metadata table as `{key: text}`. */
const meta = (page: Page): Promise<Record<string, string>> =>
  page
    .locator("#SessionMetaTable tbody tr")
    .evaluateAll((trs) =>
      Object.fromEntries(trs.map((tr) => [(tr.children[0] as HTMLElement).innerText.trim(), (tr.children[1] as HTMLElement).innerText.trim()])),
    );

const PANELS = [
  "ChartAxisToggle",
  "TokenWaterfallChart",
  "ContextWindowChart",
  "OutputPerTurnChart",
  "TurnTiersChart",
  "ReconciliationPanel",
  "CostByTierPanel",
  "SkillCoveragePanelWrap",
  "RecordKindsPanel",
  "SessionTurnTablePanel",
  "FinalMessagePanel",
];

test("an id the index does not hold says so and links back to the sweep", async ({ mount, page }) => {
  const c = await mount(<SessionView cell={undefined} route={route({ sessionId: "nope-0000" })} />, {
    hooksConfig: { search: "?session=nope-0000", inline: inline() },
  });
  await expect(c).toContainText("No captured session nope-0000 in this index.");
  const back = page.getByRole("link", { name: "← all sessions" });
  await expect(back).toHaveAttribute("href", "?");
  await expect(page.locator("#SessionMetaTable")).toHaveCount(0);
  await expect(page.locator("#SessionTitle")).toHaveCount(0);
});

test("title and metadata name the arm, with the rung on its own row", async ({ mount, page }) => {
  const c1 = cell({ effort: "high" });
  await mount(<SessionView cell={c1} route={route()} />, { hooksConfig: { search: `?session=${SID}`, inline: inline([c1]) } });
  await expect(page.locator("#SessionTitle")).toContainText("eval_dual_density · claude/claude-opus-5 · high");
  const m = await meta(page);
  expect(Object.keys(m)).toEqual([
    "verdict",
    "suite",
    "case",
    "skill",
    "fixture",
    "task",
    "prompt sent",
    "harness / model",
    "effort",
    "started",
    "wall",
    "estimated_cost_usd",
    "harness_reported_cost_usd",
    "accumulative_billed_tokens",
    "baseline_tokens",
    "peak_context_tokens",
    "context window",
    "turns",
    "tool_calls",
    "files written",
  ]);
  expect(m).toMatchObject({
    verdict: expect.stringMatching(/^pass$/i),
    suite: "skills/mermaidjs-diagrams/evals/eval_mermaid.py",
    case: "eval_dual_density",
    skill: "mermaidjs-diagrams",
    fixture: "small-repo",
    task: "draw the architecture",
    "prompt sent": "/mermaidjs-diagrams draw the architecture",
    "harness / model": "claude / claude-opus-5",
    effort: "high",
    wall: "83.0s",
    estimated_cost_usd: "$1.0276",
    harness_reported_cost_usd: "$1.0288",
    accumulative_billed_tokens: "1,504,090",
    baseline_tokens: "35,599",
    peak_context_tokens: "120,245 · 12.0% of 1M",
    "context window": "1,000,000 tokens (harness-reported)",
    turns: "3 (harness reported 23)",
    tool_calls: "14",
    "files written": "ARCHITECTURE.md",
  });
  await expect(page.locator("#SessionMetaTable code", { hasText: /^high$/ })).toHaveCount(1);
});

test("a rung-less session omits the rung from the title and says the CLI default in muted prose", async ({ mount, page }) => {
  const c0 = cell({ effort: null });
  await mount(<SessionView cell={c0} route={route()} />, { hooksConfig: { search: `?session=${SID}`, inline: inline([c0]) } });
  const title = await page.locator("#SessionTitle").innerText();
  expect(title).toContain("eval_dual_density · claude/claude-opus-5");
  expect(title).not.toMatch(/claude-opus-5 · /);
  expect((await meta(page)).effort).toBe(EFFORT_DEFAULT);
  const row = page.locator("#SessionMetaTable tbody tr", { hasText: EFFORT_DEFAULT });
  await expect(row.locator("span.muted")).toHaveText(EFFORT_DEFAULT);
});

test("absent fields fall back to their stated sentences", async ({ mount, page }) => {
  const c = cell({
    task: null,
    prompt: null,
    files_written: [],
    context_window: null,
    reported_turns: null,
    skill: null,
    fixture: null,
    suite: null,
  } as Partial<Cell>);
  await mount(<SessionView cell={c} route={route()} />, { hooksConfig: { search: `?session=${SID}`, inline: inline([c]) } });
  const m = await meta(page);
  expect(m.task).toBe("not recorded on this result; replay to recover it (ADR 0025, ADR 0044)");
  expect(m["prompt sent"]).toBe("not recorded on this result; replay to recover it (ADR 0025)");
  expect(m["files written"]).toBe("none");
  expect(m["context window"]).toBe("not reported");
  expect(m.turns).toBe("3");
  expect(m.skill).toBe("–");
  expect(m.fixture).toBe("–");
  expect(m.suite).toBe("–");
});

test("charts, panels and the turn table appear once the result loads", async ({ mount, page }) => {
  const c = cell();
  await mount(<SessionView cell={c} route={route()} />, { hooksConfig: { search: `?session=${SID}`, inline: inline([c]) } });
  for (const id of PANELS) await expect(page.locator(`#${id}`), id).toHaveCount(1);
  await expect(page.locator("#FinalMessage")).toContainText("Both gates pass clean.");
  await expect(page.locator("#SessionTurnTable tbody tr.SessionTurnRow")).toHaveCount(3);
  await expect(page.locator("[data-xh-loading='result']")).toHaveCount(0);
  // Nothing open by default: the summary view, per-turn axis, nice records.
  await expect(page.locator("#SessionTurnTable tr.detail-row")).toHaveCount(0);
  await expect(page.locator("#ChartAxisToggle [data-state='on']")).toHaveText("per turn");
  await expect(page.locator("#ViewToggle [data-state='on']")).toHaveText("Summary view");
  await expect(page.locator("#RecordViewToggle [data-state='on']")).toHaveText("nice records");
});

test("a result the payload does not hold shows the error and no charts", async ({ mount, page }) => {
  const c = cell();
  const data = { ...inline([c]), results: {} };
  await mount(<SessionView cell={c} route={route()} />, { hooksConfig: { search: `?session=${SID}`, inline: data } });
  await expect(page.locator("#SessionView")).toContainText(`no inline result for ${SID}`);
  // Metadata still renders from the cell alone.
  await expect(page.locator("#SessionMetaTable")).toBeVisible();
  await expect(page.locator("[data-xh-loading='result']")).toHaveCount(0);
  for (const id of PANELS) await expect(page.locator(`#${id}`), id).toHaveCount(0);
});

test("?turn=2 opens that turn with its records", async ({ mount, page }) => {
  const c = cell();
  await mount(<SessionView cell={c} route={route({ turn: 2 })} />, { hooksConfig: { search: `?session=${SID}&turn=2`, inline: inline([c]) } });
  const detail = page.locator("#SessionTurnTable tr.detail-row");
  await expect(detail).toHaveCount(1);
  await expect(detail).toHaveAttribute("data-n", "2");
  await expect(detail.locator(".rec[data-el='RecordCard']")).toHaveCount(3);
  for (const n of [4, 5, 6]) await expect(page.locator(`#L${n}`)).toBeVisible();
  await expect(page.locator("#SessionTurnTable tr.SessionTurnRow[data-n='2']")).toHaveClass(/row-open/);
});

test("view=detailed opens every turn", async ({ mount, page }) => {
  const c = cell();
  await mount(<SessionView cell={c} route={route({ turnView: "detailed" })} />, {
    hooksConfig: { search: `?session=${SID}&view=detailed`, inline: inline([c]) },
  });
  await expect(page.locator("#SessionTurnTable tr.detail-row")).toHaveCount(3);
  await expect(page.locator(".rec[data-el='RecordCard']")).toHaveCount(9);
  await expect(page.locator("#ViewToggle [data-state='on']")).toHaveText("Detailed view");
});

test("axis=line selects the per-line x-axis", async ({ mount, page }) => {
  const c = cell();
  await mount(<SessionView cell={c} route={route({ axis: "line" })} />, { hooksConfig: { search: `?session=${SID}&axis=line`, inline: inline([c]) } });
  await expect(page.locator("#ChartAxisToggle [data-state='on']")).toHaveText("per session-log line");
});

test("rec=raw renders every record as raw JSON", async ({ mount, page }) => {
  const c = cell();
  await mount(<SessionView cell={c} route={route({ turn: 1, rec: "raw" })} />, {
    hooksConfig: { search: `?session=${SID}&turn=1&rec=raw`, inline: inline([c]) },
  });
  await expect(page.locator("#RecordViewToggle [data-state='on']")).toHaveText("raw JSON");
  await expect(page.locator(".rec[data-el='RecordCard'] .rec-raw")).toHaveCount(3);
  await expect(page.locator(".rec[data-el='RecordCard'] .rec-nice")).toHaveCount(0);
});

test("line=5 opens its owning turn, scrolls to the record and flashes it", async ({ mount, page }) => {
  const c = cell();
  await mount(<SessionView cell={c} route={route({ line: 5 })} />, { hooksConfig: { search: `?session=${SID}&line=5`, inline: inline([c]) } });
  // records 4–6 belong to turn 2 (fixtures.call)
  await expect(page.locator("#SessionTurnTable tr.detail-row")).toHaveAttribute("data-n", "2");
  const target = page.locator("#L5");
  await expect(target).toHaveClass(/xh-target/);
  await expect(target).toBeInViewport();
  await expect(page.locator("#L4")).not.toHaveClass(/xh-target/);
  // The flash is transient.
  await expect(target).not.toHaveClass(/xh-target/, { timeout: 5_000 });
});

test("every control writes the whole route back to the URL", async ({ mount, page }) => {
  const c = cell();
  await mount(<SessionView cell={c} route={route()} />, { hooksConfig: { search: `?session=${SID}`, inline: inline([c]) } });
  await expect(page.locator("#SessionTurnTable tbody tr.SessionTurnRow")).toHaveCount(3);

  await page.locator("#SessionTurnTable tr.SessionTurnRow[data-n='1']").click();
  await expect.poll(() => search(page)).toBe(`?session=${SID}&turn=1&view=summary`);
  await expect(page.locator("#SessionTurnTable tr.detail-row")).toHaveAttribute("data-n", "1");

  await page.locator("#ChartAxisToggle").getByText("per session-log line").click();
  await expect.poll(() => search(page)).toBe(`?session=${SID}&turn=1&view=summary&axis=line`);
  await expect(page.locator("#ChartAxisToggle [data-state='on']")).toHaveText("per session-log line");

  await page.locator("#RecordViewToggle").getByText("raw JSON").click();
  await expect.poll(() => search(page)).toBe(`?session=${SID}&turn=1&view=summary&axis=line&rec=raw`);
  await expect(page.locator(".rec[data-el='RecordCard'] .rec-raw")).toHaveCount(3);

  await page.locator("#ViewToggle").getByText("detailed").click();
  await expect.poll(() => search(page)).toBe(`?session=${SID}&turn=1&view=detailed&axis=line&rec=raw`);
  await expect(page.locator("#SessionTurnTable tr.detail-row")).toHaveCount(3);

  // Back to the defaults: an absent param is the default, so they drop out of the URL.
  await page.locator("#ChartAxisToggle").getByText("per turn").click();
  await page.locator("#RecordViewToggle").getByText("nice records").click();
  await expect.poll(() => search(page)).toBe(`?session=${SID}&turn=1&view=detailed`);
});

test("clicking an open turn closes it and drops turn= from the URL", async ({ mount, page }) => {
  const c = cell();
  await mount(<SessionView cell={c} route={route({ turn: 3 })} />, { hooksConfig: { search: `?session=${SID}&turn=3`, inline: inline([c]) } });
  await expect(page.locator("#SessionTurnTable tr.detail-row")).toHaveAttribute("data-n", "3");
  await page.locator("#SessionTurnTable tr.SessionTurnRow[data-n='3']").click();
  await expect(page.locator("#SessionTurnTable tr.detail-row")).toHaveCount(0);
  await expect.poll(() => search(page)).toBe(`?session=${SID}&view=summary`);
});

test("the theme param survives a control write", async ({ mount, page }) => {
  const c = cell();
  await mount(<SessionView cell={c} route={route({ theme: "dark" })} />, { hooksConfig: { search: `?session=${SID}&theme=dark`, inline: inline([c]) } });
  await page.locator("#ChartAxisToggle").getByText("per session-log line").click();
  await expect.poll(() => search(page)).toBe(`?session=${SID}&view=summary&axis=line&theme=dark`);
});
