"""``model.suite``: the one suite loader collection and replay share (ADR 0040)."""

# Standard Library
import logging
import sys
import textwrap
from pathlib import Path

# Third Party
import pytest

# Our Libraries
from pytest_xharness_eval.model import suite as suites
from pytest_xharness_eval.model.suite import EvalSuite

SUITE = textwrap.dedent(
    """
    from pytest_xharness_eval import evalcase

    NOT_A_CASE = "a module-level value the loader must not mistake for one"

    @evalcase(task="{task}", skill="demo", fixture="seed")
    def {name}(output):
        pass
    """
)


def _suite_file(path: Path, *, name: str = "eval_demo", task: str = "go") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(SUITE.format(name=name, task=task), encoding="utf-8")
    return path


def test_a_suite_is_imported_by_path_and_offers_only_its_cases(tmp_path: Path) -> None:
    """Collection and a replay import a suite through this one loader (ADR 0040)."""
    suite = EvalSuite.load(_suite_file(tmp_path / "a" / "evals" / "eval_demo.py", task="alpha"))
    assert [c.name for c in suite.cases] == ["eval_demo"]
    found = suite.case_named("eval_demo")
    assert found is not None and found.task == "alpha"
    assert suite.case_named("eval_absent") is None
    # Registered while it executes, under a name derived from its path, so two skills may
    # both declare an eval_demo.py without the second shadowing the first.
    assert sys.modules[suite.module.__name__] is suite.module
    other = EvalSuite.load(_suite_file(tmp_path / "b" / "evals" / "eval_demo.py", task="beta"))
    assert other.module.__name__ != suite.module.__name__
    assert (other.cases[0].task, suite.cases[0].task) == ("beta", "alpha")


def test_a_file_python_has_no_loader_for_is_an_import_error(tmp_path: Path) -> None:
    path = tmp_path / "eval_demo.notpy"
    path.write_text("X = 1\n", encoding="utf-8")
    with pytest.raises(ImportError, match="cannot load eval module"):
        EvalSuite.load(path)


def test_find_case_searches_the_skills_suites_and_a_broken_one_does_not_stop_it(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """A replay recovers a case by name; one unimportable suite must not lose the others (ADR 0023)."""
    evals = tmp_path / "evals"
    evals.mkdir()
    (evals / "eval_broken.py").write_text("import does_not_exist_anywhere\n", encoding="utf-8")
    _suite_file(evals / "eval_late.py", name="eval_late", task="late")

    with caplog.at_level(logging.WARNING):
        found = suites.find_case(evals, "eval_late")

    assert found is not None
    path, case = found
    assert path.name == "eval_late.py" and case.task == "late"
    assert "could not import eval_broken.py" in caplog.text
    assert suites.find_case(evals, "eval_nobody_declares") is None
