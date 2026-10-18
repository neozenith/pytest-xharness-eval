"""``model.output``: what a grader is handed (``CaseOutput``) and what a precheck is handed (``Seed``)."""

# Standard Library
from dataclasses import replace
from pathlib import Path

# Third Party
import pytest

# Our Libraries
from pytest_xharness_eval import CaseOutput, Usage
from pytest_xharness_eval.model.output import Seed
from pytest_xharness_eval.model.scenario import Scenario, write_tree
from tests.support import _result

SCENARIO = Scenario(
    generator="rows",
    params={"target": "doc.md"},
    expect={"recall": 0.9},
    files={"doc.md": "# seed\n", "blob.bin": "é".encode()},
)


def _workspace(tmp_path: Path) -> Path:
    """The seed as materialised, then edited and extended by a run."""
    return write_tree({"doc.md": "# fixed\n", "new.md": "added\n", "blob.bin": b"\x00"}, tmp_path / "ws")


def _output(tmp_path: Path, scenario: Scenario | None = SCENARIO) -> CaseOutput:
    run = replace(_result("claude-opus-5", Usage(1, 2)), files_written=["doc.md", "new.md"])
    return CaseOutput(
        run=run, workspace=_workspace(tmp_path), seeded=frozenset({"doc.md", "blob.bin"}), scenario=scenario
    )


# -- Seed: the precheck's view, before anything has run --------------------------


def test_a_seed_reads_the_materialised_workspace_and_its_scenarios_merged_params(tmp_path: Path) -> None:
    ws = write_tree({"doc.md": "# seed\n"}, tmp_path / "ws")
    seed = Seed(workspace=ws, scenario=SCENARIO)
    assert seed.path("doc.md") == ws / "doc.md"
    assert seed.read("doc.md") == "# seed\n"
    assert seed.params == {"target": "doc.md", "recall": 0.9}


def test_a_seed_of_a_committed_fixture_has_no_params_and_asking_raises(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="committed fixture"):
        _ = Seed(workspace=tmp_path).params


# -- CaseOutput ------------------------------------------------------------------


def test_params_are_the_scenarios_params_and_expectations_merged(tmp_path: Path) -> None:
    assert _output(tmp_path).params == {"target": "doc.md", "recall": 0.9}


def test_params_of_a_committed_fixture_is_a_grader_bug_and_raises(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="no scenario params"):
        _ = _output(tmp_path, scenario=None).params


def test_seed_is_the_text_the_scenario_wrote_before_the_agent_touched_it(tmp_path: Path) -> None:
    output = _output(tmp_path)
    assert output.read("doc.md") == "# fixed\n"
    assert output.seed("doc.md") == "# seed\n"
    assert output.seed("blob.bin") == "é"  # bytes in the scenario are decoded as UTF-8


def test_seed_of_a_path_the_scenario_did_not_hold_raises_naming_what_it_did(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match=r"new.md was not part of the scenario.*\['blob.bin', 'doc.md'\]"):
        _output(tmp_path).seed("new.md")


def test_seed_of_a_committed_fixture_raises_rather_than_guess(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="answers only for a generated scenario"):
        _output(tmp_path, scenario=None).seed("doc.md")


def test_the_written_added_and_changed_views_split_the_run_diff_by_the_seed_list(tmp_path: Path) -> None:
    output = _output(tmp_path)
    assert (output.written, output.added, output.changed) == (["doc.md", "new.md"], ["new.md"], ["doc.md"])
    assert output.wrote("doc.md") and not output.wrote("blob.bin")
    assert output.exists("blob.bin") and output.filenames == ["blob.bin", "doc.md", "new.md"]


def test_reading_an_absent_file_is_a_failed_check_naming_what_is_there(tmp_path: Path) -> None:
    with pytest.raises(AssertionError, match=r"missing.md is not a file in the workspace"):
        _output(tmp_path).read("missing.md")
