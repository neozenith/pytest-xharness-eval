/**
 * `Switch` (src/components/ui/switch.tsx): Tamagui's switch with the radix-style
 * `checked`/`onCheckedChange` surface, a 34x20 track (hit area pushed to 28px tall by
 * `.XhSwitch::after`), an accent track when on, and the report's focus ring.
 */
import { expect, test } from "@playwright/experimental-ct-react";
import type { Locator } from "@playwright/test";
import { Switch } from "../src/components/ui/switch";
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

/** WCAG contrast between two painted colours, resolved through a canvas. */
const ratio = (el: Locator, fg: string, bg: string) =>
  el.evaluate(
    (_, [f, b]) => {
      const canvas = document.createElement("canvas");
      canvas.width = canvas.height = 1;
      const ctx = canvas.getContext("2d", { willReadFrequently: true })!;
      const px = (c: string) => {
        ctx.fillStyle = "#fff";
        ctx.fillRect(0, 0, 1, 1);
        ctx.fillStyle = c;
        ctx.fillRect(0, 0, 1, 1);
        return ctx.getImageData(0, 0, 1, 1).data;
      };
      const lum = (d: Uint8ClampedArray) =>
        [d[0]!, d[1]!, d[2]!]
          .map((v) => v / 255)
          .map((c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4))
          .reduce((acc, c, i) => acc + c * [0.2126, 0.7152, 0.0722][i]!, 0);
      const [x, y] = [lum(px(f)), lum(px(b))].sort((p, q) => q - p);
      return (x! + 0.05) / (y! + 0.05);
    },
    [fg, bg] as const,
  );

test("Switch is a role=switch with aria-checked, named by aria-label", async ({ page, mount }) => {
  await mount(<Switch checked={false} aria-label="show ignored files" />);
  const s = page.getByRole("switch", { name: "show ignored files" });
  await expect(s).toBeVisible();
  await expect(s).toHaveAttribute("aria-checked", "false");
  await expect(s).not.toBeChecked();
  await expect(s).toHaveClass(/\bXhSwitch\b/);
});

test("Switch keeps a caller's className beside XhSwitch", async ({ page, mount }) => {
  await mount(<Switch checked={false} className="mine" aria-label="x" />);
  await expect(page.getByRole("switch")).toHaveClass(/\bXhSwitch\b.*\bmine\b|\bmine\b.*\bXhSwitch\b/);
});

test("Switch controlled: click reports the next state; the prop, not the click, flips aria-checked", async ({ page, mount }) => {
  const seen: boolean[] = [];
  const c = await mount(<Switch checked={false} onCheckedChange={(v) => seen.push(v)} aria-label="x" />);
  const s = page.getByRole("switch");
  await s.click();
  await expect.poll(() => seen).toEqual([true]);
  await expect(s).toHaveAttribute("aria-checked", "false");
  await c.update(<Switch checked onCheckedChange={(v) => seen.push(v)} aria-label="x" />);
  await expect(s).toHaveAttribute("aria-checked", "true");
  await expect(s).toBeChecked();
  await s.click();
  await expect.poll(() => seen).toEqual([true, false]);
});

for (const key of ["Space", "Enter"] as const) {
  test(`Switch toggles from the keyboard with ${key}`, async ({ page, mount }) => {
    const seen: boolean[] = [];
    await mount(<Switch checked={false} onCheckedChange={(v) => seen.push(v)} aria-label="x" />);
    await page.keyboard.press("Tab");
    await expect(page.getByRole("switch")).toBeFocused();
    await page.keyboard.press(key);
    await expect.poll(() => seen).toEqual([true]);
  });
}

test("Switch uncontrolled (defaultChecked) toggles its own aria-checked", async ({ page, mount }) => {
  await mount(<Switch defaultChecked={false} aria-label="x" />);
  const s = page.getByRole("switch");
  await s.click();
  await expect(s).toHaveAttribute("aria-checked", "true");
  await page.keyboard.press("Space");
  await expect(s).toHaveAttribute("aria-checked", "false");
});

test("Switch track is 34x20 with a 14px round thumb", async ({ page, mount }) => {
  await mount(<Switch checked={false} aria-label="x" />);
  const s = page.getByRole("switch");
  await expect(s).toHaveCSS("width", "34px");
  await expect(s).toHaveCSS("height", "20px");
  const thumb = s.locator(".is_SwitchThumb");
  await expect(thumb).toHaveCSS("width", "14px");
  await expect(thumb).toHaveCSS("height", "14px");
});

test("Switch thumb travels right when checked", async ({ page, mount }) => {
  const c = await mount(<Switch checked={false} aria-label="x" />);
  const s = page.getByRole("switch");
  const thumb = s.locator(".is_SwitchThumb");
  const track = (await s.boundingBox())!;
  const off = (await thumb.boundingBox())!;
  expect(off.x - track.x).toBeLessThan(track.width / 2 - off.width / 2);
  await c.update(<Switch checked aria-label="x" />);
  await expect
    .poll(async () => {
      const on = (await thumb.boundingBox())!;
      return on.x + on.width / 2 - track.x;
    })
    .toBeGreaterThan(track.width / 2);
});

test("Switch hit area extends to 28px tall (the ::after sleeve toggles it)", async ({ page, mount }) => {
  const seen: boolean[] = [];
  await mount(
    <div style={{ padding: 20 }}>
      <Switch checked={false} onCheckedChange={(v) => seen.push(v)} aria-label="x" />
    </div>,
  );
  const box = (await page.getByRole("switch").boundingBox())!;
  // 3px above the visible track: outside the 20px box, inside the 28px sleeve.
  await page.mouse.click(box.x + box.width / 2, box.y - 3);
  await expect.poll(() => seen).toEqual([true]);
});

for (const mode of ["light", "dark"] as const) {
  test(`Switch on paints the --xh-accent track (${mode})`, async ({ page, mount }) => {
    await mount(<Switch checked aria-label="x" />, { hooksConfig: { mode } satisfies HooksConfig });
    const s = page.getByRole("switch");
    const accent = await resolved(s, "accent");
    await expect(s).toHaveCSS("background-color", accent);
    await expect(s).toHaveCSS("border-top-color", accent);
    await expect(s.locator(".is_SwitchThumb")).toHaveCSS("background-color", await resolved(s, "panel"));
  });

  test(`Switch off is a recessed slot with a --xh-line border (${mode})`, async ({ page, mount }) => {
    await mount(<Switch checked={false} aria-label="x" />, { hooksConfig: { mode } satisfies HooksConfig });
    const s = page.getByRole("switch");
    await expect(s).toHaveCSS("border-top-color", await resolved(s, "line"));
    const bg = await s.evaluate((n) => getComputedStyle(n).backgroundColor);
    expect(bg).not.toBe(await resolved(s, "accent"));
    expect(bg).not.toBe("rgba(0, 0, 0, 0)");
  });

  test(`Switch off thumb is distinguishable from its track, >= 3:1 non-text contrast (${mode})`, async ({ page, mount }) => {
    // BUG (switch.tsx:23,37): the off knob (muted 72% into panel) against the off track (muted 12%
    // into code) is 2.52:1 in light and 2.98:1 in dark, under WCAG 1.4.11's 3:1 for the graphic
    // that identifies the state, though the comment says it "stays legible in both themes".
    test.fail(true, "off-state knob below 3:1 against its track");
    await mount(<Switch checked={false} aria-label="x" />, { hooksConfig: { mode } satisfies HooksConfig });
    const s = page.getByRole("switch");
    const track = await s.evaluate((n) => getComputedStyle(n).backgroundColor);
    const knob = await s.locator(".is_SwitchThumb").evaluate((n) => getComputedStyle(n).backgroundColor);
    expect(await ratio(s, knob, track)).toBeGreaterThanOrEqual(3);
  });

  test(`Switch on thumb against the accent track >= 3:1 (${mode})`, async ({ page, mount }) => {
    await mount(<Switch checked aria-label="x" />, { hooksConfig: { mode } satisfies HooksConfig });
    const s = page.getByRole("switch");
    const track = await s.evaluate((n) => getComputedStyle(n).backgroundColor);
    const knob = await s.locator(".is_SwitchThumb").evaluate((n) => getComputedStyle(n).backgroundColor);
    expect(await ratio(s, knob, track)).toBeGreaterThanOrEqual(3);
  });

  test(`Switch focus-visible ring is 2px solid --xh-accent, offset 2px (${mode})`, async ({ page, mount }) => {
    await mount(<Switch checked={false} aria-label="x" />, { hooksConfig: { mode } satisfies HooksConfig });
    const s = page.getByRole("switch");
    await page.keyboard.press("Tab");
    await expect(s).toBeFocused();
    await expect(s).toHaveCSS("outline-style", "solid");
    await expect(s).toHaveCSS("outline-width", "2px");
    await expect(s).toHaveCSS("outline-offset", "2px");
    await expect(s).toHaveCSS("outline-color", await resolved(s, "accent"));
  });
}

test("Switch disabled: not operable by click or keyboard", async ({ page, mount }) => {
  const seen: boolean[] = [];
  await mount(<Switch checked={false} disabled onCheckedChange={(v) => seen.push(v)} aria-label="x" />);
  const s = page.getByRole("switch");
  await expect(s).toBeDisabled();
  await s.click({ force: true });
  await s.focus();
  await page.keyboard.press("Space");
  await expect(s).toHaveAttribute("aria-checked", "false");
  expect(seen).toEqual([]);
});
