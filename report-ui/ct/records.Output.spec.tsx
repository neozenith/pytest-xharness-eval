/** `Output`: tool output sniffed as JSON, a diff, ANSI or plain text. */
import { expect, test } from "./test";
import { Output } from "../src/components/records/values";
import { ANSI_TEXT } from "./fixtures";

test("JSON output is parsed and pretty-printed", async ({ mount }) => {
  const c = await mount(<Output text={'  {"ok":true,"n":[1,2]}  '} title="output" />);
  await expect(c.locator('[data-el="V.output"]')).toHaveCount(1);
  await expect(c.locator('[data-el="V.json"] .ch-title')).toHaveText("output");
  await expect(c.locator('[data-el="V.json"] .hljs-attr')).toHaveText(['"ok"', '"n"']);
});

test("text that only looks like JSON stays text", async ({ mount }) => {
  const c = await mount(<Output text="{this is not json}" />);
  await expect(c.locator('[data-el="V.json"]')).toHaveCount(0);
  await expect(c.locator("code")).toHaveText("{this is not json}");
});

test("a diff is highlighted as a diff", async ({ mount }) => {
  const c = await mount(<Output text={"diff --git a/x b/x\n@@ -1 +1 @@\n-a\n+b"} />);
  await expect(c.locator('[data-el="V.diff"] .hljs-addition')).toHaveText("+b");
  await c.update(<Output text={"*** Begin Patch\n*** Update File: x\n-a\n+b\n*** End Patch"} />);
  await expect(c.locator('[data-el="V.diff"]')).toBeVisible();
});

test("ANSI output renders in colour", async ({ mount }) => {
  const c = await mount(<Output text={ANSI_TEXT} title="output" />);
  await expect(c.locator('[data-el="V.ansi"] .ch-title')).toHaveText("output");
  await expect(c.locator('[data-el="V.ansi"]')).not.toContainText("\u001b");
});

test("plain output is a plain, unhighlighted code block", async ({ mount }) => {
  const c = await mount(<Output text={"total 0\n-rw-r--r-- README.md"} />);
  await expect(c.locator("code.language-text")).toHaveText("total 0\n-rw-r--r-- README.md");
});

test("empty output is nothing", async ({ mount, page }) => {
  await mount(<Output text="" />);
  await expect(page.locator("#root")).toBeEmpty();
});
