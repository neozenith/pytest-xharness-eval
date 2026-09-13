/**
 * Keyboard operability of the control panel: every field must be reachable by Tab
 * alone, and at least one of each control shape (select, text input, range, checkbox)
 * must be operable without a mouse.
 */
import { expect, test } from "@playwright/test";
import { loadFixtureGraph, routeFixtureGraph } from "./helpers";

test.beforeEach(async ({ page }) => {
  await routeFixtureGraph(page, loadFixtureGraph());
  await page.goto("/");
  await expect(page.getByTestId("header")).toBeVisible();
});

test("every control panel field is reachable by Tab", async ({ page }) => {
  const expectedTestIds = ["level", "metric", "layout", "search", "min-weight", "limit"];

  // Start Tab traversal from a known point: the top of the document.
  await page.locator("body").click({ position: { x: 2, y: 2 } });

  const seenTestIds = new Set<string>();
  let sawCheckbox = false;
  for (let i = 0; i < 40; i++) {
    await page.keyboard.press("Tab");
    const active = await page.evaluate(() => {
      const el = document.activeElement;
      return el instanceof HTMLElement
        ? { testId: el.getAttribute("data-testid"), type: el.getAttribute("type") }
        : null;
    });
    if (active?.testId) seenTestIds.add(active.testId);
    if (active?.type === "checkbox") sawCheckbox = true;
    if (seenTestIds.size >= expectedTestIds.length && sawCheckbox) break;
  }

  for (const id of expectedTestIds) {
    expect([...seenTestIds], `data-testid=${id} should be Tab-reachable`).toContain(id);
  }
  expect(sawCheckbox, "at least one language/orphan checkbox should be Tab-reachable").toBe(true);
});

test("the search field is operable via keyboard alone", async ({ page }) => {
  await page.getByTestId("search").focus();
  await page.keyboard.type("targetfn");
  await expect(page.getByTestId("shown")).toContainText("showing 1 of 1");
});

test("a checkbox is operable via keyboard alone (Space toggles it)", async ({ page }) => {
  const orphansCheckbox = page.getByTestId("controls").getByRole("checkbox", { name: "hide orphans" });
  await orphansCheckbox.focus();
  await expect(orphansCheckbox).not.toBeChecked();

  await page.keyboard.press("Space");
  await expect(orphansCheckbox).toBeChecked();
  await expect(page.getByTestId("shown")).toContainText("showing 50 of 50");

  await page.keyboard.press("Space");
  await expect(orphansCheckbox).not.toBeChecked();
  await expect(page.getByTestId("shown")).toContainText("showing 60 of 60");
});

test("a range slider is operable via keyboard alone (Home jumps to its minimum)", async ({ page }) => {
  await page.getByTestId("limit").focus();
  await page.keyboard.press("Home");
  // 60 fixture nodes capped to the slider's minimum (50) hides exactly 10.
  await expect(page.getByTestId("shown")).toContainText("10 of 60");
  await expect(page.getByTestId("shown")).toContainText("hidden by the 50-node cap");
});

test("a select is operable via keyboard alone (type-ahead jumps to an option)", async ({ page }) => {
  // Native <select> elements support type-ahead (press a letter to jump to the next
  // option starting with it) without ever opening the popup -- unlike ArrowUp/Down,
  // which move the OS-native popup and are not exercisable through synthetic key
  // events in headless Chromium (verified against a bare <select> on a blank page).
  const level = page.getByTestId("level");
  await expect(level).toHaveValue("folder");
  await level.focus();
  await page.keyboard.press("f");
  await expect(level).toHaveValue("file");
});

test("the accessible graph table is fully reachable and operable by keyboard", async ({ page }) => {
  // A class selector, not a role+name one: the button's accessible name flips between
  // "View graph as table" and "Hide graph as table" on click, and a name-filtered
  // locator stops matching once the name it was built with is no longer current.
  const toggle = page.locator("button.table-toggle");
  await toggle.focus();
  await expect(toggle).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(toggle).toHaveText("Hide graph as table");

  const targetRow = page.locator("[data-testid=graph-table] tbody tr", { hasText: "TargetFn" });
  const selectButton = targetRow.getByRole("button", { name: "Select" });
  await selectButton.focus();
  await page.keyboard.press("Enter");
  await expect(page.getByTestId("detail")).toContainText("TargetFn");
  await expect(targetRow.getByRole("button", { name: "Selected" })).toBeFocused();
});
