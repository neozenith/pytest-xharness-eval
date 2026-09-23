/**
 * `Block`: one content block, left-ruled in its category's colour and headed by its type. A
 * block type with no renderer falls back to its JSON under a grey rule.
 */
import { expect, test } from "@playwright/experimental-ct-react";
import { Block } from "../src/components/records/blocks";
import { CATEGORIES } from "../src/lib/records";
import { ANSI_TEXT } from "./fixtures";

const rgb = (hex: string): string => {
  const n = parseInt(hex.slice(1), 16);
  return `rgb(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255})`;
};

const RULED: [string, Record<string, unknown>, string][] = [
  ["text", { type: "text", text: "hello" }, "assistant_text"],
  ["thinking", { type: "thinking", thinking: "hmm" }, "thinking"],
  ["tool_use", { type: "tool_use", id: "t1", name: "Bash", input: { command: "ls" } }, "tool_call"],
  ["tool_result", { type: "tool_result", tool_use_id: "t1", content: "ok" }, "tool_result"],
];

for (const [type, block, category] of RULED) {
  test(`${type} is headed by its type and ruled in the ${category} colour`, async ({ mount }) => {
    const c = await mount(<Block block={block} />);
    await expect(c.locator(".block").first()).toHaveClass(new RegExp(`\\bblock ${type}\\b`));
    await expect(c.locator(".bhead")).toHaveText(type);
    await expect(c.locator(`[data-el="B.${type}"]`)).toHaveCount(1);
    await expect(c.locator(".block").first()).toHaveCSS("border-left-color", rgb(CATEGORIES[category]!));
  });
}

test("input_text, output_text and Text render as prose", async ({ mount }) => {
  for (const type of ["input_text", "output_text", "Text"]) {
    const c = await mount(<Block block={{ type, text: `a ${type}` }} />);
    await expect(c.locator(`[data-el="B.${type}"] [data-el="V.text"] .txt`)).toHaveText(`a ${type}`);
    await c.unmount();
  }
});

test("redacted_thinking says so", async ({ mount }) => {
  const c = await mount(<Block block={{ type: "redacted_thinking", data: "opaque" }} />);
  await expect(c).toContainText("(redacted thinking)");
  await expect(c).not.toContainText("opaque");
});

test("tool_use shows its tool, id and caller, then the tool's own renderer", async ({ mount }) => {
  const c = await mount(<Block block={{ type: "tool_use", id: "toolu_9", name: "Read", input: { file_path: "a.md" }, caller: { type: "direct" } }} />);
  const kvs = c.locator('[data-el="B.tool_use"] > [data-el="V.kvs"]');
  await expect(kvs).toContainText("toolRead");
  await expect(kvs).toContainText("idtoolu_9");
  await expect(kvs).toContainText("callerdirect");
  await expect(c.locator('[data-el="T.Read"]')).toContainText("filea.md");
});

test("tool_result: is_error in red, list content joined, ANSI in colour", async ({ mount }) => {
  const c = await mount(
    <Block
      block={{
        type: "tool_result",
        tool_use_id: "t",
        is_error: true,
        content: [
          { type: "text", text: "line one" },
          { type: "text", text: "line two" },
        ],
      }}
    />,
  );
  await expect(c.locator(".bad")).toHaveText("true");
  await expect(c.locator('[data-el="V.output"]')).toContainText("line one\nline two");
  await c.update(<Block block={{ type: "tool_result", tool_use_id: "t", content: ANSI_TEXT }} />);
  await expect(c).toContainText("is_errorfalse");
  await expect(c.locator('[data-el="V.ansi"] code.ansi span').first()).toHaveCSS("color", "rgb(187, 0, 0)");
});

test("an unknown block type falls back to JSON under the neutral rule", async ({ mount }) => {
  const c = await mount(<Block block={{ type: "image", source: { media_type: "image/png" } }} />);
  await expect(c.locator(".bhead")).toHaveText("image");
  await expect(c.locator('[data-el="B.fallback"] [data-el="V.json"]')).toContainText('"media_type": "image/png"');
  await expect(c.locator('[data-el="B.fallback"] > .comp-label')).toHaveCSS("opacity", "1");
});

test("a block with no type is 'unknown', and a bare string is prose", async ({ mount }) => {
  const c = await mount(<Block block={{ foo: 1 }} />);
  await expect(c.locator(".bhead")).toHaveText("unknown");
  await c.update(<Block block="just words" />);
  await expect(c.locator('[data-el="V.text"] .txt')).toHaveText("just words");
});
