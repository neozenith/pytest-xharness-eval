/**
 * `Code`: a titled, highlighted, scrollable code block. highlight.js is bundled; its theme is
 * injected once and has a dark variant. Unknown languages show plain; ANSI switches to colour.
 */
import { expect, test } from "./test";
import { Code } from "../src/components/records/values";
import type { HooksConfig } from "../playwright/index";
import { ANSI_TEXT, UNBROKEN } from "./fixtures";

const LANGS: [string, string, string][] = [
  ["python", "def f():\n    return 1", ".hljs-keyword"],
  ["typescript", "const x: number = 1;", ".hljs-keyword"],
  ["javascript", "let a = 'b';", ".hljs-string"],
  ["json", '{"a": 1}', ".hljs-attr"],
  ["yaml", "key: value", ".hljs-attr"],
  ["markdown", "# Title", ".hljs-section"],
  ["bash", 'echo "x"', ".hljs-built_in"],
  ["xml", "<a href='x'>y</a>", ".hljs-tag"],
  ["css", ".a { color: red; }", ".hljs-selector-class"],
  ["ini", "[section]\nk = v", ".hljs-section"],
  ["diff", "-a\n+b", ".hljs-addition"],
];

for (const [lang, src, cls] of LANGS) {
  test(`${lang} is highlighted (${cls})`, async ({ mount }) => {
    const c = await mount(<Code lang={lang} text={src} title="content" />);
    await expect(c.locator(`code.hljs.language-${lang}`)).toBeVisible();
    await expect(c.locator(`code ${cls}`).first()).toBeVisible();
    await expect(c.locator(".ch-lang")).toHaveText(lang);
  });
}

test("the highlight theme is injected once, however many blocks mount", async ({ mount, page }) => {
  await mount(
    <div>
      <Code lang="json" text="{}" />
      <Code lang="python" text="pass" />
    </div>,
  );
  await expect(page.locator("style#xh-hljs-theme")).toHaveCount(1);
});

test("light theme token colours", async ({ mount }) => {
  const c = await mount(<Code lang="python" text={'def f():\n    return "s"'} />);
  await expect(c.locator(".hljs-keyword").first()).toHaveCSS("color", "rgb(215, 58, 73)");
  await expect(c.locator(".hljs-string")).toHaveCSS("color", "rgb(34, 134, 58)");
});

test("dark theme token colours", async ({ mount }) => {
  const c = await mount<HooksConfig>(<Code lang="python" text={'def f():\n    return "s"'} />, { hooksConfig: { mode: "dark" } });
  await expect(c.locator(".hljs-keyword").first()).toHaveCSS("color", "rgb(255, 123, 114)");
  await expect(c.locator(".hljs-string")).toHaveCSS("color", "rgb(126, 231, 135)");
  await expect(c.locator("pre.xh-pre")).toHaveCSS("background-color", "rgb(31, 35, 48)");
});

test("an unknown or empty language shows plain text, escaped", async ({ mount }) => {
  const c = await mount(<Code lang="cobol" text="<b>not bold</b>" />);
  await expect(c.locator("code.hljs")).toHaveText("<b>not bold</b>");
  await expect(c.locator("code b")).toHaveCount(0);
  await expect(c.locator(".code-head")).toHaveCount(0);
  await c.update(<Code lang="" text="plain" />);
  await expect(c.locator("code.language-text")).toHaveText("plain");
});

test("markup inside highlighted code is escaped", async ({ mount }) => {
  const c = await mount(<Code lang="json" text={'{"x": "<img src=x onerror=alert(1)>"}'} />);
  await expect(c.locator("img")).toHaveCount(0);
});

test("a non-string value is pretty-printed", async ({ mount }) => {
  const c = await mount(<Code lang="json" text={{ a: [1] }} />);
  await expect(c.locator("code")).toContainText('"a": [');
});

test("ANSI inside code is rendered as colour instead of highlighted", async ({ mount }) => {
  const c = await mount(<Code lang="bash" text={ANSI_TEXT} />);
  await expect(c.locator('[data-el="V.ansi"]')).toBeVisible();
  await expect(c.locator(".hljs")).toHaveCount(0);
});

test("a long block scrolls inside its capped box, never the page", async ({ mount, page }) => {
  const c = await mount(<Code lang="bash" text={`${UNBROKEN}\n`.repeat(200)} title="huge" />);
  const pre = c.locator("pre.xh-pre");
  await expect(pre).toHaveCSS("overflow", "auto");
  const [client, scroll] = await pre.evaluate((el) => [el.clientHeight, el.scrollHeight]);
  expect(scroll).toBeGreaterThan(client!);
  expect(client!).toBeLessThanOrEqual(800 * 0.6 + 1);
  expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(0);
  await pre.focus();
  await expect(pre).toBeFocused();
});
