/**
 * The findings from the adversarial design review, each pinned by the behaviour it
 * asked for rather than by the markup that happens to deliver it.
 *
 * These are grouped in one file on purpose: they are one class of defect. In every
 * case the app knew something the reader needed (data was dropped, the selection is
 * off-screen, the totals are vacuous) and simply did not say it, or said it somewhere
 * the reader might never scroll to. Nothing here is a rendering bug, which is exactly
 * why nothing here was caught by the specs that assert on rendering.
 */
import { expect, test } from "@playwright/test";
import { loadFixtureGraph, routeFixtureGraph, setRangeValue } from "./helpers";

/** Finding #8: the default view answers something before the reader touches a control. */
test("the landing view names the most-called definition and the conductance extremes", async ({ page }) => {
  await routeFixtureGraph(page, loadFixtureGraph());
  await page.goto("/");

  const lede = page.getByTestId("lede");
  // TargetFn is the fixture's only node above leverage 1 (3 callers, 3 sites).
  await expect(lede).toContainText("TargetFn");
  await expect(lede).toContainText("3 callers, 3 call sites");
  await expect(lede).toContainText("fixture_py/pkg_a/mod1.py");
  // Folder boundary: pkg_a 0.037 is the lowest phi, pkg_c 0.059 the highest.
  await expect(lede).toContainText("3 measurable folder clusters");
  await expect(lede).toContainText("least at pkg_a");
  await expect(lede).toContainText("0.037");
  await expect(lede).toContainText("most at pkg_c");
  await expect(lede).toContainText("0.059");

  // The lede is in the header, which never scrolls -- the point of putting it there.
  await expect(page.locator("header [data-testid=lede]")).toBeVisible();
});

/** Finding #8, second half: the lede's link is a real selection, not decoration. */
test("the lede's definition link selects that definition", async ({ page }) => {
  await routeFixtureGraph(page, loadFixtureGraph());
  await page.goto("/");

  await page.getByTestId("lede").getByRole("button", { name: "TargetFn" }).click();
  await expect(page.getByTestId("detail")).toContainText("TargetFn");
});

/** Finding #3: the data-loss banner and the bands caveat are out of the scrolling sidebar. */
test("the slice count and the bands caveat render in the main column, not the sidebar", async ({ page }) => {
  await routeFixtureGraph(page, loadFixtureGraph());
  await page.goto("/");

  // Asserted by ancestry, not by position: "is it inside the region that scrolls away"
  // is the actual finding, and a pixel assertion would pass the day someone moves it
  // back into `aside.left` and gives that sidebar a taller viewport.
  await expect(page.locator("section.middle [data-testid=shown]")).toBeVisible();
  await expect(page.locator("section.middle [data-testid=caveat]")).toBeVisible();
  await expect(page.locator("aside.left [data-testid=shown]")).toHaveCount(0);
  await expect(page.locator("aside.left [data-testid=caveat]")).toHaveCount(0);
  await expect(page.getByTestId("caveat")).toContainText("rank, they do not grade");
});

/** Finding #6: a selection the current slice does not draw says so, and says why. */
test("a selected definition excluded by a filter is reported as not drawn", async ({ page }) => {
  await routeFixtureGraph(page, loadFixtureGraph());
  await page.goto("/");

  await page.getByRole("button", { name: "View graph as table" }).click();
  await page
    .locator("[data-testid=graph-table] tbody tr", { hasText: "TargetFn" })
    .getByRole("button", { name: "Select" })
    .click();
  await expect(page.getByTestId("detail")).toContainText("TargetFn");
  await expect(page.getByTestId("off-slice")).toHaveCount(0);

  // Narrow the view to something TargetFn is not.
  await page.getByTestId("search").fill("CalleeX");
  await expect(page.getByTestId("shown")).toContainText("showing 1 of 1");

  const notice = page.getByTestId("off-slice");
  await expect(notice).toContainText("Not drawn in the current view");
  await expect(notice).toContainText("a filter excludes it");
  // The detail panel still describes it -- the selection is not silently dropped.
  await expect(page.getByTestId("detail")).toContainText("TargetFn");
});

/** Finding #6 again: the cap is a different cause, and gets a different remedy. */
test("a selected definition pushed out by the node cap names the cap, not the filters", async ({ page }) => {
  await routeFixtureGraph(page, loadFixtureGraph());
  await page.goto("/");

  // Filler3 has leverage 0. The slice ranks by the active metric before capping, and
  // the fixture has exactly 50 nodes above leverage 0 -- so a 50-node cap drops every
  // orphan and keeps everything else, with no filter involved.
  await page.getByRole("button", { name: "View graph as table" }).click();
  // Matched on the exact Name cell, not `hasText`: the fixture also holds Filler30
  // through Filler39, and a substring row match picks whichever of those the ranking
  // put first -- a non-orphan that the cap never touches.
  await page
    .locator("[data-testid=graph-table] tbody tr")
    .filter({ has: page.getByRole("cell", { name: "Filler3", exact: true }) })
    .getByRole("button", { name: "Select" })
    .click();
  await expect(page.getByTestId("detail")).toContainText("Filler3");
  await expect(page.getByTestId("off-slice")).toHaveCount(0);

  await setRangeValue(page.getByTestId("limit"), 50);
  const notice = page.getByTestId("off-slice");
  await expect(notice).toContainText("outside the node cap");
  await expect(notice).toContainText("Max nodes");
});

/** Finding #7: WCAG 2.4.1. The accessible table must not be a 150-stop tab corridor. */
test("the graph table can be skipped past with the keyboard", async ({ page }) => {
  await routeFixtureGraph(page, loadFixtureGraph());
  await page.goto("/");
  await page.getByRole("button", { name: "View graph as table" }).click();

  const skip = page.getByRole("link", { name: /Skip past the graph table/ });
  // Measured, not `toBeVisible`. The `.sr-only` technique keeps the element rendered
  // and 1px square with its paint clipped away, precisely so it stays in the
  // accessibility tree -- and Playwright, which asks for a non-empty box rather than
  // for paint, calls that visible. The assertion has to be the size, or it is testing
  // the opposite of what the technique does.
  expect((await skip.boundingBox())!.width).toBeLessThanOrEqual(2);
  await skip.focus();
  expect((await skip.boundingBox())!.width).toBeGreaterThan(100);

  await page.keyboard.press("Enter");
  // Focus, not just scroll position. An anchor that moves the viewport and leaves the
  // focus ring 150 rows behind has bypassed nothing for a keyboard user.
  await expect(page.locator("#graph-table-end")).toBeFocused();
});

/** Finding #9: a zero-node graph must not render as a flawless one. */
test("an empty graph refuses to report 0% orphans and 100% resolved", async ({ page }) => {
  const graph = loadFixtureGraph();
  graph.nodes = [];
  graph.edges = [];
  graph.clusters = { language: {}, folder: {}, file: {}, class: {} };
  graph.totals = {
    ...graph.totals,
    nodes: 0,
    edges: 0,
    callSites: 0,
    orphanPct: 0,
    resolvedPct: 100,
  };
  await routeFixtureGraph(page, graph);
  await page.goto("/");

  const empty = page.getByTestId("empty-graph");
  await expect(empty).toBeVisible();
  await expect(empty).toContainText("no definitions");
  await expect(empty).toContainText("arithmetic over an empty set, not findings");
  // The normal chrome -- which would have printed those two numbers as if they were
  // findings -- is not rendered at all.
  await expect(page.getByTestId("header")).toHaveCount(0);
  await expect(page.getByTestId("graph-canvas")).toHaveCount(0);
});
