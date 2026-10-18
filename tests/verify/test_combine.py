"""``verify.combine``: many checkers, every failure reported, errors left as errors (ADR 0045)."""

from __future__ import annotations

# Standard Library
from functools import partial
from typing import TYPE_CHECKING

# Third Party
import pytest

# Our Libraries
from pytest_xharness_eval import CaseOutput, Usage, verify
from pytest_xharness_eval.verify.combine import checker_name
from tests.support import _result

if TYPE_CHECKING:
    # Standard Library
    from pathlib import Path


@pytest.fixture
def output(tmp_path: Path) -> CaseOutput:
    (tmp_path / "a.md").write_text("hello\n", encoding="utf-8")
    run = _result("m", Usage(output_tokens=1))
    run.files_written = ["a.md"]
    return CaseOutput(run=run, workspace=tmp_path)


def test_every_failure_is_reported_not_just_the_first(output: CaseOutput) -> None:
    with pytest.raises(AssertionError) as failed:
        verify.check_all(
            output,
            lambda o: verify.check_files_written(o, "b.md"),
            partial(verify.check_turns_within, at_most=5),
            ("goodbye in a.md", lambda o: verify.check_matches(o, "a.md", "goodbye")),
            partial(verify.check_skill_triggered, by="prompt"),
        )
    text = str(failed.value)
    # The first line is what a cell record keeps, so it names the first failure, not a count;
    # a bare lambda has no readable name, so its own message stands without a prefix.
    assert text.splitlines()[0] == "the run did not write ['b.md']; it wrote ['a.md'] (+2 more)"
    assert text.splitlines()[1] == "3 of 4 checks failed:"
    assert "1. the run did not write ['b.md']" in text
    assert "2. [goodbye in a.md] a.md matches 'goodbye' 0 time(s)" in text
    assert "3. [check_skill_triggered(by='prompt')] the skill under test was never triggered" in text
    assert "<lambda>" not in text


def test_all_passing_returns(output: CaseOutput) -> None:
    verify.check_all(
        output, lambda o: verify.check_files_written(o, "a.md"), partial(verify.check_no_files_added, allow=["a.md"])
    )


def test_an_error_propagates_unchanged_and_at_once(output: CaseOutput) -> None:
    """A RuntimeError means the cell could not be graded; folding it into fails would hide that."""
    seen: list[str] = []

    def broken(_: CaseOutput) -> None:
        raise RuntimeError("tool could not start")

    def later(_: CaseOutput) -> None:
        seen.append("ran")

    with pytest.raises(RuntimeError, match="tool could not start"):
        verify.check_all(output, lambda o: verify.check_tools_used(o, "Bash"), broken, later)
    assert seen == []


def test_partials_are_named_with_their_bound_arguments() -> None:
    assert checker_name(partial(verify.check_cost_within, usd=0.5)) == "check_cost_within(usd=0.5)"
    assert checker_name(verify.check_rollout) == "check_rollout"
    assert checker_name(lambda o: None) is None and checker_name(partial(lambda o, n: None, n=1)) is None
    assert checker_name(("label", verify.check_rollout)) == "label"
