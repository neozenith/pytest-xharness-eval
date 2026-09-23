/**
 * `RecordCardCodex`: the card with its harness fixed to `codex`. Codex's two tool dialects
 * (`exec` JavaScript and `apply_patch`), its command executions and its token counts each get
 * their renderer; a Claude line handed to it is classified as Codex would, never as Claude.
 */
import { expect, test } from "@playwright/experimental-ct-react";
import { RecordCardCodex } from "../src/components/records/RecordCard";
import { ANSI_TEXT, claudeToolUse, codexCompleted, codexResponse, codexTokenCount } from "./fixtures";

test("an exec_command call shows its cmd as bash, its workdir, and the JavaScript collapsed", async ({ mount }) => {
  const rec = codexResponse({
    type: "custom_tool_call",
    name: "exec",
    call_id: "call_1",
    status: "completed",
    input: 'const r = await tools.exec_command({ cmd: "bun run check", workdir: "/w", yield_time_ms: 1000 });',
  });
  const c = await mount(<RecordCardCodex lineNo={30} raw={JSON.stringify(rec)} view="nice" />);
  await expect(c.locator("#L30")).toHaveAttribute("data-harness", "codex");
  const exec = c.locator('[data-el="T.exec"]');
  await expect(exec.locator('[data-el="V.bash"]')).toContainText("bun run check");
  await expect(exec.locator('[data-el="V.kvs"]')).toContainText("workdir/w");
  await expect(exec.locator('[data-el="V.kvs"]')).toContainText("yield_time_ms1000");
  const js = exec.locator(".language-javascript");
  await expect(js).toBeHidden();
  await exec.getByText("full tool input (javascript)").click();
  await expect(js).toBeVisible();
  await expect(js.locator(".hljs-keyword").first()).toBeVisible();
});

test("an apply_patch exec renders the patch as a highlighted diff", async ({ mount }) => {
  const patch = "*** Begin Patch\\n*** Add File: a.md\\n+# A\\n*** End Patch";
  const rec = codexResponse({ type: "custom_tool_call", name: "exec", call_id: "c", input: `tools.apply_patch("${patch}")` });
  const c = await mount(<RecordCardCodex lineNo={31} raw={JSON.stringify(rec)} view="nice" />);
  const diff = c.locator('[data-el="T.exec"] > [data-el="V.diff"]');
  await expect(diff).toContainText("*** Add File: a.md");
  await expect(diff.locator(".hljs-addition")).toContainText("+# A");
});

test("a command execution shows cwd, exit, the command and its ANSI output", async ({ mount }) => {
  const rec = codexCompleted({
    item_type: "CommandExecution",
    command: ["bash", "-lc", "pytest"],
    cwd: "/w",
    status: "failed",
    exit_code: 1,
    aggregated_output: ANSI_TEXT,
  });
  const c = await mount(<RecordCardCodex lineNo={32} raw={JSON.stringify(rec)} view="nice" />);
  const body = c.locator('[data-el="R.codex/event_msg/item_completed/CommandExecution"]');
  await expect(body.locator('[data-el="V.kvs"]').first()).toContainText("exit1");
  await expect(body.locator('[data-el="V.bash"]')).toContainText("bash -lc pytest");
  await expect(body.locator('[data-el="V.ansi"]')).toContainText("FAILED");
  await expect(body.locator('[data-el="V.ansi"]')).not.toContainText("\u001b");
});

test("a token_count shows this call and the cumulative usage, captioned", async ({ mount }) => {
  const c = await mount(<RecordCardCodex lineNo={33} raw={JSON.stringify(codexTokenCount())} view="nice" />);
  const body = c.locator('[data-el="R.codex/event_msg/token_count"]');
  await expect(body.locator(".sublabel")).toHaveText(["this call", "cumulative"]);
  const grids = body.locator('[data-el="V.usage"]');
  await expect(grids).toHaveCount(2);
  await expect(grids.nth(0)).toContainText("input10,000");
  await expect(grids.nth(0)).toContainText("cache read8,000");
  await expect(grids.nth(0)).toContainText("thinking64");
  await expect(grids.nth(1)).toContainText("total30,400");
  await expect(body).toContainText("context window258,400");
});

test("a Claude line handed to the Codex card is classified as Codex would", async ({ mount }) => {
  const c = await mount(<RecordCardCodex lineNo={34} raw={JSON.stringify(claudeToolUse("Bash", { command: "ls" }))} view="nice" />);
  await expect(c.locator("#L34")).toHaveAttribute("data-kind", "codex/assistant");
  await expect(c.locator('[data-el="R.fallback"]')).toContainText('"Bash"');
});
