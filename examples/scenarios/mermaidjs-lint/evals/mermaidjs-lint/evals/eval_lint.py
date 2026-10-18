"""mermaidjs-lint as a scenario: can an agent clear one rule's findings from the messages alone?

The scenarios are generated from the linter's own rule fixtures (``tests/fixtures/rules``):
each file's ``<!-- expect: ... -->`` marker names the rules it reproduces and is stripped
before the agent sees it. The suite this replaces kept a hand-edited copy of each fixture.
"""

from __future__ import annotations

import os
import re
from functools import partial
from pathlib import Path

from pytest_xharness_eval import CaseOutput, Seed, Table, evalcase

from pytest_xharness_eval.verify import (
    check_all,
    check_fences_kept,
    check_files_written,
    check_no_files_added,
    check_rollout,
    check_tool_clean,
    require_seed_fails,
)

#: The mermaidjs-lint checkout under test. Required: an unset variable stops collection by name.
REPO = Path(os.environ["MERMAIDJS_LINT_REPO"])
RULES = REPO / "tests" / "fixtures" / "rules"
LINT = ("bun", "run", str(REPO / "src" / "bin.ts"), "--json", "--profile", "github")
EXPECT = re.compile(r"^<!-- expect: (?P<rules>[^>]*?) -->\n\n?", re.MULTILINE)
CHOSEN = (
    "contrast-edge-label",
    "contrast-border-reported",
    "contrast-sequence-note",
    "contrast-text-unfixable-erd",
    "complexity-nesting",
    "parse-fence-unterminated",
)


def _row(name: str) -> dict[str, object]:
    found = EXPECT.search((RULES / f"{name}.md").read_text(encoding="utf-8"))
    rules = found["rules"].split() if found else []
    return {"fixture": name, "target": "diagram.md", "rules": rules}


def _build(row: object) -> dict[str, str | bytes]:
    text = (RULES / f"{row['fixture']}.md").read_text(encoding="utf-8")  # type: ignore[index]
    return {"diagram.md": EXPECT.sub("", text, count=1)}


TASK = "Make `" + " ".join(LINT[:3]) + " --profile github {target}` exit 0 by editing {target} in place."
SCENARIOS = Table(name="mermaidjs-lint-rules", rows=[_row(n) for n in CHOSEN], build=_build, label="fixture", task=TASK)


def _reproduces(seed: Seed) -> None:
    """Free, before the paid run: the stripped seed still reports every rule its marker named."""
    target = str(seed.params["target"])
    require_seed_fails(seed, seed.read(target), LINT, rules=seed.params["rules"], name=target, exactly=False)


@evalcase(fixture=SCENARIOS, tracks=[str(REPO / "src")], precheck=_reproduces)
def eval_lint(output: CaseOutput) -> None:
    """Scope held, every mermaid fence kept, and the linter is clean on the agent's file."""
    target = str(output.params["target"])
    check_rollout(output)
    check_all(
        output,
        lambda o: check_files_written(o, target),
        partial(check_no_files_added, allow=(".*_cache/*",)),
        lambda o: check_fences_kept(o, target, output.seed(target), lang="mermaid"),
        lambda o: check_tool_clean(o, [*LINT, target]),
    )
