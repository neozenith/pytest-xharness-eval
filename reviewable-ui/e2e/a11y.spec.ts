/**
 * Accessibility. The project targets WCAG AAA (see docs/plans/maintainability), so this
 * asserts zero violations across wcag2a, wcag2aa AND wcag2aaa. If axe finds a real
 * violation, this test is left failing on purpose (see the final report) rather than
 * narrowing the tag list to make it pass.
 */
import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import { loadFixtureGraph, routeFixtureGraph, setRangeValue } from "./helpers";

const WCAG_TAGS = ["wcag2a", "wcag2aa", "wcag2aaa"];

test("initial view has zero WCAG a/aa/aaa violations", async ({ page }) => {
  await routeFixtureGraph(page, loadFixtureGraph());
  await page.goto("/");
  await expect(page.getByTestId("header")).toBeVisible();
  await expect(page.locator("[data-testid=cluster-table] tbody tr")).not.toHaveCount(0);

  const results = await new AxeBuilder({ page }).withTags(WCAG_TAGS).analyze();
  expect(results.violations, JSON.stringify(results.violations, null, 2)).toEqual([]);
});

test("the selected-node detail + accessible graph table have zero WCAG a/aa/aaa violations", async ({ page }) => {
  await routeFixtureGraph(page, loadFixtureGraph());
  await page.goto("/");
  await expect(page.getByTestId("header")).toBeVisible();

  // Select via the app's own accessible alternative to the canvas (GraphCanvas.tsx's
  // "View graph as table"), leaving that region expanded for the scan too.
  await page.getByRole("button", { name: "View graph as table" }).click();
  const targetRow = page.locator("[data-testid=graph-table] tbody tr", { hasText: "TargetFn" });
  await targetRow.getByRole("button", { name: "Select" }).click();
  await expect(page.getByTestId("detail")).toContainText("TargetFn");

  const results = await new AxeBuilder({ page }).withTags(WCAG_TAGS).analyze();
  expect(results.violations, JSON.stringify(results.violations, null, 2)).toEqual([]);
});

test("the fatal error view has zero WCAG a/aa/aaa violations", async ({ page }) => {
  await page.route("**/graph.json*", async (route) => {
    await route.fulfill({ status: 404, contentType: "text/plain", body: "not found" });
  });
  await page.goto("/");
  await expect(page.getByTestId("fatal")).toBeVisible();

  const results = await new AxeBuilder({ page }).withTags(WCAG_TAGS).analyze();
  expect(results.violations, JSON.stringify(results.violations, null, 2)).toEqual([]);
});

/**
 * The two warning banners, which none of the scans above ever render.
 *
 * This is the gap that let a real AAA failure ship: `.banner` paints
 * rgba(245,158,11,0.12) over `--panel`, so `.warn.banner` text reads against the
 * composite rather than the token's nominal background, and `--warn` scored 6.64:1
 * there while the stylesheet's own comment table certified it at 8.07:1. Every scan
 * above passed, because the orphan banner needs `orphanPct > 40` (the fixture is at
 * 16.7%) and the cap banner needs the node cap to actually bite (it does not at the
 * default limit of 150 for a 60-node graph). A state no test enters is a state no
 * gate checks.
 */
test("both warning banners have zero WCAG a/aa/aaa violations", async ({ page }) => {
  const graph = loadFixtureGraph();
  // Mutating the fixture's own totals, not the app: these are input values the
  // extractor reports, and a high orphan rate is exactly the case the banner is for.
  graph.totals.orphanPct = 62;
  graph.totals.resolvedPct = 38;
  await routeFixtureGraph(page, graph);
  await page.goto("/");

  const orphanBanner = page.locator("header p.banner");
  await expect(orphanBanner).toContainText("62% of definitions have no caller");

  // Drive the cap below the fixture's 60 nodes so the data-loss banner renders too.
  await setRangeValue(page.getByTestId("limit"), 50);
  await expect(page.getByTestId("shown")).toContainText("hidden by the 50-node cap");

  const results = await new AxeBuilder({ page }).withTags(WCAG_TAGS).analyze();
  expect(results.violations, JSON.stringify(results.violations, null, 2)).toEqual([]);
});

/**
 * The two states the design review added, scanned for the same reason the banners
 * above are: a state no test enters is a state no gate checks, and "it is new" is the
 * worst possible reason to trust it.
 */
test("the empty-graph view has zero WCAG a/aa/aaa violations", async ({ page }) => {
  const graph = loadFixtureGraph();
  graph.nodes = [];
  graph.edges = [];
  graph.clusters = { language: {}, folder: {}, file: {}, class: {} };
  graph.totals = { ...graph.totals, nodes: 0, edges: 0, callSites: 0, orphanPct: 0, resolvedPct: 100 };
  await routeFixtureGraph(page, graph);
  await page.goto("/");
  await expect(page.getByTestId("empty-graph")).toBeVisible();

  const results = await new AxeBuilder({ page }).withTags(WCAG_TAGS).analyze();
  expect(results.violations, JSON.stringify(results.violations, null, 2)).toEqual([]);
});

test("the off-slice notice and the focused skip link have zero WCAG a/aa/aaa violations", async ({ page }) => {
  await routeFixtureGraph(page, loadFixtureGraph());
  await page.goto("/");
  await page.getByRole("button", { name: "View graph as table" }).click();
  await page
    .locator("[data-testid=graph-table] tbody tr", { hasText: "TargetFn" })
    .getByRole("button", { name: "Select" })
    .click();
  await page.getByTestId("search").fill("CalleeX");
  await expect(page.getByTestId("off-slice")).toBeVisible();

  // Focused, because the skip link paints nothing until it is -- and an off-screen
  // element is one axe's colour-contrast rule declines to evaluate. Scanning it
  // unfocused would return a pass that means "not checked".
  await page.getByRole("link", { name: /Skip past the graph table/ }).focus();

  const results = await new AxeBuilder({ page }).withTags(WCAG_TAGS).analyze();
  expect(results.violations, JSON.stringify(results.violations, null, 2)).toEqual([]);
});
