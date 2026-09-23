/** `Diff`: a unified diff with removed and added lines highlighted. */
import { expect, test } from "@playwright/experimental-ct-react";
import { Diff } from "../src/components/records/values";
import type { HooksConfig } from "../playwright/index";

const DIFF = "--- a.md\n+++ a.md\n@@ -1,2 +1,2 @@\n-old line\n+new line\n context";

test("removals, additions and hunk headers carry their highlight classes", async ({ mount }) => {
  const c = await mount(<Diff text={DIFF} title="unified diff" />);
  await expect(c.locator('[data-el="V.diff"]')).toHaveCount(1);
  await expect(c.locator(".hljs-deletion").last()).toHaveText("-old line");
  await expect(c.locator(".hljs-addition").last()).toHaveText("+new line");
  await expect(c.locator(".hljs-meta")).toContainText("@@ -1,2 +1,2 @@");
  await expect(c.locator(".hljs-deletion").last()).toHaveCSS("color", "rgb(179, 29, 40)");
});

test("dark mode recolours the diff", async ({ mount }) => {
  const c = await mount<HooksConfig>(<Diff text={DIFF} />, { hooksConfig: { mode: "dark" } });
  await expect(c.locator(".hljs-deletion").last()).toHaveCSS("color", "rgb(255, 161, 152)");
});
