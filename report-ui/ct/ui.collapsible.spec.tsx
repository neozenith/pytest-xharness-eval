/**
 * `Collapsible` / `CollapsibleTrigger` / `CollapsibleContent` (src/components/ui/collapsible.tsx):
 * Tamagui's disclosure behind the radix-style surface, with the trigger's bare text wrapped in
 * an inheriting Text node (the same `wrapTextChildren` Button uses).
 */
import { expect, test } from "./test";
import type { Locator } from "@playwright/test";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "../src/components/ui/collapsible";
import type { HooksConfig } from "../playwright/index";

const resolved = (el: Locator, token: string) =>
  el.evaluate((_, t) => {
    const probe = document.createElement("span");
    probe.style.color = `var(--xh-${t})`;
    document.body.append(probe);
    const out = getComputedStyle(probe).color;
    probe.remove();
    return out;
  }, token);

const disclosure = (props: { open?: boolean; defaultOpen?: boolean; onOpenChange?: (open: boolean) => void } = {}) => (
  <Collapsible {...props}>
    <CollapsibleTrigger className="env-trigger">
      <i aria-hidden>{">"}</i>
      environment
    </CollapsibleTrigger>
    <CollapsibleContent>
      <p>PATH=/usr/bin</p>
    </CollapsibleContent>
  </Collapsible>
);

test("Collapsible starts closed: trigger is a collapsed button and the content is absent", async ({ page, mount }) => {
  await mount(disclosure());
  const t = page.getByRole("button", { name: "environment" });
  await expect(t).toBeVisible();
  await expect(t).toHaveAttribute("aria-expanded", "false");
  await expect(t).toHaveAttribute("data-state", "closed");
  await expect(t).toHaveClass(/\benv-trigger\b/);
  await expect(page.getByText("PATH=/usr/bin")).toBeHidden();
});

test("CollapsibleTrigger wraps its bare text in a Text node and leaves elements alone", async ({ page, mount }) => {
  await mount(disclosure());
  const t = page.getByRole("button", { name: "environment" });
  expect(await t.evaluate((n) => [...n.children].map((c) => c.tagName))).toEqual(["I", "SPAN"]);
  const label = t.getByText("environment", { exact: true });
  await expect(label).toHaveCSS("color", await t.evaluate((n) => getComputedStyle(n).color));
});

test("Collapsible opens and closes on click", async ({ page, mount }) => {
  await mount(disclosure());
  const t = page.getByRole("button", { name: "environment" });
  await t.click();
  await expect(t).toHaveAttribute("aria-expanded", "true");
  await expect(t).toHaveAttribute("data-state", "open");
  const body = page.getByText("PATH=/usr/bin");
  await expect(body).toBeVisible();
  await t.click();
  await expect(t).toHaveAttribute("aria-expanded", "false");
  await expect(body).toBeHidden();
});

for (const key of ["Enter", "Space"] as const) {
  test(`Collapsible toggles from the keyboard with ${key}`, async ({ page, mount }) => {
    await mount(disclosure());
    const t = page.getByRole("button", { name: "environment" });
    await page.keyboard.press("Tab");
    await expect(t).toBeFocused();
    await page.keyboard.press(key);
    await expect(t).toHaveAttribute("aria-expanded", "true");
    await expect(page.getByText("PATH=/usr/bin")).toBeVisible();
    await page.keyboard.press(key);
    await expect(t).toHaveAttribute("aria-expanded", "false");
  });
}

test("Collapsible defaultOpen renders the content from the first paint", async ({ page, mount }) => {
  await mount(disclosure({ defaultOpen: true }));
  await expect(page.getByRole("button", { name: "environment" })).toHaveAttribute("aria-expanded", "true");
  await expect(page.getByText("PATH=/usr/bin")).toBeVisible();
});

test("Collapsible controlled: the trigger reports, the open prop decides", async ({ page, mount }) => {
  const seen: boolean[] = [];
  const c = await mount(disclosure({ open: false, onOpenChange: (o) => seen.push(o) }));
  const t = page.getByRole("button", { name: "environment" });
  await t.click();
  await expect.poll(() => seen).toEqual([true]);
  await expect(t).toHaveAttribute("aria-expanded", "false");
  await c.update(disclosure({ open: true, onOpenChange: (o) => seen.push(o) }));
  await expect(t).toHaveAttribute("aria-expanded", "true");
  await expect(page.getByText("PATH=/usr/bin")).toBeVisible();
});

for (const mode of ["light", "dark"] as const) {
  test(`CollapsibleTrigger shows the focus-visible ring in --xh-accent (${mode})`, async ({ page, mount }) => {
    await mount(disclosure(), { hooksConfig: { mode } satisfies HooksConfig });
    const t = page.getByRole("button", { name: "environment" });
    await page.keyboard.press("Tab");
    await expect(t).toBeFocused();
    await expect(t).toHaveCSS("outline-style", "solid");
    await expect(t).toHaveCSS("outline-width", "2px");
    await expect(t).toHaveCSS("outline-color", await resolved(t, "accent"));
  });
}

test("CollapsibleTrigger aria-controls points at the open content", async ({ page, mount }) => {
  // Regression: the trigger named an id (`_r_N_`) that CollapsibleContent never rendered.
  await mount(disclosure({ defaultOpen: true }));
  const controls = await page.getByRole("button", { name: "environment" }).getAttribute("aria-controls");
  expect(controls).toBeTruthy();
  await expect(page.locator(`[id="${controls}"]`)).toHaveCount(1);
  await expect(page.locator(`[id="${controls}"]`)).toContainText("PATH=/usr/bin");
});

test("CollapsibleTrigger never references an absent node: no aria-controls while closed", async ({ page, mount }) => {
  await mount(disclosure());
  const t = page.getByRole("button", { name: "environment" });
  await expect(t).not.toHaveAttribute("aria-controls", /.*/);
  await t.click();
  const controls = await t.getAttribute("aria-controls");
  await expect(page.locator(`[id="${controls}"]`)).toContainText("PATH=/usr/bin");
  await t.click();
  await expect(t).not.toHaveAttribute("aria-controls", /.*/);
});

test("Two Collapsibles on one page control their own content", async ({ page, mount }) => {
  await mount(
    <div>
      {disclosure({ defaultOpen: true })}
      <Collapsible defaultOpen>
        <CollapsibleTrigger>second</CollapsibleTrigger>
        <CollapsibleContent>
          <p>HOME=/root</p>
        </CollapsibleContent>
      </Collapsible>
    </div>,
  );
  const first = await page.getByRole("button", { name: "environment" }).getAttribute("aria-controls");
  const second = await page.getByRole("button", { name: "second" }).getAttribute("aria-controls");
  expect(first).not.toBe(second);
  await expect(page.locator(`[id="${second}"]`)).toHaveText("HOME=/root");
});
