/** `Envelope`: the harness's bookkeeping fields, collapsed, for either dialect. */
import { expect, test } from "./test";
import { Envelope } from "../src/components/records/values";
import { claudeToolUse, codexTurnContext } from "./fixtures";

test("a Claude record's envelope, opened", async ({ mount }) => {
  const c = await mount(<Envelope rec={claudeToolUse("Bash", { command: "ls" })} />);
  await expect(c.locator('[data-el="V.envelope"]')).toHaveCount(1);
  const kvs = c.locator('[data-el="V.kvs"]');
  await expect(kvs).toBeHidden();
  await c.getByText("record envelope").click();
  await expect(kvs.locator("b")).toHaveText(["timestamp", "uuid", "requestId", "sessionId", "effort"]);
  await expect(kvs).toContainText("efforthigh");
});

test("isSidechain false is shown, not dropped", async ({ mount }) => {
  const c = await mount(<Envelope rec={{ type: "user", isSidechain: false, gitBranch: "main", version: "2.1.90" }} />);
  await c.getByText("record envelope").click();
  await expect(c.locator('[data-el="V.kvs"]')).toContainText("isSidechainfalse");
  await expect(c.locator('[data-el="V.kvs"]')).toContainText("gitBranchmain");
});

test("a Codex record's envelope carries its timestamp and turn_id", async ({ mount }) => {
  const c = await mount(<Envelope rec={codexTurnContext()} />);
  await c.getByText("record envelope").click();
  await expect(c.locator('[data-el="V.kvs"] b')).toHaveText(["timestamp", "turn_id"]);
});

test("a record with no envelope fields renders no disclosure body", async ({ mount }) => {
  const c = await mount(<Envelope rec={{ type: "x" }} />);
  await c.getByText("record envelope").click();
  await expect(c.locator('[data-el="V.kvs"]')).toHaveCount(0);
});
