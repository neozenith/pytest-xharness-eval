/** `Bash`: a shell command, highlighted as bash. */
import { expect, test } from "@playwright/experimental-ct-react";
import { Bash } from "../src/components/records/values";

test("highlights builtins, strings and variables", async ({ mount }) => {
  const c = await mount(<Bash cmd={'echo "$HOME" && ls -la'} title="command" />);
  await expect(c.locator('[data-el="V.bash"]')).toHaveCount(1);
  await expect(c.locator("code.language-bash .hljs-built_in").first()).toHaveText("echo");
  await expect(c.locator(".hljs-string")).toContainText("$HOME");
  await expect(c.locator(".hljs-variable")).toHaveText("$HOME");
});

test("a multi-line heredoc keeps its lines", async ({ mount }) => {
  const c = await mount(<Bash cmd={"cat <<'EOF'\nline\nEOF"} />);
  await expect(c.locator("code")).toHaveText("cat <<'EOF'\nline\nEOF");
});
