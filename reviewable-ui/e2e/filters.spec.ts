/**
 * Filters, against the deterministic fixture (60 nodes: 44 python / 16 typescript, 10
 * orphans, 25 edges with weights 1-6 and exactly one edge at weight 6). Every expected
 * number below is derived directly from `e2e/fixtures/graph.tiny.json` (see
 * `tmp/gen-graph.mjs`-shaped counts recorded in that file's `totals`), not guessed.
 */
import { expect, test } from "@playwright/test";
import { canvasAlphaSum, loadFixtureGraph, routeFixtureGraph, setRangeValue, waitForCanvasSettled } from "./helpers";

test.beforeEach(async ({ page }) => {
  await routeFixtureGraph(page, loadFixtureGraph());
  await page.goto("/");
  await expect(page.getByTestId("header")).toBeVisible();
  await expect(page.getByTestId("shown")).toContainText("showing 60 of 60");
});

test("search narrows the shown/total count", async ({ page }) => {
  await page.getByTestId("search").fill("targetfn");
  await expect(page.getByTestId("shown")).toContainText("showing 1 of 1");

  await page.getByTestId("search").fill("");
  await expect(page.getByTestId("shown")).toContainText("showing 60 of 60");
});

test("the node cap reduces the shown count", async ({ page }) => {
  // Capping switches the note to a "definitions are hidden" warning rather than
  // "showing X of Y" (see App.tsx's `capped` branch).
  await setRangeValue(page.getByTestId("limit"), 50);
  await expect(page.getByTestId("shown")).toContainText("10 of 60");
  await expect(page.getByTestId("shown")).toContainText("hidden by the 50-node cap");
});

test("a language checkbox filters nodes by language", async ({ page }) => {
  const controls = page.getByTestId("controls");
  await controls.getByRole("checkbox", { name: "typescript" }).uncheck();
  // 44 python-only nodes remain of the fixture's 60.
  await expect(page.getByTestId("shown")).toContainText("showing 44 of 44");
});

test("hide orphans removes leverage-0 nodes", async ({ page }) => {
  const controls = page.getByTestId("controls");
  await controls.getByRole("checkbox", { name: "hide orphans" }).check();
  // 10 of the fixture's 60 nodes are orphans (leverage 0).
  await expect(page.getByTestId("shown")).toContainText("showing 50 of 50");
});

test("min edge weight reduces rendered edges", async ({ page }) => {
  // Grid layout positions nodes purely by insertion order, independent of edges, so any
  // pixel change here can only come from edges appearing/disappearing.
  await page.getByTestId("layout").selectOption("grid");
  const canvas = page.getByTestId("graph-canvas");
  await waitForCanvasSettled(canvas);
  const before = await canvasAlphaSum(canvas);

  // Only one of the fixture's 25 edges has sites >= 6; the other 24 should disappear.
  await setRangeValue(page.getByTestId("min-weight"), 6);
  await waitForCanvasSettled(canvas);
  const after = await canvasAlphaSum(canvas);

  expect(after, "raising the min edge weight to its max should leave less drawn (edge) ink").toBeLessThan(before);
});
