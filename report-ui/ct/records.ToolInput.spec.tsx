/**
 * `ToolInput`: one tool call's payload by tool name. Claude's tools each lift their own fields
 * (Bash's command, Edit's diff, Write's content highlighted by extension); Codex's `exec` is
 * JavaScript whose `cmd` is dug out; any other tool shows its input as JSON or code.
 */
import { expect, test } from "@playwright/experimental-ct-react";
import { ToolInput } from "../src/components/records/tools";

test("Bash: description, timeout and background flag, then the command highlighted as bash", async ({ mount }) => {
  const c = await mount(<ToolInput name="Bash" input={{ command: 'echo "hi" | wc -l', description: "count", timeout: 5000, run_in_background: true }} />);
  await expect(c.locator('[data-el="T.Bash"]')).toHaveCount(1);
  const kvs = c.locator('[data-el="V.kvs"]');
  await expect(kvs).toContainText("descriptioncount");
  await expect(kvs).toContainText("timeout5000");
  await expect(kvs).toContainText("run_in_backgroundtrue");
  const bash = c.locator('[data-el="V.bash"]');
  await expect(bash.locator(".code-head .ch-title")).toHaveText("command");
  await expect(bash.locator(".code-head .ch-lang")).toHaveText("bash");
  await expect(bash.locator("code.hljs.language-bash .hljs-string")).toHaveText('"hi"');
  await expect(bash.locator("pre")).toHaveAttribute("aria-label", "command · bash (scrollable)");
});

test("Read, Skill, Glob and Grep lift their fields into a key/value grid", async ({ mount }) => {
  const c = await mount(<ToolInput name="Read" input={{ file_path: "SKILL.md", offset: 10, limit: 50 }} />);
  await expect(c.locator('[data-el="V.kvs"]')).toContainText("fileSKILL.md");
  await expect(c.locator('[data-el="V.kvs"]')).toContainText("offset10");
  await c.update(<ToolInput name="Skill" input={{ skill: "mermaidjs-diagrams", args: "draw" }} />);
  await expect(c.locator('[data-el="V.kvs"]')).toContainText("skillmermaidjs-diagrams");
  await c.update(<ToolInput name="Glob" input={{ pattern: "**/*.md" }} />);
  await expect(c.locator(".kvs")).toHaveText("pattern**/*.md");
  await c.update(<ToolInput name="Grep" input={{ pattern: "TODO", path: "src", glob: "*.ts", output_mode: "count" }} />);
  await expect(c.locator('[data-el="V.kvs"]')).toContainText("output_modecount");
});

test("Edit renders as a unified diff with removals and additions highlighted", async ({ mount }) => {
  const c = await mount(<ToolInput name="Edit" input={{ file_path: "a.py", old_string: "x = 1", new_string: "x = 2", replace_all: true }} />);
  await expect(c.locator('[data-el="V.kvs"]')).toContainText("replace_alltrue");
  const diff = c.locator('[data-el="V.diff"]');
  await expect(diff.locator(".ch-title")).toHaveText("edit");
  await expect(diff).toContainText("--- a.py");
  await expect(diff.locator(".hljs-deletion")).toContainText("-x = 1");
  await expect(diff.locator(".hljs-addition").last()).toContainText("+x = 2");
});

test("MultiEdit renders one numbered diff per edit", async ({ mount }) => {
  const c = await mount(
    <ToolInput
      name="MultiEdit"
      input={{
        file_path: "a.py",
        edits: [
          { old_string: "a", new_string: "b" },
          { old_string: "c", new_string: "d" },
        ],
      }}
    />,
  );
  await expect(c.locator('[data-el="V.diff"] .ch-title')).toHaveText(["edit 1", "edit 2"]);
});

test("Write highlights its content by the file's extension", async ({ mount }) => {
  const c = await mount(<ToolInput name="Write" input={{ file_path: "src/app.py", content: "def main():\n    return 1\n" }} />);
  await expect(c.locator(".ch-lang")).toHaveText("python");
  await expect(c.locator("code.language-python .hljs-keyword").first()).toHaveText("def");
  await c.update(<ToolInput name="Write" input={{ file_path: "diagram.mmd", content: "graph TD; A-->B" }} />);
  // An extension highlight.js has no grammar for is shown plain, still as code.
  await expect(c.locator("code.hljs.language-text")).toHaveText("graph TD; A-->B");
});

test("Codex exec: an exec_command call becomes workdir + bash cmd with the JS collapsed", async ({ mount }) => {
  const c = await mount(<ToolInput name="exec" input={'await tools.exec_command({"cmd":"rg -n TODO","workdir":"/w","max_output_tokens":4000})'} />);
  await expect(c.locator('[data-el="T.exec"]')).toHaveCount(1);
  await expect(c.locator('[data-el="V.kvs"]')).toContainText("workdir/w");
  await expect(c.locator('[data-el="V.kvs"]')).toContainText("max_output_tokens4000");
  await expect(c.locator('[data-el="V.bash"] .ch-title')).toHaveText("cmd");
  await expect(c.locator('[data-el="V.bash"]')).toContainText("rg -n TODO");
  await expect(c.locator("code.language-javascript")).toBeHidden();
});

test("Codex exec: a non-strict literal with an escaped quote still yields its cmd", async ({ mount }) => {
  const c = await mount(<ToolInput name="exec" input={'tools.exec_command({ cmd: "echo \\"a\\"", workdir: base + "/x" })'} />);
  await expect(c.locator('[data-el="V.bash"]')).toContainText('echo "a"');
});

test("Codex exec: JavaScript that is not an exec_command shows as highlighted JavaScript", async ({ mount }) => {
  const c = await mount(<ToolInput name="exec" input={"const files = await tools.list_dir({ path: '.' });"} />);
  await expect(c.locator('[data-el="V.code"] .ch-title')).toHaveText("input");
  await expect(c.locator("code.language-javascript .hljs-keyword").first()).toBeVisible();
});

test("Codex exec: an object input shows as JSON", async ({ mount }) => {
  const c = await mount(<ToolInput name="exec" input={{ cmd: "ls" }} />);
  await expect(c.locator('[data-el="V.json"]')).toContainText('"cmd": "ls"');
});

test("an unknown tool falls back visibly: its object as JSON, its string as code", async ({ mount }) => {
  const c = await mount(<ToolInput name="TodoWrite" input={{ todos: [{ content: "draw", status: "pending" }] }} />);
  await expect(c.locator('[data-el="T.fallback"]')).toHaveCount(1);
  await expect(c.locator('[data-el="T.fallback"] > .comp-label')).toHaveCSS("opacity", "1");
  await expect(c.locator('[data-el="V.json"] .ch-title')).toHaveText("input");
  await expect(c.locator('[data-el="V.json"]')).toContainText('"status": "pending"');
  await c.update(<ToolInput name="mcp__x__y" input="free text" />);
  await expect(c.locator('[data-el="V.code"]')).toContainText("free text");
});

test("a missing input is an empty object, not a crash", async ({ mount }) => {
  const c = await mount(<ToolInput name={null} input={null} />);
  await expect(c.locator('[data-el="V.json"]')).toContainText("{}");
});

// Finding: `codexExec` parsed a non-JSON literal with `Function(...)`, i.e. it *ran* whatever
// JavaScript the session log carried between the braces. A log line is agent output (and an
// agent echoes what a repository tells it to), so opening the report executed it in the
// reader's browser. The literal is now read by a parser that never evaluates.
test("Codex exec: a literal that is code, not data, is never executed", async ({ mount, page }) => {
  const input = 'tools.exec_command({ cmd: "ls", workdir: (window.__pwned = 1, "/w") })';
  const c = await mount(<ToolInput name="exec" input={input} />);
  await expect(c.locator('[data-el="T.exec"]')).toContainText("ls");
  expect(await page.evaluate(() => (window as unknown as { __pwned?: number }).__pwned)).toBeUndefined();
});

test("Codex exec: an unquoted-key literal with a trailing comma and single quotes still yields its fields", async ({ mount }) => {
  const input = "tools.exec_command({ cmd: 'rg -n \"a: b\" src', workdir: '/w', yield_time_ms: 1000, })";
  const c = await mount(<ToolInput name="exec" input={input} />);
  const kvs = c.locator('[data-el="T.exec"] > [data-el="V.kvs"]');
  await expect(kvs).toContainText("workdir/w");
  await expect(kvs).toContainText("yield_time_ms1000");
  await expect(c.locator('[data-el="V.bash"] code')).toHaveText('rg -n "a: b" src');
});
