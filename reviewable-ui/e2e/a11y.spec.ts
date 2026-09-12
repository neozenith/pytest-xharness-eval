/**
 * Accessibility. The project targets WCAG AAA (see docs/plans/maintainability), so this
 * asserts zero violations across wcag2a, wcag2aa AND wcag2aaa. If axe finds a real
 * violation, this test is left failing on purpose (see the final report) rather than
 * narrowing the tag list to make it pass.
 */
import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import { loadFixtureGraph, routeFixtureGraph } from "./helpers";

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
