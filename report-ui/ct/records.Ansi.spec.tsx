/** `Ansi`: terminal output rendered in colour through ansi_up; the escape codes never show. */
import { expect, test } from "./test";
import { Ansi } from "../src/components/records/values";
import { ANSI_TEXT } from "./fixtures";

test("colour codes become coloured spans, and nothing of the text is stripped", async ({ mount }) => {
  const c = await mount(<Ansi text={ANSI_TEXT} title="output" />);
  await expect(c.locator('[data-el="V.ansi"]')).toHaveCount(1);
  await expect(c.locator(".ch-title")).toHaveText("output");
  await expect(c.locator(".ch-lang")).toHaveText("ansi");
  await expect(c.locator("code.ansi")).toHaveText("FAILED tests/test_x.py::test_y\nPASSED tests/test_x.py::test_z");
  await expect(c.locator("code.ansi span", { hasText: "FAILED" })).toHaveCSS("color", "rgb(187, 0, 0)");
  await expect(c.locator("code.ansi span", { hasText: "PASSED" })).toHaveCSS("color", "rgb(0, 187, 0)");
});

test("bold and 256-colour codes render too", async ({ mount }) => {
  const c = await mount(<Ansi text={"\u001b[1mbold\u001b[0m \u001b[38;5;208morange\u001b[0m"} />);
  await expect(c.locator("code.ansi span", { hasText: "bold" })).toHaveCSS("font-weight", "700");
  await expect(c.locator("code.ansi span", { hasText: "orange" })).toHaveCSS("color", "rgb(255, 135, 0)");
  await expect(c.locator(".code-head")).toHaveCount(0);
});

test("markup in the output is escaped, not injected", async ({ mount }) => {
  const c = await mount(<Ansi text={"\u001b[31m<img src=x onerror=alert(1)>\u001b[0m"} />);
  await expect(c.locator("img")).toHaveCount(0);
  await expect(c).toContainText("<img src=x onerror=alert(1)>");
});

test("the scroll box is focusable and named for a keyboard", async ({ mount }) => {
  const c = await mount(<Ansi text={ANSI_TEXT} title="output" />);
  const pre = c.locator("pre.xh-pre");
  await expect(pre).toHaveAttribute("tabindex", "0");
  await expect(pre).toHaveAttribute("role", "region");
  await expect(pre).toHaveAttribute("aria-label", "output · ansi (scrollable)");
});
