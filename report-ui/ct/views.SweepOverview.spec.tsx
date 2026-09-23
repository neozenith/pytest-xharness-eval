/**
 * `SweepOverview` (ADR 0042, ADR 0049): the view derives the filtered cells once and hands the
 * same array to both charts and both tables, so every assertion here reads all four consumers.
 * The filter lives in the URL, so a deeplink (`hooksConfig.search`) and a chip click must land on
 * the same page.
 */
import { expect, test } from "@playwright/experimental-ct-react";
import type { Locator, Page } from "@playwright/test";
import { SweepOverview } from "../src/views/SweepOverview";
import { NO_MATCH } from "../src/lib/facets";
import type { HooksConfig } from "../playwright/index";
import { cell, index, inline, sweep } from "./fixtures";

/** The fixture sweep plus a second `high` run of the same arm, so one summary group holds two runs. */
const cells = () => [...sweep(), cell({ session_id: "aaaaaaaa-0005", effort: "high", estimated_cost_usd: 1.4, verdict: "pass" })];

const rows = (page: Page): Locator => page.locator("#SessionTable tbody tr.SessionRow");
const summaryRows = (page: Page): Locator => page.locator("#SessionSummaryTable tbody tr[data-key]");
/** A summary column's body text, found by its head's `data-k` (the body cells carry no key). */
const summaryColumn = (page: Page, key: string): Promise<string[]> =>
  page.locator("#SessionSummaryTable").evaluate((table, k) => {
    const i = [...table.querySelectorAll("thead th")].findIndex((th) => th.getAttribute("data-k") === k);
    return [...table.querySelectorAll("tbody tr[data-key]")].map((tr) => (tr.children[i] as HTMLElement).innerText.trim());
  }, key);
const accumulationLegend = (page: Page): Locator => page.locator("#TokenAccumulationChart [data-el='ChartLegend'] button");

const mountAt = async (mount: (c: React.JSX.Element, o: { hooksConfig: HooksConfig }) => Promise<Locator>, search = "?", data = cells()) =>
  mount(<SweepOverview index={index(data)} />, { hooksConfig: { search, inline: inline(data) } });

test("unfiltered: every session, every group, one accumulation line per arm", async ({ mount, page }) => {
  const c = await mountAt(mount);
  await expect(c).toBeVisible();
  await expect(rows(page)).toHaveCount(8);
  await expect(page.locator("#SessionCount")).toHaveText("(8)");
  // Seven arms: the two `high` runs of opus share a group.
  await expect(page.locator("#SummaryCount")).toHaveText("(7 groups)");
  await expect(summaryRows(page)).toHaveCount(7);
  await expect(accumulationLegend(page)).toHaveCount(7);
  await expect(page.locator("#TokenWaterfallAggregateChart")).toContainText("averaged over 8 runs");
  await expect(page.locator("#OverviewFilterCount")).toContainText("8 sessions");
  await expect(page.locator("#OverviewFiltersClear")).toHaveAttribute("aria-hidden", "true");
});

test("the summary splits one model into one row per rung, in ladder order, rung-less last", async ({ mount, page }) => {
  await mountAt(mount, "?model=claude-opus-5");
  await expect(summaryRows(page)).toHaveCount(4);
  expect(await summaryColumn(page, "effort")).toEqual(["low", "high", "max", "–"]);
  // The two `high` runs are one group of two, not two groups.
  const high = page.locator("#SessionSummaryTable tbody tr[data-key$='|high']");
  await expect(high).toHaveCount(1);
  await expect(page.locator("#SummaryCount")).toHaveText("(4 groups)");
  await expect(page.locator("#SessionCount")).toHaveText("(5 of 8)");
});

test("?harness=codex deeplink narrows both charts and both tables", async ({ mount, page }) => {
  await mountAt(mount, "?harness=codex");
  await expect(rows(page)).toHaveCount(2);
  await expect(page.locator("#SessionCount")).toHaveText("(2 of 8)");
  await expect(page.locator("#SummaryCount")).toHaveText("(2 groups)");
  await expect(accumulationLegend(page)).toHaveCount(2);
  await expect(page.locator("#TokenWaterfallAggregateChart")).toContainText("averaged over 2 runs");
  await expect(page.locator("#OverviewFilterCount")).toContainText("2 of 8 sessions");
  await expect(page.locator(".filter-chip[data-facet='harness'][data-value='codex']")).toHaveAttribute("aria-pressed", "true");
  for (const sid of await rows(page).evaluateAll((trs) => trs.map((tr) => tr.getAttribute("data-sid")))) expect(sid).toMatch(/^cccccccc-/);
});

test("?effort=high narrows everything to the one rung", async ({ mount, page }) => {
  await mountAt(mount, "?effort=high");
  await expect(rows(page)).toHaveCount(2);
  await expect(page.locator("#SessionCount")).toHaveText("(2 of 8)");
  await expect(page.locator("#SummaryCount")).toHaveText("(1 group)");
  await expect(summaryRows(page)).toHaveCount(1);
  await expect(accumulationLegend(page)).toHaveCount(1);
  await expect(accumulationLegend(page)).toContainText("high");
  await expect(accumulationLegend(page)).toContainText("n=2");
  await expect(page.locator("#TokenWaterfallAggregateChart")).toContainText("averaged over 2 runs");
  // A rung-less (pre-ADR 0049) session never matches a rung selection.
  await expect(page.locator("#SessionTable tr[data-sid='aaaaaaaa-0004']")).toHaveCount(0);
});

test("the effort chips come in ladder order, not alphabetical", async ({ mount, page }) => {
  await mountAt(mount);
  const chips = page.locator(".filter-chip[data-facet='effort']");
  await expect(chips).toHaveCount(5);
  expect(await chips.evaluateAll((els) => els.map((e) => e.getAttribute("data-value")))).toEqual(["low", "medium", "high", "xhigh", "max"]);
});

test("a chip click writes the URL and ripples to every consumer; clear restores the sweep", async ({ mount, page }) => {
  await mountAt(mount);
  await page.locator(".filter-chip[data-facet='harness'][data-value='codex']").click();
  await expect.poll(() => page.evaluate(() => location.search)).toBe("?harness=codex");
  await expect(rows(page)).toHaveCount(2);
  await expect(page.locator("#SessionCount")).toHaveText("(2 of 8)");
  await expect(page.locator("#SummaryCount")).toHaveText("(2 groups)");
  await expect(accumulationLegend(page)).toHaveCount(2);
  await expect(page.locator("#TokenWaterfallAggregateChart")).toContainText("averaged over 2 runs");

  // AND across facets: codex × low is the one luna run.
  await page.locator(".filter-chip[data-facet='effort'][data-value='low']").click();
  await expect.poll(() => page.evaluate(() => location.search)).toBe("?harness=codex&effort=low");
  await expect(rows(page)).toHaveCount(1);
  await expect(page.locator("#SessionCount")).toHaveText("(1 of 8)");

  await page.locator("#OverviewFiltersClear").click();
  await expect.poll(() => page.evaluate(() => location.search)).toBe("");
  await expect(rows(page)).toHaveCount(8);
  await expect(page.locator("#SessionCount")).toHaveText("(8)");
  await expect(page.locator("#SummaryCount")).toHaveText("(7 groups)");
});

test("a filter that selects nothing says NO_MATCH in the chart and both tables", async ({ mount, page }) => {
  await mountAt(mount, "?harness=codex&model=claude-opus-5");
  await expect(page.locator("#SessionCount")).toHaveText("(0 of 8)");
  await expect(page.locator("#SummaryCount")).toHaveText("(0 groups)");
  await expect(page.locator("#TokenAccumulationChart")).toContainText(NO_MATCH);
  await expect(page.locator("#SessionSummaryTable td.empty")).toHaveText(NO_MATCH);
  await expect(page.locator("#SessionTable td.empty")).toHaveText(NO_MATCH);
  // The chart must not accuse a filtered-to-nothing reader of having no ledger.
  await expect(page.locator("#TokenAccumulationChart")).not.toContainText("No session with a per-call ledger");
  await expect(page.locator("#TokenWaterfallAggregateChart")).toContainText("averaged over 0 runs");
});

test("a stale deeplink value round-trips as a lit chip and matches nothing", async ({ mount, page }) => {
  await mountAt(mount, "?skill=__gone__");
  const chip = page.locator(".filter-chip[data-facet='skill'][data-value='__gone__']");
  await expect(chip).toHaveAttribute("aria-pressed", "true");
  await expect(page.locator("#SessionTable td.empty")).toHaveText(NO_MATCH);
  await expect(page.locator("#SessionCount")).toHaveText("(0 of 8)");
});

test("short model names are derived from the unfiltered sweep, not the filtered subset", async ({ mount, page }) => {
  // `anthropic-opus-5` and `claude-opus-5` both shorten to `opus-5`, so the sweep keeps full names.
  // Filtered to claude the collision is off-screen, and the names must not re-shorten under it.
  const data = [
    cell({ session_id: "s-1", model: "claude-opus-5" }),
    cell({ session_id: "s-2", model: "claude-sonnet-5" }),
    cell({ session_id: "s-3", harness: "codex", model: "anthropic-opus-5" }),
  ];
  await mountAt(mount, "?harness=claude", data);
  await expect(rows(page)).toHaveCount(2);
  await expect(page.locator("#SessionTable tbody td[data-k='model']")).toHaveText(["claude-opus-5", "claude-sonnet-5"], { useInnerText: true });
  await expect(summaryRows(page)).toHaveCount(2);
  expect(await summaryColumn(page, "model")).toEqual(["claude-opus-5", "claude-sonnet-5"]);
});

test("without a collision the tables print the short model name", async ({ mount, page }) => {
  const data = [cell({ session_id: "s-1", model: "claude-opus-5" }), cell({ session_id: "s-2", model: "claude-sonnet-5" })];
  await mountAt(mount, "?", data);
  // SessionTable sorts by `at` descending by default; both share one timestamp, so compare as a set.
  const models = await page.locator("#SessionTable tbody td[data-k='model']").allInnerTexts();
  expect(models.sort()).toEqual(["opus-5", "sonnet-5"]);
});

/*
 * A push is witnessed by Back, not by `history.length`. CT reuses one page per worker, and once
 * earlier tests have walked it to Chromium's 50-entry cap a push drops the oldest entry and the
 * length stays 50: under a full parallel suite `before + 1` read 51 against 50. Back landing on
 * the overview is what a push means to a reader, and a replace would have left nothing to return to.
 */
test("clicking a session row pushes the session route", async ({ mount, page }) => {
  await mountAt(mount);
  await page.locator("#SessionTable tr[data-sid='bbbbbbbb-0001'] td[data-k='case']").click();
  await expect.poll(() => page.evaluate(() => location.search)).toBe("?session=bbbbbbbb-0001");
  await page.evaluate(() => history.back());
  await expect.poll(() => page.evaluate(() => location.search)).toBe("");
});
