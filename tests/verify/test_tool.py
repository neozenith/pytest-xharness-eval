"""``verify.tool``: running the tool under test, and telling its findings from its crashes (ADR 0045)."""

from __future__ import annotations

# Standard Library
import sys
import textwrap
from typing import TYPE_CHECKING

# Third Party
import pytest

# Our Libraries
from pytest_xharness_eval import CaseOutput, Usage, verify
from pytest_xharness_eval.model.output import Seed
from pytest_xharness_eval.model.verdict import Unmeasurable
from pytest_xharness_eval.verify.tool import describe
from tests.support import _result

if TYPE_CHECKING:
    # Standard Library
    from pathlib import Path

#: A tiny lint-style CLI: JSON findings, exit 1 when there are any, and three ways to break.
LINT = textwrap.dedent(
    """\
    import json, os, sys
    from pathlib import Path

    mode, target = sys.argv[1], Path(sys.argv[-1])
    if mode == "crash":
        sys.exit(3)
    if mode == "nojson":
        print("Traceback: boom")
        sys.exit(1)
    if mode == "hang":
        import time
        time.sleep(5)
    text = target.read_text(encoding="utf-8")
    found = [
        {"file": target.name, "line": n, "rule": word, "message": word.lower() + " found"}
        for n, line in enumerate(text.splitlines(), 1)
        for word in ("BAD", "UGLY")
        if word in line
    ]
    if mode == "plain":
        print("\\n".join(f["message"] for f in found) or "ok")
    elif mode == "list":
        print(json.dumps(found))
    else:
        print(json.dumps({"findings": found, "env": os.environ.get("LINT_FLAVOUR", "")}))
    sys.exit(1 if found else 0)
    """
)


@pytest.fixture
def lint(tmp_path: Path) -> list[str]:
    """The command prefix: the interpreter running the lint script, which lives outside the workspace."""
    script = tmp_path / "tools" / "lint.py"
    script.parent.mkdir()
    script.write_text(LINT, encoding="utf-8")
    return [sys.executable, str(script)]


@pytest.fixture
def output(tmp_path: Path) -> CaseOutput:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    (workspace / "good.md").write_text("fine prose\n", encoding="utf-8")
    (workspace / "bad.md").write_text("ok\nBAD line\nUGLY too\n", encoding="utf-8")
    return CaseOutput(run=_result("m", Usage()), workspace=workspace, seeded=frozenset({"good.md", "bad.md"}))


def test_run_tool_runs_in_the_workspace_and_captures_everything(output: CaseOutput, lint: list[str]) -> None:
    run = verify.run_tool(output, [*lint, "json", "good.md"])
    assert run.returncode == 0 and run.json()["findings"] == []
    assert run.command.endswith("json good.md")


def test_env_is_merged_over_the_current_environment(output: CaseOutput, lint: list[str]) -> None:
    run = verify.run_tool(output, [*lint, "json", "good.md"], env={"LINT_FLAVOUR": "strict"})
    assert run.json()["env"] == "strict"


def test_an_exit_outside_ok_codes_is_an_error_not_a_fail(output: CaseOutput, lint: list[str]) -> None:
    """A crashed tool says nothing about the agent, so it must grade ``error``."""
    with pytest.raises(Unmeasurable, match="exited 3"):
        verify.run_tool(output, [*lint, "crash", "good.md"], ok_codes=(0, 1))
    with pytest.raises(Unmeasurable, match="exited 1"):
        verify.run_tool(output, [*lint, "json", "bad.md"])


def test_a_tool_that_cannot_start_or_hangs_is_an_error(output: CaseOutput, lint: list[str]) -> None:
    with pytest.raises(Unmeasurable, match="could not start"):
        verify.run_tool(output, [str(output.workspace / "no-such-binary")])
    with pytest.raises(Unmeasurable, match="was killed"):
        verify.run_tool(output, [*lint, "hang", "good.md"], timeout_s=0.5)


def test_findings_reads_the_named_list_or_the_top_level(output: CaseOutput, lint: list[str]) -> None:
    found = verify.findings(output, [*lint, "json", "bad.md"])
    assert [f["rule"] for f in found] == ["BAD", "UGLY"]
    assert describe(found[0]) == "bad.md:2 BAD bad found"
    assert len(verify.findings(output, [*lint, "list", "bad.md"], json_key=None)) == 2


def test_exit_one_without_json_is_a_crash_not_a_finding(output: CaseOutput, lint: list[str]) -> None:
    """Lint CLIs exit 1 for findings *and* for some crashes; only a report tells them apart."""
    with pytest.raises(Unmeasurable, match="printed no JSON"):
        verify.findings(output, [*lint, "nojson", "bad.md"])
    with pytest.raises(Unmeasurable, match="no findings list"):
        verify.findings(output, [*lint, "json", "bad.md"], json_key="errors")


def test_check_tool_passes_shows_findings_or_the_output_tail(output: CaseOutput, lint: list[str]) -> None:
    verify.check_tool_passes(output, [*lint, "json", "good.md"])
    with pytest.raises(AssertionError, match=r"bad.md:3 UGLY ugly found"):
        verify.check_tool_passes(output, [*lint, "json", "bad.md"])
    with pytest.raises(AssertionError, match="bad found"):
        verify.check_tool_passes(output, [*lint, "plain", "bad.md"])
    with pytest.raises(Unmeasurable, match="exited 3"):
        verify.check_tool_passes(output, [*lint, "crash", "bad.md"])


def test_check_tool_clean_lists_every_remaining_finding(output: CaseOutput, lint: list[str]) -> None:
    verify.check_tool_clean(output, [*lint, "json", "good.md"])
    with pytest.raises(AssertionError, match=r"2 finding\(s\) remain") as failed:
        verify.check_tool_clean(output, [*lint, "json", "bad.md"])
    assert "bad.md:2 BAD" in str(failed.value) and "bad.md:3 UGLY" in str(failed.value)


def test_the_seed_must_still_fail_as_described(output: CaseOutput, lint: list[str], tmp_path: Path) -> None:
    """A fixture that drifted from its rule tests nothing, and that is the host's fault."""
    committed = tmp_path / "fixtures" / "seed.md"
    committed.parent.mkdir()
    committed.write_text("BAD\n", encoding="utf-8")
    verify.require_seed_fails(output, committed, [*lint, "json"], rules=["BAD"])
    verify.require_seed_fails(output, "BAD and UGLY\n", [*lint, "json"], rules=["BAD"], exactly=False)
    with pytest.raises(Unmeasurable, match=r"should fail \['BAD'\] alone; it reports \['BAD', 'UGLY'\]"):
        verify.require_seed_fails(output, "BAD and UGLY\n", [*lint, "json"], rules=["BAD"])
    with pytest.raises(Unmeasurable, match=r"reports \[\]"):
        verify.require_seed_fails(output, "clean\n", [*lint, "json"], rules=["BAD"])


def test_scratch_lives_beside_the_workspace_so_no_file_is_added(output: CaseOutput, lint: list[str]) -> None:
    """A check's scratch file must not read as something the agent added, whatever the order."""
    verify.require_seed_fails(output, "BAD\n", [*lint, "json"], rules=["BAD"], name="nested/seed.md")
    scratch = verify.scratch_dir(output)
    assert scratch.parent == output.workspace.parent and (scratch / "nested" / "seed.md").is_file()
    assert output.filenames == ["bad.md", "good.md"]
    verify.check_no_files_added(output)


def test_tool_run_tail_quotes_both_streams() -> None:
    run = verify.ToolRun(argv=("x",), returncode=1, stdout="a\nb\n", stderr="oops\n")
    assert run.tail(lines=1) == "b\n[stderr]\noops"
    assert verify.ToolRun(argv=("x",), returncode=0, stdout="", stderr="").tail() == "(no output)"


def test_a_precheck_gates_the_seed_it_is_handed_before_any_run(output: CaseOutput, lint: list[str]) -> None:
    """``require_seed_fails`` takes the ``Seed`` a precheck gets, and scratches beside its workspace too."""
    seed = Seed(workspace=output.workspace)
    verify.require_seed_fails(seed, seed.path("bad.md"), [*lint, "json"], rules=["BAD", "UGLY"])
    verify.require_seed_fails(seed, seed.read("bad.md"), [*lint, "json"], rules=["UGLY"], exactly=False)
    assert verify.scratch_dir(seed) == verify.scratch_dir(output)
    assert sorted(p.name for p in output.workspace.iterdir()) == ["bad.md", "good.md"]
    with pytest.raises(RuntimeError) as refused:
        verify.require_seed_fails(seed, seed.path("good.md"), [*lint, "json"], rules=["BAD"])
    # Rules first: a record keeps only the opening characters of the first line.
    assert str(refused.value).startswith("the seed should fail ['BAD'] alone; it reports [] (good.md).")
