/**
 * `ToggleGroup` / `ToggleGroupItem` (src/components/ui/toggle-group.tsx): Tamagui's single-choice
 * segmented control behind the radix-style `type`/`value`/`onValueChange` surface. The selected
 * segment is painted by `.XhToggleGroup [data-state="on"]` in index.css: a raised thumb in ink,
 * the others muted.
 */
import { expect, test } from "@playwright/experimental-ct-react";
import type { Locator } from "@playwright/test";
import { ToggleGroup, ToggleGroupItem } from "../src/components/ui/toggle-group";
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

/** WCAG contrast of the element's text over every ancestor background, composited on a canvas. */
const contrast = (el: Locator) =>
  el.evaluate((node) => {
    const canvas = document.createElement("canvas");
    canvas.width = canvas.height = 1;
    const ctx = canvas.getContext("2d", { willReadFrequently: true })!;
    const paint = (colour: string) => {
      ctx.fillStyle = colour;
      ctx.fillRect(0, 0, 1, 1);
    };
    const chain: string[] = [];
    for (let n: Element | null = node; n; n = n.parentElement) chain.push(getComputedStyle(n).backgroundColor);
    paint("#ffffff");
    for (const bg of chain.reverse()) paint(bg);
    const [br, bgc, bb] = ctx.getImageData(0, 0, 1, 1).data;
    paint(getComputedStyle(node).color);
    const [fr, fg, fb] = ctx.getImageData(0, 0, 1, 1).data;
    const lum = (r = 0, g = 0, b = 0) =>
      [r, g, b]
        .map((v) => v / 255)
        .map((c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4))
        .reduce((acc, c, i) => acc + c * [0.2126, 0.7152, 0.0722][i]!, 0);
    const [a, b] = [lum(fr, fg, fb), lum(br, bgc, bb)].sort((x, y) => y - x);
    return (a! + 0.05) / (b! + 0.05);
  });

type Pick = (v: string) => void;

const group = (value: string, onValueChange?: Pick, extra: { disabledB?: boolean } = {}) => (
  <ToggleGroup id="ViewToggle" type="single" variant="outline" size="sm" value={value} onValueChange={onValueChange} aria-label="turn table view">
    <ToggleGroupItem value="summary" data-view="summary">
      Summary view
    </ToggleGroupItem>
    <ToggleGroupItem value="detailed" data-view="detailed" disabled={extra.disabledB}>
      Detailed view
    </ToggleGroupItem>
  </ToggleGroup>
);

test("ToggleGroup is a labelled group of buttons carrying XhToggleGroup", async ({ page, mount }) => {
  await mount(group("summary"));
  const g = page.getByRole("group", { name: "turn table view" });
  await expect(g).toBeVisible();
  await expect(g).toHaveClass(/\bXhToggleGroup\b/);
  await expect(g).toHaveAttribute("id", "ViewToggle");
  await expect(g).toHaveAttribute("data-orientation", "horizontal");
  await expect(g.getByRole("button")).toHaveCount(2);
  // The call-site-only props are swallowed, never leaked onto the DOM.
  await expect(g).not.toHaveAttribute("variant");
  await expect(g).not.toHaveAttribute("size");
});

test("ToggleGroup keeps a caller's className beside XhToggleGroup", async ({ page, mount }) => {
  await mount(
    <ToggleGroup className="mine" value="a" aria-label="g">
      <ToggleGroupItem value="a">A</ToggleGroupItem>
    </ToggleGroup>,
  );
  await expect(page.getByRole("group")).toHaveClass(/XhToggleGroup mine/);
});

test("ToggleGroupItem marks the selected segment data-state=on and forwards data-* props", async ({ page, mount }) => {
  await mount(group("summary"));
  const on = page.getByRole("button", { name: "Summary view" });
  const off = page.getByRole("button", { name: "Detailed view" });
  await expect(on).toHaveAttribute("data-state", "on");
  await expect(off).toHaveAttribute("data-state", "off");
  await expect(on).toHaveAttribute("data-view", "summary");
});

test("ToggleGroup exposes the selected segment to assistive tech", async ({ page, mount }) => {
  // BUG (toggle-group.tsx:17,24): the items are plain <button>s whose selection lives only in
  // `data-state` — no aria-pressed, and no role=radio/aria-checked — so a screen reader cannot
  // tell which view is chosen (WCAG 4.1.2). Expected aria-pressed=true (or aria-checked) on the
  // selected segment.
  test.fail(true, "selected ToggleGroupItem has no aria-pressed/aria-checked");
  await mount(group("summary"));
  const on = page.getByRole("button", { name: "Summary view" });
  await expect(on).toHaveAttribute("aria-pressed", "true", { timeout: 1_000 });
});

test("ToggleGroup click reports the chosen value; the value prop moves the selection", async ({ page, mount }) => {
  const seen: string[] = [];
  const c = await mount(group("summary", (v) => seen.push(v)));
  await page.getByRole("button", { name: "Detailed view" }).click();
  await expect.poll(() => seen).toEqual(["detailed"]);
  await c.update(group("detailed", (v) => seen.push(v)));
  await expect(page.getByRole("button", { name: "Detailed view" })).toHaveAttribute("data-state", "on");
  await expect(page.getByRole("button", { name: "Summary view" })).toHaveAttribute("data-state", "off");
});

test("ToggleGroup clicking the selected segment reports an empty value (single mode deselect)", async ({ page, mount }) => {
  // Call sites guard with `v && onChange(v)`; this pins the value they are guarding against.
  const seen: string[] = [];
  await mount(group("summary", (v) => seen.push(v)));
  await page.getByRole("button", { name: "Summary view" }).click();
  await expect.poll(() => seen).toEqual([""]);
});

for (const key of ["Enter", "Space"] as const) {
  test(`ToggleGroup selects the focused segment with ${key}`, async ({ page, mount }) => {
    const seen: string[] = [];
    await mount(group("summary", (v) => seen.push(v)));
    await page.getByRole("button", { name: "Detailed view" }).focus();
    await page.keyboard.press(key);
    await expect.poll(() => seen).toEqual(["detailed"]);
  });
}

test("ToggleGroup arrow keys move focus between segments", async ({ page, mount }) => {
  await mount(group("summary"));
  const a = page.getByRole("button", { name: "Summary view" });
  const b = page.getByRole("button", { name: "Detailed view" });
  await a.focus();
  await page.keyboard.press("ArrowRight");
  await expect(b).toBeFocused();
  await page.keyboard.press("ArrowLeft");
  await expect(a).toBeFocused();
});

test("ToggleGroup disabled item: not operable", async ({ page, mount }) => {
  const seen: string[] = [];
  await mount(group("summary", (v) => seen.push(v), { disabledB: true }));
  const b = page.getByRole("button", { name: "Detailed view" });
  await expect(b).toBeDisabled();
  await b.click({ force: true });
  expect(seen).toEqual([]);
  await expect(b).toHaveAttribute("data-state", "off");
});

test("ToggleGroupItem geometry: 28px tall, 11px inline padding, 7px radius", async ({ page, mount }) => {
  await mount(group("summary"));
  const b = page.getByRole("button", { name: "Summary view" });
  await expect(b).toHaveCSS("height", "28px");
  await expect(b).toHaveCSS("padding-left", "11px");
  await expect(b).toHaveCSS("border-top-left-radius", "7px");
  await expect(b).toHaveCSS("border-top-width", "0px");
});

test("ToggleGroupItem wraps its label in an inheriting Text node", async ({ page, mount }) => {
  await mount(group("summary"));
  const label = page.getByRole("button", { name: "Summary view" }).getByText("Summary view", { exact: true });
  expect(await label.evaluate((n) => n.tagName)).toBe("SPAN");
});

test("ToggleGroup selection keeps segment widths stable (no weight change)", async ({ page, mount }) => {
  const c = await mount(group("summary"));
  const b = page.getByRole("button", { name: "Detailed view" });
  const before = (await b.boundingBox())!.width;
  const weightOff = await b.evaluate((n) => getComputedStyle(n).fontWeight);
  await c.update(group("detailed"));
  await expect(b).toHaveAttribute("data-state", "on");
  expect((await b.boundingBox())!.width).toBeCloseTo(before, 1);
  expect(await b.evaluate((n) => getComputedStyle(n).fontWeight)).toBe(weightOff);
});

for (const mode of ["light", "dark"] as const) {
  test(`ToggleGroup selected segment is inked, others muted (${mode})`, async ({ page, mount }) => {
    await mount(group("summary"), { hooksConfig: { mode } satisfies HooksConfig });
    const on = page.getByRole("button", { name: "Summary view" });
    const off = page.getByRole("button", { name: "Detailed view" });
    await expect(on).toHaveCSS("color", await resolved(on, "ink"));
    await expect(off).toHaveCSS("color", await resolved(off, "muted"));
    expect(await on.evaluate((n) => getComputedStyle(n).boxShadow)).not.toBe("none");
    expect(await on.evaluate((n) => getComputedStyle(n).backgroundColor)).not.toBe("rgba(0, 0, 0, 0)");
    if (mode === "light") await expect(on).toHaveCSS("background-color", await resolved(on, "panel"));
  });

  test(`ToggleGroup selected segment keeps its thumb under the pointer (${mode})`, async ({ page, mount }) => {
    await mount(group("summary"), { hooksConfig: { mode } satisfies HooksConfig });
    const on = page.getByRole("button", { name: "Summary view" });
    const rest = await on.evaluate((n) => getComputedStyle(n).backgroundColor);
    await on.hover();
    await expect(on).toHaveCSS("background-color", rest);
    await expect(on).toHaveCSS("color", await resolved(on, "ink"));
  });

  test(`ToggleGroup unselected hover takes a wash (${mode})`, async ({ page, mount }) => {
    await mount(group("summary"), { hooksConfig: { mode } satisfies HooksConfig });
    const off = page.getByRole("button", { name: "Detailed view" });
    const rest = await off.evaluate((n) => getComputedStyle(n).color);
    await off.hover();
    await expect(off).not.toHaveCSS("color", rest);
  });

  test(`ToggleGroup segment labels clear AA in both states (${mode})`, async ({ page, mount }) => {
    await mount(<div style={{ background: "var(--xh-panel)", padding: 8 }}>{group("summary")}</div>, { hooksConfig: { mode } satisfies HooksConfig });
    expect(await contrast(page.getByRole("button", { name: "Summary view" }))).toBeGreaterThanOrEqual(4.5);
    expect(await contrast(page.getByRole("button", { name: "Detailed view" }))).toBeGreaterThanOrEqual(4.5);
  });

  test(`ToggleGroupItem focus-visible ring is 2px solid --xh-accent, inset 1px (${mode})`, async ({ page, mount }) => {
    await mount(group("summary"), { hooksConfig: { mode } satisfies HooksConfig });
    const on = page.getByRole("button", { name: "Summary view" });
    await page.keyboard.press("Tab");
    await expect(on).toBeFocused();
    await expect(on).toHaveCSS("outline-style", "solid");
    await expect(on).toHaveCSS("outline-width", "2px");
    await expect(on).toHaveCSS("outline-offset", "-1px");
    await expect(on).toHaveCSS("outline-color", await resolved(on, "accent"));
  });
}

test("ToggleGroup costs one Tab stop: Tab from the group's segment leaves the control", async ({ page, mount }) => {
  // BUG (toggle-group.tsx:17,24): every segment renders tabindex=0, so Tab walks Summary, then
  // Detailed, then leaves: one stop per segment rather than the single roving stop of the
  // toolbar/radio-group pattern the arrow keys already implement. Expected: the next Tab leaves.
  test.fail(true, "ToggleGroup is one Tab stop per segment, not one roving stop");
  await mount(
    <div>
      {group("summary")}
      <button type="button">after</button>
    </div>,
  );
  await page.keyboard.press("Tab");
  await expect(page.getByRole("button", { name: "Summary view" })).toBeFocused({ timeout: 1_000 });
  await page.keyboard.press("Tab");
  await expect(page.getByRole("button", { name: "after" })).toBeFocused({ timeout: 1_000 });
});
