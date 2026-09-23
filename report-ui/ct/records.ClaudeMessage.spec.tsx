/**
 * `ClaudeMessage`: a Claude API message: its blocks, then the call's model, stop reason and id,
 * then a captioned token grid (with the 1h/5m cache split when the API reports it).
 */
import { expect, test } from "./test";
import { ClaudeMessage } from "../src/components/records/blocks";
import { claudeAssistant } from "./fixtures";

const message = (content: unknown = [{ type: "text", text: "Both gates pass." }]) => (claudeAssistant(content) as { message: Record<string, unknown> }).message;

test("blocks first, then model, stop and message id", async ({ mount }) => {
  const c = await mount(<ClaudeMessage message={message()} />);
  await expect(c.locator('[data-el="claudeMessage"]')).toHaveCount(1);
  await expect(c.locator('[data-el="B.text"]')).toContainText("Both gates pass.");
  const call = c.locator('[data-el="claudeMessage"] > [data-el="V.kvs"]');
  await expect(call).toContainText("modelclaude-opus-5");
  await expect(call).toContainText("stoptool_use");
  await expect(call).toContainText("message idmsg_011");
});

test("usage is captioned 'tokens' and grids every tier, with the 1h / 5m split", async ({ mount }) => {
  const c = await mount(<ClaudeMessage message={message()} />);
  await expect(c.locator('[data-el="claudeMessage"] > .sublabel')).toHaveText("tokens");
  const usage = c.locator('[data-el="V.usage"]');
  await expect(usage).toContainText("input2");
  await expect(usage).toContainText("cache read35,865");
  await expect(usage).toContainText("cache write4,234");
  await expect(usage).toContainText("1h / 5m4,234 / 0");
  await expect(usage).toContainText("output264");
});

test("a message without usage has no caption and no grid", async ({ mount }) => {
  const c = await mount(<ClaudeMessage message={{ model: "claude-opus-5", content: [{ type: "text", text: "hi" }] }} />);
  await expect(c.locator(".sublabel")).toHaveCount(0);
  await expect(c.locator('[data-el="V.usage"]')).toHaveCount(0);
});

test("text, thinking and tool_use blocks side by side each keep their own renderer", async ({ mount }) => {
  const c = await mount(
    <ClaudeMessage
      message={message([
        { type: "thinking", thinking: "plan" },
        { type: "text", text: "now run it" },
        { type: "tool_use", id: "t", name: "Write", input: { file_path: "a.json", content: '{"a": 1}' } },
      ])}
    />,
  );
  await expect(c.locator('[data-el="B.thinking"]')).toContainText("plan");
  await expect(c.locator('[data-el="B.text"]')).toContainText("now run it");
  await expect(c.locator('[data-el="T.Write"] code.language-json .hljs-attr')).toHaveText('"a"');
});

test("a non-object message renders only its label frame, never a crash", async ({ mount, page }) => {
  await mount(<ClaudeMessage message="not an object" />);
  await expect(page.locator('#root [data-el="V.text"]')).toHaveCount(0);
});
