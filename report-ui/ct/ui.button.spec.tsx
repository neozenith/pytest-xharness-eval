/**
 * `Button` (src/components/ui/button.tsx): a Tamagui frame rendered as `<button>`, two variants,
 * four sizes, per-size typography, string children wrapped in an inheriting Text node, and
 * `render={<a href/>}` for link-shaped buttons.
 */
import { expect, test } from "@playwright/experimental-ct-react";
import type { Locator } from "@playwright/test";
import { Button } from "../src/components/ui/button";
import type { HooksConfig } from "../playwright/index";

/** What `var(--xh-<token>)` resolves to on this page, serialised as computed colours are. */
const resolved = (el: Locator, token: string) =>
  el.evaluate((_, t) => {
    const probe = document.createElement("span");
    probe.style.color = `var(--xh-${t})`;
    document.body.append(probe);
    const out = getComputedStyle(probe).color;
    probe.remove();
    return out;
  }, token);

const SIZES = {
  default: { height: 32, padding: 14, fontSize: "13px", radius: "8px" },
  sm: { height: 28, padding: 10, fontSize: "12.5px", radius: "8px" },
  xs: { height: 26, padding: 8, fontSize: "11.5px", radius: "6px" },
  "icon-sm": { height: 32, padding: 0, fontSize: "13px", radius: "8px" },
} as const;

test("Button renders a native <button> named by its text", async ({ page, mount }) => {
  await mount(<Button>Run</Button>);
  const b = page.getByRole("button", { name: "Run" });
  await expect(b).toBeVisible();
  expect(await b.evaluate((n) => n.tagName)).toBe("BUTTON");
});

test("Button wraps a bare string child in a Text node that inherits the frame's type", async ({ page, mount }) => {
  await mount(<Button size="sm">Run</Button>);
  const b = page.getByRole("button", { name: "Run" });
  const text = b.getByText("Run", { exact: true });
  expect(await text.evaluate((n) => n.tagName)).toBe("SPAN");
  expect(await text.evaluate((n) => n.parentElement?.tagName)).toBe("BUTTON");
  await expect(text).toHaveCSS("font-size", "12.5px");
  await expect(text).toHaveCSS("color", await b.evaluate((n) => getComputedStyle(n).color));
  await expect(b).toHaveCSS("font-weight", "500");
  await expect(b).toHaveCSS("white-space", "nowrap");
});

test("Button wraps number and mixed children, leaving elements untouched", async ({ page, mount }) => {
  await mount(
    <Button>
      {"runs "}
      {3}
      <i data-testid="icon">*</i>
    </Button>,
  );
  const b = page.getByRole("button");
  await expect(b).toHaveText("runs 3*");
  expect(await b.evaluate((n) => [...n.children].map((c) => c.tagName))).toEqual(["SPAN", "SPAN", "I"]);
});

test("Button default is the outline variant: hairline border, panel fill", async ({ page, mount }) => {
  await mount(<Button>Run</Button>);
  const b = page.getByRole("button");
  await expect(b).toHaveCSS("border-top-color", await resolved(b, "line"));
  await expect(b).toHaveCSS("border-top-width", "1px");
  await expect(b).toHaveCSS("background-color", await resolved(b, "panel"));
  expect(await b.evaluate((n) => getComputedStyle(n).boxShadow)).not.toBe("none");
});

test("Button outline answers hover with the --xh-code fill", async ({ page, mount }) => {
  await mount(<Button variant="outline">Run</Button>);
  const b = page.getByRole("button");
  await b.hover();
  await expect(b).toHaveCSS("background-color", await resolved(b, "code"));
});

test("Button ghost is borderless and transparent until hovered", async ({ page, mount }) => {
  await mount(<Button variant="ghost">Run</Button>);
  const b = page.getByRole("button");
  await expect(b).toHaveCSS("background-color", "rgba(0, 0, 0, 0)");
  await expect(b).toHaveCSS("border-top-color", "rgba(0, 0, 0, 0)");
  await b.hover();
  await expect(b).toHaveCSS("background-color", await resolved(b, "code"));
});

for (const [size, want] of Object.entries(SIZES)) {
  test(`Button size=${size}: ${want.height}px tall, ${want.padding}px inline padding, ${want.fontSize} type`, async ({ page, mount }) => {
    await mount(<Button size={size as keyof typeof SIZES}>{size === "icon-sm" ? "+" : "Run"}</Button>);
    const b = page.getByRole("button");
    await expect(b).toHaveCSS("height", `${want.height}px`);
    await expect(b).toHaveCSS("padding-left", `${want.padding}px`);
    await expect(b).toHaveCSS("padding-right", `${want.padding}px`);
    await expect(b).toHaveCSS("font-size", want.fontSize);
    await expect(b).toHaveCSS("border-top-left-radius", want.radius);
    if (size === "icon-sm") await expect(b).toHaveCSS("width", "32px");
  });
}

test("Button every size but xs clears the 28px hit-target floor", async ({ page, mount }) => {
  await mount(
    <div>
      <Button size="default">a</Button>
      <Button size="sm">b</Button>
      <Button size="icon-sm">c</Button>
    </div>,
  );
  for (const name of ["a", "b", "c"]) {
    const box = await page.getByRole("button", { name }).boundingBox();
    expect(box!.height).toBeGreaterThanOrEqual(28);
  }
});

test("Button fires onClick on click, Enter and Space", async ({ page, mount }) => {
  let clicks = 0;
  await mount(<Button onClick={() => clicks++}>Run</Button>);
  const b = page.getByRole("button");
  await b.click();
  await expect.poll(() => clicks).toBe(1);
  await b.focus();
  await page.keyboard.press("Enter");
  await expect.poll(() => clicks).toBe(2);
  await page.keyboard.press("Space");
  await expect.poll(() => clicks).toBe(3);
});

test("Button forwards aria-label and id to the DOM node", async ({ page, mount }) => {
  await mount(
    <Button id="ThemeToggle" aria-label="switch to dark theme">
      ☾
    </Button>,
  );
  const b = page.getByRole("button", { name: "switch to dark theme" });
  await expect(b).toHaveAttribute("id", "ThemeToggle");
});

test("Button disabled: native disabled, dimmed, inert to click and Tab", async ({ page, mount }) => {
  let clicks = 0;
  await mount(
    <div>
      <Button disabled onClick={() => clicks++}>
        Run
      </Button>
      <Button>After</Button>
    </div>,
  );
  const b = page.getByRole("button", { name: "Run" });
  await expect(b).toBeDisabled();
  await expect(b).toHaveCSS("opacity", "0.5");
  await b.click({ force: true });
  await page.keyboard.press("Tab");
  await expect(page.getByRole("button", { name: "After" })).toBeFocused();
  expect(clicks).toBe(0);
});

for (const mode of ["light", "dark"] as const) {
  test(`Button focus-visible ring is 2px solid --xh-accent, offset 2px (${mode})`, async ({ page, mount }) => {
    await mount(<Button>Run</Button>, { hooksConfig: { mode } satisfies HooksConfig });
    const b = page.getByRole("button");
    await page.keyboard.press("Tab");
    await expect(b).toBeFocused();
    await expect(b).toHaveCSS("outline-style", "solid");
    await expect(b).toHaveCSS("outline-width", "2px");
    await expect(b).toHaveCSS("outline-offset", "2px");
    await expect(b).toHaveCSS("outline-color", await resolved(b, "accent"));
  });

  test(`Button outline colours follow the ${mode} tokens`, async ({ page, mount }) => {
    await mount(<Button>Run</Button>, { hooksConfig: { mode } satisfies HooksConfig });
    const b = page.getByRole("button");
    const panel = mode === "light" ? "rgb(255, 255, 255)" : "rgb(23, 26, 35)";
    await expect(b).toHaveCSS("background-color", panel);
    await expect(b).toHaveCSS("color", mode === "light" ? "rgb(27, 29, 35)" : "rgb(230, 232, 239)");
  });
}

test("Button render={<a href/>} is a link, keeps the button styling, and follows its href", async ({ page, mount }) => {
  await mount(
    <Button size="sm" render={<a href="#target" />}>
      Open
    </Button>,
  );
  const a = page.getByRole("link", { name: "Open" });
  await expect(a).toBeVisible();
  expect(await a.evaluate((n) => n.tagName)).toBe("A");
  await expect(a).toHaveAttribute("href", "#target");
  await expect(page.getByRole("button")).toHaveCount(0);
  await expect(a).toHaveCSS("height", "28px");
  await expect(a).toHaveCSS("border-top-color", await resolved(a, "line"));
  await a.focus();
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/#target$/);
});

test("Button render={<a/>} shows the same focus-visible ring", async ({ page, mount }) => {
  await mount(<Button render={<a href="#x" />}>Open</Button>);
  const a = page.getByRole("link");
  await page.keyboard.press("Tab");
  await expect(a).toBeFocused();
  await expect(a).toHaveCSS("outline-style", "solid");
  await expect(a).toHaveCSS("outline-color", await resolved(a, "accent"));
});

test("Button disabled shows the not-allowed cursor", async ({ page, mount }) => {
  // BUG (button.tsx:14): the frame's unconditional `cursor: "pointer"` is an atomic class that
  // outranks index.css's page-wide `button:disabled { cursor: not-allowed }` ("one disabled look
  // for every control"), so a disabled Button still promises a click. Expected not-allowed.
  test.fail(true, "disabled Button keeps cursor: pointer");
  await mount(<Button disabled>Run</Button>);
  await expect(page.getByRole("button")).toHaveCSS("cursor", "not-allowed", { timeout: 1_000 });
});
