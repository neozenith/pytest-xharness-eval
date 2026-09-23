/** `Xmlish`: harness-injected XML-tagged text as titled sections, nested and with markdown bodies. */
import { expect, test } from "@playwright/experimental-ct-react";
import { Xmlish } from "../src/components/records/values";
import { CATEGORIES } from "../src/lib/records";

const rgb = (hex: string): string => {
  const n = parseInt(hex.slice(1), 16);
  return `rgb(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255})`;
};

test("each top-level element is a section ruled in the harness_context colour", async ({ mount }) => {
  const c = await mount(<Xmlish text={'lead-in\n<a>one</a>\n<b attr="1">two</b>\ntail'} />);
  await expect(c.locator('[data-el="V.xmlish"]')).toHaveCount(1);
  const sections = c.locator('[data-el="V.xmlish"] > .block.xml');
  await expect(sections).toHaveCount(2);
  await expect(sections.locator(".bhead .tag")).toHaveText(["<a>", "<b>"]);
  await expect(sections.nth(1).locator(".bhead code")).toHaveText('attr="1"');
  await expect(sections.first()).toHaveCSS("border-left-color", rgb(CATEGORIES.harness_context!));
  await expect(c.locator('[data-el="V.xmlish"] > [data-el="V.text"] .txt')).toHaveText(["lead-in", "tail"]);
});

test("nested elements nest; a markdown body is highlighted as markdown", async ({ mount }) => {
  const c = await mount(<Xmlish text={"<outer><inner>x</inner></outer><notes>- one\n- two</notes>"} />);
  await expect(c.locator(".block.xml .block.xml .bhead .tag")).toHaveText("<inner>");
  await expect(c.locator("code.language-markdown .hljs-bullet").first()).toBeVisible();
});

test("text with no elements is plain prose", async ({ mount }) => {
  const c = await mount(<Xmlish text="<unclosed> only" />);
  await expect(c.locator(".block")).toHaveCount(0);
  await expect(c.locator('[data-el="V.text"] .txt')).toHaveText("<unclosed> only");
});
