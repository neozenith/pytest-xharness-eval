/**
 * `Blocks`: a message's content. A string is prose; a list is one `Block` per element, in
 * order; anything else is nothing rather than a crash.
 */
import { expect, test } from "./test";
import { Blocks } from "../src/components/records/blocks";

test("a list renders one block per element, in order", async ({ mount, page }) => {
  await mount(
    <Blocks
      content={[
        { type: "thinking", thinking: "first" },
        { type: "text", text: "second" },
        { type: "tool_use", id: "t", name: "Bash", input: { command: "ls" } },
      ]}
    />,
  );
  await expect(page.locator("#root .block > .bhead")).toHaveText(["thinking", "text", "tool_use"]);
});

test("a string is prose, and an XML-tagged string is titled sections", async ({ mount, page }) => {
  const c = await mount(<Blocks content="plain words" />);
  await expect(c.locator('[data-el="V.text"]')).toHaveCount(1);
  await c.update(<Blocks content={"<command-name>/mermaidjs-diagrams</command-name>\n<command-args>draw</command-args>"} />);
  await expect(page.locator("#root .block.xml .bhead .tag")).toHaveText(["<command-name>", "<command-args>"]);
});

test("content that is neither a string nor a list renders nothing", async ({ mount, page }) => {
  await mount(<Blocks content={{ type: "text", text: "not in a list" }} />);
  await expect(page.locator("#root")).toBeEmpty();
});
