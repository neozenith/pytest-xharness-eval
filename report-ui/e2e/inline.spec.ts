/**
 * The inline smoke (`make ui-smoke`): the built page, populated the way
 * `report.py --inline` populates it, opened over `file://` in a real browser. Proves the
 * bundle boots with zero network, the data binds, and every element id the glossary names
 * is on the page once a session is open. Set `XH_INLINE_HTML` to the populated page
 * (scripts/inline.py writes it); without it this spec skips so `bun run e2e` can run the
 * matrix alone.
 */
import path from "node:path";
import { expect, test } from "@playwright/test";
import { collectConsole, OUT_ROOT, settle, writeArtifacts } from "./helpers";

const INLINE = process.env.XH_INLINE_HTML;

/** Every element id the glossary names must be on the page once a session is open. */
const GLOSSARY_IDS = [
  "ReportHeader",
  "NavSidebar",
  "NavToggle",
  "ReportTitle",
  "ReportMeta",
  "ThemeToggle",
  "SessionView",
  "SessionHeader",
  "SessionTitle",
  "SessionMetaTable",
  "ChartAxisToggle",
  "TokenWaterfallChart",
  "ContextWindowChart",
  "ContextWindowNote",
  "ReconciliationPanel",
  "CostByTierPanel",
  "RatesApplied",
  "OutputPerTurnChart",
  "TurnTiersChart",
  "SkillCoveragePanelWrap",
  "SkillCoveragePanel",
  "SkillCoverageSummary",
  "ShowIgnored",
  "RecordKindsPanel",
  "SessionTurnTablePanel",
  "SessionTurnTable",
  "ViewToggle",
  "RecordViewToggle",
  "FinalMessagePanel",
  "FinalMessage",
];

test("inline page boots over file:// and binds the captured data", async ({ page }) => {
  test.skip(!INLINE, "XH_INLINE_HTML not set: run via `make ui-smoke CAPTURED=…`");
  const url = `file://${path.resolve(INLINE!)}`;
  const consoleEntries = collectConsole(page);

  await page.goto(url, { waitUntil: "load" });
  await settle(page);
  const rows = page.locator("#SessionTable tbody tr");
  expect(await rows.count()).toBeGreaterThan(0);
  const sid = await rows.first().getAttribute("data-sid");
  expect(sid).toBeTruthy();

  // Open the first session and check the glossary parity list.
  await page.goto(`${url}?session=${sid}`, { waitUntil: "load" });
  await settle(page);
  const missing: string[] = [];
  for (const id of GLOSSARY_IDS) {
    if ((await page.locator(`#${id}`).count()) === 0) missing.push(id);
  }
  expect(missing, "glossary element ids missing from an open session").toEqual([]);

  // A turn opened in the detailed view renders its records.
  await page.goto(`${url}?session=${sid}&turn=1&view=detailed`, { waitUntil: "load" });
  await settle(page);
  expect(await page.locator("[data-el='RecordCard']").count()).toBeGreaterThan(0);

  // Back on the overview the accumulation chart mounts again, with the filter control and the
  // summary the glossary says sit beside it. (The `GLOSSARY_IDS` parity list is checked with a
  // session open, so the overview's own ids are asserted here instead.)
  await page.goto(`${url}`, { waitUntil: "load" });
  await settle(page);
  await expect(page.locator("#OverviewFilters")).toBeVisible();
  await expect(page.locator("#TokenAccumulationChart")).toBeVisible();
  await expect(page.locator("#TokenWaterfallAggregateChart")).toBeVisible();

  // The two charts are a row, not a stack, at this viewport — and their plots start on the same
  // line, which is what makes them comparable rather than merely adjacent.
  const charts = await page.evaluate(() => {
    const grid = document.getElementById("OverviewCharts");
    const tops = [...(grid?.children ?? [])].map((c) => Math.round(c.getBoundingClientRect().top));
    const plots = [...document.querySelectorAll("#OverviewCharts [role='img']")].map((e) => Math.round(e.getBoundingClientRect().top));
    return {
      cards: tops.length,
      sameRow: tops.length === 2 && tops[0] === tops[1],
      plots: plots.length,
      plotDelta: plots.length === 2 ? plots[1]! - plots[0]! : null,
    };
  });
  expect(charts).toEqual({ cards: 2, sameRow: true, plots: 2, plotDelta: 0 });
  await expect(page.locator("#SessionSummaryTable")).toBeVisible();

  // The column budget: the sessions table has to fit its card without a horizontal scrollbar,
  // which is the whole point of dropping the id column, merging the two cost columns and
  // abbreviating the token counts. Measured, not asserted from the column count.
  const overflow = await page.evaluate(() => {
    const box = document.querySelector("#SessionTable")?.closest("[data-slot='table-container']");
    return box ? box.scrollWidth - box.clientWidth : -1;
  });
  // `>= 0` as well as `<= 1`: the probe returns -1 when it cannot find the box at all, and a
  // one-sided assertion would have passed on a renamed id rather than failing on it.
  expect(overflow).toBeGreaterThanOrEqual(0);
  expect(overflow).toBeLessThanOrEqual(1);

  const errors = consoleEntries.filter((e) => e.type === "error" || e.type === "pageerror");
  writeArtifacts(path.join(OUT_ROOT, "inline"), { "console.json": consoleEntries.slice() });
  await page.screenshot({ path: path.join(OUT_ROOT, "inline", "screenshot.png"), fullPage: true, animations: "disabled" });
  expect(errors.map((e) => `${e.type}: ${e.text}`)).toEqual([]);
});
