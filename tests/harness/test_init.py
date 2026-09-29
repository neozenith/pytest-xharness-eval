"""``harness``: the registry, the extension point, and what every harness renders (ADR 0034)."""

# Standard Library
from collections.abc import Iterator
from pathlib import Path
from typing import Any

# Third Party
import pytest

# Our Libraries
from pytest_xharness_eval import (
    Call,
    Cell,
    RunResult,
    ToolCall,
    Usage,
)
from pytest_xharness_eval import harness as harnesses
from pytest_xharness_eval.derive import skillcov
from pytest_xharness_eval.harness import claude as claude_harness
from pytest_xharness_eval.harness import codex as codex_harness
from pytest_xharness_eval.model import matrix as mx
from pytest_xharness_eval.model.layout import SessionDir
from pytest_xharness_eval.model.registry import Shells
from tests.support import _result, _skill


def test_an_unregistered_harness_fails_loudly_rather_than_defaulting() -> None:
    """The dispatch that used to fall through to Codex now raises (ADR 0034)."""
    with pytest.raises(harnesses.UnknownHarness, match="unknown harness 'gemini'"):
        harnesses.get("gemini")


def test_each_harness_renders_the_rung_in_its_own_dialect() -> None:
    """claude has a first-class flag; codex has only the config mechanism (ADR 0049)."""
    assert claude_harness.effort_argv("high") == ["--effort", "high"]
    assert codex_harness.effort_argv("high") == ["-c", "model_reasoning_effort=high"]
    # No rung asked for means no argument at all, which is what leaves the CLI on its own
    # default -- distinct from naming a rung that happens to be the default.
    assert claude_harness.effort_argv(None) == [] and codex_harness.effort_argv(None) == []


class _ProbeHarness(harnesses.Harness):
    """A third harness that exists only to prove one is reachable without editing anything.

    It deliberately cannot run: ADR 0002 forbids faking a CLI, its subprocess or its
    session log, and nothing here does. ``run`` and ``session_from_capture`` raise, and
    the test asserts they are never reached -- what is exercised is registration and
    dispatch, which is what a new provider actually has to plug into.
    """

    name = "probe"
    shell_tools = frozenset({"Terminal"})
    persistent_shells = frozenset({"Terminal"})

    def invoke(self, *, skill: str, task: str) -> str:
        return f"probe:{skill} {task}"

    def run(self, **kwargs: object) -> RunResult:  # type: ignore[override]
        raise NotImplementedError("the probe harness never invokes anything")

    def session_from_capture(self, session: SessionDir, stored: dict[str, Any]) -> Any:
        raise NotImplementedError("the probe harness has no dialect to replay")

    def classify_record(self, rec: dict[str, Any]) -> str:
        return f"probe/{rec.get('kind') or 'unknown'}"


@pytest.fixture
def probe_harness() -> Iterator[harnesses.Harness]:
    agent = harnesses.register(_ProbeHarness())
    try:
        yield agent
    finally:
        harnesses.unregister(agent.name)


def test_a_third_harness_needs_no_edit_outside_its_own_module(probe_harness: harnesses.Harness) -> None:
    """The operational claim ADR 0034 was made for, asserted rather than argued.

    Registering one class is the whole job: the matrix knows it, its records classify as
    its own, its census counts them, and coverage attribution uses *its* shell vocabulary
    -- with no branch on the name anywhere between here and those call sites.
    """
    assert "probe" in mx.known_harnesses()
    assert mx.expand(["probe/some-model"]) == [Cell(harness="probe", model="some-model")]

    # Classification is the harness's own, not a fall-through to Codex.
    assert probe_harness.classify({"kind": "widget"}) == "probe/widget"
    assert probe_harness.classify("not a record") == "probe/unknown"  # type: ignore[arg-type]
    assert probe_harness.census([{"kind": "widget"}, {"kind": "widget"}, {}]) == {
        "probe/unknown": 1,
        "probe/widget": 2,
    }


def test_coverage_uses_the_new_harnesss_own_shell_vocabulary(tmp_path: Path, probe_harness: harnesses.Harness) -> None:
    """``Terminal`` is a shell for this harness and for no other; nothing had to learn the name."""
    files = skillcov.catalog(_skill(tmp_path))
    r = _result("m", Usage(), harness="probe")
    r.workspace = "/x/ws"
    r.calls = [
        Call(n=1, at="t", tools=[ToolCall("Terminal", "", {"command": "cd /x/skills/demo && cat SKILL.md"})]),
        # The cwd persisted, because this harness says its Terminal is persistent.
        Call(n=2, at="t", tools=[ToolCall("Terminal", "", {"command": "bun run scripts/check.ts"})]),
    ]
    cov = skillcov.annotate("demo", files, r)
    by = {f.path: f for f in cov.files}
    assert by["SKILL.md"].loaded == [1]
    assert by["scripts/check.ts"].run == [2]


def test_coverage_can_be_handed_a_shell_vocabulary_instead_of_looking_one_up(tmp_path: Path) -> None:
    """Annotating a ledger is arithmetic, not a registry call (ADR 0039).

    The same run, under a harness name nothing has registered: handed the vocabulary it
    produces the same answer, and asked to find one it fails loudly rather than guessing.
    """
    files = skillcov.catalog(_skill(tmp_path))
    r = _result("m", Usage(), harness="nowhere")
    r.workspace = "/x/ws"
    r.calls = [
        Call(n=1, at="t", tools=[ToolCall("Terminal", "", {"command": "cd /x/skills/demo && cat SKILL.md"})]),
        Call(n=2, at="t", tools=[ToolCall("Terminal", "", {"command": "bun run scripts/check.ts"})]),
    ]
    shells = Shells(tools=frozenset({"Terminal"}), persistent=frozenset({"Terminal"}))

    cov = skillcov.annotate("demo", files, r, shells)
    by = {f.path: f for f in cov.files}
    assert by["SKILL.md"].loaded == [1]
    assert by["scripts/check.ts"].run == [2]

    with pytest.raises(harnesses.UnknownHarness, match="unknown harness 'nowhere'"):
        skillcov.annotate("demo", files, r)
