/**
 * Round-1 accessibility fixes to GraphCanvas.tsx: the accessible table's Callers/Callees
 * columns, its roving-tabindex keyboard navigation and rebuild-safe focus recovery, and
 * the toolbar's live row count. Each behaviour here is new in this round; nothing below
 * duplicates keyboard.spec.ts (Tab reachability), selection.spec.ts (the selection path)
 * or a11y.spec.ts (the baseline page-level scans) -- see each test's own comment for what
 * specifically it pins.
 */
import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import { loadFixtureGraph, routeFixtureGraph, setRangeValue } from "./helpers";

const WCAG_TAGS = ["wcag2a", "wcag2aa", "wcag2aaa"];

test.beforeEach(async ({ page }) => {
  await routeFixtureGraph(page, loadFixtureGraph());
  await page.goto("/");
  await expect(page.getByTestId("header")).toBeVisible();
  await page.getByRole("button", { name: "View graph as table" }).click();
});

test("the Callers/Callees columns report TargetFn's real in/out edge counts", async ({ page }) => {
  // selection.spec.ts already establishes TargetFn as 3 distinct callers (CallerA/B/C)
  // and 2 distinct callees (CalleeX/Y) via the detail panel's "Called by (3)"/"Calls
  // (2)" text. The table used to stop at Name/Cluster/Band/Value and never mention
  // edges at all -- these two new columns are the same fact, read from the table
  // instead of the detail panel, without having to select the row first.
  const targetRow = page.locator("[data-testid=graph-table] tbody tr", { hasText: "TargetFn" });
  const cells = targetRow.locator("td");
  await expect(cells.nth(3)).toHaveText("3"); // Value column, unchanged position
  await expect(cells.nth(4)).toHaveText("3"); // Callers
  await expect(cells.nth(5)).toHaveText("2"); // Callees
});

test("the toolbar note is a live region that reports the current row count", async ({ page }) => {
  const note = page.getByTestId("graph-note");
  await expect(note).toHaveAttribute("role", "status");
  await expect(note).toContainText("60 definitions drawn");

  // Narrowing the graph with the search field (already pinned as keyboard-operable in
  // keyboard.spec.ts) rebuilds `elements`, and this note must track the new count
  // without needing the table re-opened or re-scanned -- that's what aria-live is for.
  // "targetfn" narrows the fixture to exactly one match (filters.spec.ts's "showing 1
  // of 1"), which singularises "definition" -- pinned here, not just in
  // singular-counts.spec.ts, so a future edit to this count can't silently regress
  // the noun's number without failing the test that already covers this exact search.
  await page.getByTestId("search").fill("targetfn");
  await expect(note).toContainText("1 definition drawn");
});

test("roving tabindex: only one Select button is a Tab stop, and Arrow/Home/End move it", async ({ page }) => {
  const buttons = page.locator("[data-testid=graph-table] tbody tr button");
  const count = await buttons.count();
  expect(count, "fixture should draw more than a couple of rows").toBeGreaterThan(2);

  const first = buttons.nth(0);
  const second = buttons.nth(1);
  const last = buttons.nth(count - 1);

  await first.focus();
  await expect(first).toBeFocused();
  await expect(first).toHaveAttribute("tabindex", "0");
  await expect(second).toHaveAttribute("tabindex", "-1");

  await page.keyboard.press("ArrowDown");
  await expect(second).toBeFocused();
  await expect(second).toHaveAttribute("tabindex", "0");
  await expect(first).toHaveAttribute("tabindex", "-1");

  await page.keyboard.press("End");
  await expect(last).toBeFocused();
  await expect(last).toHaveAttribute("tabindex", "0");

  await page.keyboard.press("Home");
  await expect(first).toBeFocused();

  // Clamped, not wrapped: ArrowUp at the first row must not move focus off the table.
  await page.keyboard.press("ArrowUp");
  await expect(first).toBeFocused();
});

test("focus recovers into the table when its focused row is dropped by a rebuild", async ({ page }) => {
  // Rows are rendered in rank order (toElements sorts descending by the active
  // metric before slicing to `limit`), so the LAST row is always among the first
  // dropped when the cap tightens -- and TargetFn, the fixture's unique leverage>=2
  // node, is always rank 0 and so is never dropped by any cap above zero. That makes
  // both ends of this test deterministic without hardcoding which row is which by name.
  const buttons = page.locator("[data-testid=graph-table] tbody tr button");
  const count = await buttons.count();
  const lastLabel = await page
    .locator("[data-testid=graph-table] tbody tr")
    .nth(count - 1)
    .locator("td")
    .first()
    .textContent();
  await buttons.nth(count - 1).focus();
  await expect(buttons.nth(count - 1)).toBeFocused();

  // Driven through the same property-setter helper keyboard.spec.ts's range test
  // relies on, and deliberately WITHOUT focusing the slider itself: focus must stay
  // on the row's own button right up until the rebuild removes it from the document,
  // so the only way focus can end up elsewhere is this component's own recovery
  // effect -- not a side effect of the test moving focus itself.
  await setRangeValue(page.getByTestId("limit"), 50);
  await expect(page.getByTestId("shown")).toContainText("hidden by the 50-node cap");

  const targetRow = page.locator("[data-testid=graph-table] tbody tr", { hasText: "TargetFn" });
  const targetButton = targetRow.getByRole("button");
  await expect(targetButton).toBeFocused();
  // Sanity: the row that used to be last is actually gone, not just re-sorted --
  // otherwise this test would pass even if the dropped row had simply moved.
  if (lastLabel && lastLabel !== "TargetFn") {
    await expect(page.locator("[data-testid=graph-table] tbody tr", { hasText: lastLabel })).toHaveCount(0);
  }
});

test("the graph table with roving-tabindex focus on a non-first row has zero WCAG a/aa/aaa violations", async ({
  page,
}) => {
  const buttons = page.locator("[data-testid=graph-table] tbody tr button");
  await buttons.nth(0).focus();
  await page.keyboard.press("ArrowDown");
  await page.keyboard.press("ArrowDown");
  await expect(buttons.nth(2)).toBeFocused();

  const results = await new AxeBuilder({ page }).withTags(WCAG_TAGS).analyze();
  expect(results.violations, JSON.stringify(results.violations, null, 2)).toEqual([]);
});

test("the post-rebuild focus-recovered table state has zero WCAG a/aa/aaa violations", async ({ page }) => {
  const buttons = page.locator("[data-testid=graph-table] tbody tr button");
  const count = await buttons.count();
  await buttons.nth(count - 1).focus();
  await setRangeValue(page.getByTestId("limit"), 50);
  await expect(page.getByTestId("shown")).toContainText("hidden by the 50-node cap");

  const results = await new AxeBuilder({ page }).withTags(WCAG_TAGS).analyze();
  expect(results.violations, JSON.stringify(results.violations, null, 2)).toEqual([]);
});
