/**
 * `RecordCardClaude`: the card with its harness fixed to `claude`. Whatever the line, it is
 * classified through the `claude/*` catalogue: a Codex line handed to it is not a Codex kind.
 */
import { expect, test } from "@playwright/experimental-ct-react";
import { RecordCardClaude } from "../src/components/records/RecordCard";
import { claudeAssistant, claudeToolResult, claudeToolUse, claudeUser, codexTokenCount } from "./fixtures";

test("classifies through the claude catalogue and anchors at L<line>", async ({ mount }) => {
  const c = await mount(
    <RecordCardClaude lineNo={21} raw={JSON.stringify(claudeToolUse("Grep", { pattern: "TODO", path: "src", output_mode: "content" }))} view="nice" />,
  );
  const card = c.locator("#L21");
  await expect(card).toHaveAttribute("data-harness", "claude");
  await expect(card).toHaveAttribute("data-kind", "claude/assistant/tool_use");
  await expect(card).toHaveAttribute("data-el", "RecordCard");
  await expect(c.locator('[data-el="T.Grep"]')).toContainText("TODO");
});

test("the glossary chain RecordCard > R.<kind> > claudeMessage > B.tool_use > T.Bash > V.bash is in the DOM", async ({ mount }) => {
  const c = await mount(<RecordCardClaude lineNo={1} raw={JSON.stringify(claudeToolUse("Bash", { command: "ls -la" }))} view="nice" />);
  await expect(
    c.locator('[data-el="R.claude/assistant/tool_use"] [data-el="claudeMessage"] [data-el="B.tool_use"] [data-el="T.Bash"] [data-el="V.bash"]'),
  ).toContainText("ls -la");
});

test("a prompt, a text answer and a tool result each render their own content", async ({ mount }) => {
  const c = await mount(<RecordCardClaude lineNo={1} raw={JSON.stringify(claudeUser("draw the architecture"))} view="nice" />);
  await expect(c.locator('[data-el="R.claude/user/prompt"] [data-el="V.text"] .txt')).toHaveText("draw the architecture");
  await c.update(<RecordCardClaude lineNo={2} raw={JSON.stringify(claudeAssistant([{ type: "text", text: "Both gates pass." }]))} view="nice" />);
  await expect(c.locator('[data-el="B.text"]')).toContainText("Both gates pass.");
  await c.update(<RecordCardClaude lineNo={3} raw={JSON.stringify(claudeToolResult("ok", { is_error: true }))} view="nice" />);
  await expect(c.locator('[data-el="B.tool_result"] .bad')).toHaveText("true");
});

test("a Codex line handed to the Claude card is not read as Codex: it falls back visibly", async ({ mount }) => {
  const c = await mount(<RecordCardClaude lineNo={4} raw={JSON.stringify(codexTokenCount())} view="nice" />);
  await expect(c.locator("#L4")).toHaveAttribute("data-kind", "claude/event_msg");
  await expect(c.locator('[data-el="R.fallback"]')).toContainText("token_count");
});
