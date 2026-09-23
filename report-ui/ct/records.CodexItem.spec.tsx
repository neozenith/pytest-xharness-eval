/**
 * `CodexItem`: a Codex item's content blocks, with every other field of the item collapsed
 * into one JSON disclosure.
 */
import { expect, test } from "@playwright/experimental-ct-react";
import { CodexItem } from "../src/components/records/blocks";

test("content blocks show, the other item fields wait behind a disclosure", async ({ mount }) => {
  const c = await mount(<CodexItem item={{ item_type: "AgentMessage", id: "item_7", content: [{ type: "Text", text: "Done." }] }} />);
  await expect(c.locator('[data-el="codexItem"]')).toHaveCount(1);
  await expect(c.locator('[data-el="B.Text"]')).toContainText("Done.");
  const fields = c.locator('[data-el="V.details"] [data-el="V.json"]');
  await expect(fields).toBeHidden();
  await c.getByText("item fields").click();
  await expect(fields).toBeVisible();
  await expect(fields).toContainText('"id": "item_7"');
  await expect(fields).not.toContainText("Done.");
});

test("an item with no content still offers its fields", async ({ mount }) => {
  const c = await mount(<CodexItem item={{ item_type: "Mystery", foo: "bar" }} />);
  await expect(c.locator(".block")).toHaveCount(0);
  await c.getByText("item fields").click();
  await expect(c.locator('[data-el="V.json"]')).toContainText('"foo": "bar"');
});
