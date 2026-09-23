/**
 * `ColumnHead`: the one sortable head both session tables share. Mounted inside a real
 * `.xh-table` head cell, because every rule that styles it (`.sort-ico` opacity, the sorted wash)
 * is scoped to `.xh-table thead th`, and a bare button would test a component no page renders.
 */
import { expect, test } from "@playwright/experimental-ct-react";
import { ColumnHead } from "../src/components/ColumnHead";

const MUTED = { light: "rgb(91, 96, 112)", dark: "rgb(154, 160, 176)" };

interface HeadProps {
  name?: string;
  label?: string;
  title?: string;
  active?: boolean;
  ascending?: boolean;
  aria?: "ascending" | "descending" | "none";
  onSort?: () => void;
}

/** The head as a table renders it: one `th` in one `thead` of an `.xh-table`. */
const head = ({
  name = "estimated_cost_usd",
  label = "cost",
  title = "this plugin's estimate",
  active = false,
  ascending = true,
  aria = "none",
  onSort = () => {},
}: HeadProps) => (
  <table className="xh-table">
    <thead>
      <tr>
        <th aria-sort={aria}>
          <ColumnHead defId="def-cost" name={name} label={label} title={title} active={active} ascending={ascending} onSort={onSort} />
        </th>
      </tr>
    </thead>
  </table>
);

test.describe("ColumnHead", () => {
  test("prints the short label inside a real button", async ({ mount, page }) => {
    await mount(head({}));
    const button = page.locator("button");
    await expect(button).toBeVisible();
    await expect(button).toHaveText("cost");
    await expect(button).toHaveAttribute("type", "button");
  });

  test("an abbreviated head answers to its label and its canonical field name (WCAG 2.5.3)", async ({ mount, page }) => {
    await mount(head({}));
    await expect(page.locator("button")).toHaveAttribute("aria-label", "cost — estimated_cost_usd");
    await expect(page.getByRole("button", { name: "cost — estimated_cost_usd" })).toBeVisible();
  });

  test("a head whose label is its name carries no redundant aria-label", async ({ mount, page }) => {
    await mount(head({ name: "turns", label: "turns", title: "model API calls" }));
    const button = page.locator("button");
    await expect(button).not.toHaveAttribute("aria-label", /.*/);
    await expect(page.getByRole("button", { name: "turns", exact: true })).toBeVisible();
  });

  test("the definition reaches a screen reader through aria-describedby on a visually-hidden span", async ({ mount, page }) => {
    await mount(head({}));
    const button = page.locator("button");
    await expect(button).toHaveAttribute("aria-describedby", "def-cost");
    await expect(button).toHaveAccessibleDescription("estimated_cost_usd — this plugin's estimate");
    const def = page.locator("#def-cost");
    await expect(def).toHaveClass(/sr-only/);
    await expect(def).toHaveText("estimated_cost_usd — this plugin's estimate");
    const box = await def.evaluate((el) => {
      const s = getComputedStyle(el);
      return { position: s.position, width: el.getBoundingClientRect().width, clip: s.clipPath };
    });
    expect(box.position).toBe("absolute");
    expect(box.width).toBeLessThanOrEqual(1);
    expect(box.clip).toContain("inset(50%)");
  });

  test("the definition costs no tab stop: one Tab lands on the button and the next leaves it", async ({ mount, page }) => {
    await mount(
      <div>
        {head({})}
        <button type="button" id="after">
          after
        </button>
      </div>,
    );
    await page.keyboard.press("Tab");
    await expect(page.getByRole("button", { name: "cost — estimated_cost_usd" })).toBeFocused();
    await page.keyboard.press("Tab");
    await expect(page.locator("#after")).toBeFocused();
  });

  test("the arrow points up when ascending and down when descending", async ({ mount, page }) => {
    const c = await mount(head({ ascending: true }));
    await expect(page.locator("svg.sort-ico")).toHaveClass(/lucide-arrow-up/);
    await c.update(head({ ascending: false }));
    await expect(page.locator("svg.sort-ico")).toHaveClass(/lucide-arrow-down/);
  });

  test("the arrow is decorative: aria-hidden and outside the accessible name", async ({ mount, page }) => {
    await mount(head({}));
    await expect(page.locator("svg.sort-ico")).toHaveAttribute("aria-hidden", "true");
    await expect(page.locator("button")).toHaveAccessibleName("cost — estimated_cost_usd");
  });

  test("an inactive arrow is in the DOM at zero opacity, unmarked", async ({ mount, page }) => {
    await mount(head({}));
    const arrow = page.locator("svg.sort-ico");
    await expect(arrow).toHaveCount(1);
    await expect(arrow).not.toHaveAttribute("data-active", /.*/);
    await expect(arrow).toHaveCSS("opacity", "0");
  });

  test("an active arrow is marked, fully opaque and in the accent ink", async ({ mount, page }) => {
    await mount(head({ active: true, aria: "ascending" }));
    const arrow = page.locator("svg.sort-ico");
    await expect(arrow).toHaveAttribute("data-active", "true");
    await expect(arrow).toHaveCSS("opacity", "1");
    await expect(arrow).toHaveCSS("color", "rgb(79, 70, 229)");
  });

  test("hovering an inactive head half-reveals the arrow a click promises", async ({ mount, page }) => {
    await mount(head({}));
    await page.locator("button").hover();
    await expect(page.locator("svg.sort-ico")).toHaveCSS("opacity", "0.45");
  });

  test("keyboard focus reveals the arrow and draws an inboard focus ring", async ({ mount, page }) => {
    await mount(head({}));
    await page.keyboard.press("Tab");
    const button = page.locator("button");
    await expect(button).toBeFocused();
    await expect(page.locator("svg.sort-ico")).toHaveCSS("opacity", "0.45");
    await expect(button).toHaveCSS("outline-style", "solid");
    await expect(button).toHaveCSS("outline-offset", "-2px");
  });

  test("activating does not change the head's width: the arrow was always there", async ({ mount, page }) => {
    const c = await mount(head({}));
    const before = await page.locator("button").evaluate((el) => el.getBoundingClientRect().width);
    await c.update(head({ active: true, aria: "ascending" }));
    await expect(page.locator("svg.sort-ico")).toHaveAttribute("data-active", "true");
    const after = await page.locator("button").evaluate((el) => el.getBoundingClientRect().width);
    expect(after).toBe(before);
  });

  test("a click calls onSort once", async ({ mount, page }) => {
    let calls = 0;
    await mount(head({ onSort: () => (calls += 1) }));
    await page.locator("button").click();
    await expect.poll(() => calls).toBe(1);
  });

  for (const key of ["Enter", "Space"]) {
    test(`${key} on the focused head calls onSort`, async ({ mount, page }) => {
      let calls = 0;
      await mount(head({ onSort: () => (calls += 1) }));
      await page.keyboard.press("Tab");
      await page.keyboard.press(key);
      await expect.poll(() => calls).toBe(1);
    });
  }

  test("hovering opens a tooltip naming the field in mono, then its definition", async ({ mount, page }) => {
    await mount(<div style={{ paddingTop: 80 }}>{head({})}</div>);
    const tip = page.locator("span.mono", { hasText: "estimated_cost_usd" });
    await expect(tip).toHaveCount(0);
    await page.locator("button").hover();
    await expect(tip).toBeVisible();
    await expect(tip.locator("..")).toContainText("estimated_cost_usd — this plugin's estimate");
  });

  test("the head recedes in muted ink until it is the sorted one", async ({ mount, page }) => {
    const c = await mount(head({}));
    await expect(page.locator("th")).toHaveCSS("color", MUTED.light);
    await c.update(head({ active: true, aria: "descending" }));
    // The sorted head's button is at full ink with an accent wash behind it.
    await expect(page.locator("button")).toHaveCSS("color", "rgb(27, 29, 35)");
    await expect(page.locator("button")).not.toHaveCSS("background-color", "rgba(0, 0, 0, 0)");
  });

  test("renders in dark mode with the dark tokens", async ({ mount, page }) => {
    await mount(head({ active: true, aria: "ascending" }), { hooksConfig: { mode: "dark" } });
    await expect(page.locator("button")).toBeVisible();
    await expect(page.locator("th")).toHaveCSS("color", MUTED.dark);
    await expect(page.locator("svg.sort-ico")).toHaveCSS("color", "rgb(165, 180, 252)");
    await expect(page.locator("button")).toHaveCSS("color", "rgb(230, 232, 239)");
  });
});
