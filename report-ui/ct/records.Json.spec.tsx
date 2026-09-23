/** `Json`: a value pretty-printed and highlighted as JSON, optionally titled. */
import { expect, test } from "@playwright/experimental-ct-react";
import { Json } from "../src/components/records/values";

test("an object is pretty-printed with one-space indent and highlighted keys", async ({ mount }) => {
  const c = await mount(<Json value={{ a: 1, b: [true, null] }} title="tasks" />);
  await expect(c.locator('[data-el="V.json"]')).toHaveCount(1);
  await expect(c.locator(".ch-title")).toHaveText("tasks");
  await expect(c.locator(".ch-lang")).toHaveText("json");
  await expect(c.locator("code")).toHaveText('{\n "a": 1,\n "b": [\n  true,\n  null\n ]\n}');
  await expect(c.locator(".hljs-attr")).toHaveText(['"a"', '"b"']);
  await expect(c.locator(".hljs-literal")).toHaveText(["true", "null"]);
});

test("a string value is shown as-is (not re-quoted)", async ({ mount }) => {
  const c = await mount(<Json value="{not json" />);
  await expect(c.locator("code")).toHaveText("{not json");
});

test("untitled JSON has no head, and its scroll box is named 'json'", async ({ mount }) => {
  const c = await mount(<Json value={[1]} />);
  await expect(c.locator(".code-head")).toHaveCount(0);
  await expect(c.locator("pre")).toHaveAttribute("aria-label", "json (scrollable)");
});
