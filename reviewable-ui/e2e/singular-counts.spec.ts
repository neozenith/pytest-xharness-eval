/**
 * `GraphCanvas`'s "N definitions drawn" status note and its table's "Skip past the
 * graph table (N rows)" link both printed the bare plural noun regardless of N --
 * unlike every other counted noun in this file's own vocabulary ("caller(s)",
 * "site(s)" in Panels.tsx, "cluster(s)" in the Lede/ClusterTable fixes), these two
 * had no singular/plural ternary at all. Searching for "targetfn" is the fixture's
 * own established way to narrow the view to exactly one definition (see
 * filters.spec.ts's "showing 1 of 1"), which is the only way to reach N=1 here --
 * nothing in Storybook exercises `GraphCanvas` directly (cytoscape needs a real
 * canvas, so this is real-browser-only coverage; see the review's tier notes).
 */
import { expect, test } from "@playwright/test";
import { loadFixtureGraph, routeFixtureGraph } from "./helpers";

test("the graph-note and skip-link singularise when exactly one definition is drawn", async ({ page }) => {
  await routeFixtureGraph(page, loadFixtureGraph());
  await page.goto("/");
  await expect(page.getByTestId("header")).toBeVisible();

  await page.getByTestId("search").fill("targetfn");
  await expect(page.getByTestId("shown")).toContainText("showing 1 of 1");

  await expect(page.getByTestId("graph-note")).toHaveText(/^1 definition drawn/);
  await expect(page.getByTestId("graph-note")).not.toHaveText(/1 definitions/);

  await page.getByRole("button", { name: "View graph as table" }).click();
  const skipLink = page.locator(".skip-link");
  await expect(skipLink).toHaveText("Skip past the graph table (1 row)");
});
