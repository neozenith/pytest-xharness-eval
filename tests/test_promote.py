"""``promote``: freezing a generated scenario into a committed regression fixture (ADR 0074)."""

# Standard Library
import json
from pathlib import Path

# Third Party
import pytest

# Our Libraries
from pytest_xharness_eval import Usage, promote
from pytest_xharness_eval.emit.metrics import CellMetrics, Outcome
from pytest_xharness_eval.model.layout import CacheLayout
from pytest_xharness_eval.model.scenario import PROVENANCE_SUFFIX, Scenario, write_scenario
from pytest_xharness_eval.model.verdict import Verdict
from tests.support import _result

SCENARIO = Scenario(generator="rows", params={"target": "doc.md"}, files={"doc.md": "# bad\n"}, label="doc", task="Fix")
SUITE = "skills/lint/evals/eval_lint.py"


def _stored(cache: CacheLayout) -> Path:
    """The scenario as collection writes it: ``<cache>/scenarios/<suite path>/<case>/<id>/``."""
    return write_scenario(SCENARIO, cache.scenarios(SUITE, "eval_lint"))


def _session(cache: CacheLayout, case: dict[str, object]) -> Path:
    """A real session directory: a ``result.json`` naming its case, and the ``history.json`` its grade wrote."""
    session = cache.session(skill="lint", harness="claude", model="claude-opus-5", run="20261018T000000Z", session="s1")
    session.mkdir()
    result = _result("claude-opus-5", Usage(1, 2))
    result.write(session.result)
    stored = json.loads(session.result.read_text(encoding="utf-8")) | {"case": case}
    session.result.write_text(json.dumps(stored), encoding="utf-8")
    CellMetrics.of(
        result,
        outcome=Outcome(node="n", verdict=Verdict.FAIL, wall_ms=1, started_at="t", failure="doc.md still fails"),
        cache=cache,
    ).write(session.history)
    return session.path


def test_a_stored_scenario_is_promoted_with_its_provenance_beside_not_inside(tmp_path: Path) -> None:
    """Inside the fixture, the provenance would be copied into every later agent's workspace."""
    evals = tmp_path / "lint" / "evals"
    target = promote.promote(_stored(CacheLayout(tmp_path / "cache")), evals)
    assert target == evals / "fixtures" / SCENARIO.id
    assert sorted(p.name for p in target.iterdir()) == ["doc.md"]
    meta = json.loads((evals / "fixtures" / f"{SCENARIO.id}{PROVENANCE_SUFFIX}").read_text(encoding="utf-8"))
    assert meta == SCENARIO.provenance() | {"promoted_from": {}}
    back = Scenario.promoted(target)  # what Promoted(...) reads: the same input, frozen
    assert (back.id, back.fingerprint, back.task) == (SCENARIO.id, SCENARIO.fingerprint, "Fix")


def test_a_failed_session_is_promoted_with_the_facts_of_the_run_that_found_it(tmp_path: Path) -> None:
    cache = CacheLayout(tmp_path / "cache")
    _stored(cache)
    case = {"suite": SUITE, "name": "eval_lint", "kind": "scenario", "scenario": SCENARIO.id}
    session = _session(cache, case)

    target = promote.promote(session, tmp_path / "evals", name="regress-doc")

    assert target == tmp_path / "evals" / "fixtures" / "regress-doc"
    meta = json.loads(target.with_name(f"regress-doc{PROVENANCE_SUFFIX}").read_text(encoding="utf-8"))
    assert meta["id"] == SCENARIO.id and meta["fingerprint"] == SCENARIO.fingerprint
    assert meta["promoted_from"] == {
        "session": str(session),
        "harness": "claude",
        "model": "claude-opus-5",
        "verdict": "fail",
        "failure": "doc.md still fails",
        "case": "eval_lint",
        "suite": SUITE,
    }


def test_a_directory_outside_a_cache_results_tree_is_not_a_session_to_promote(tmp_path: Path) -> None:
    """A ``result.json`` beside a hand-moved copy names no cache, so its scenario store cannot be found."""
    case = {"suite": SUITE, "name": "eval_lint", "scenario": SCENARIO.id}
    moved = tmp_path / "a" / "b" / "c" / "d" / "e" / "copy"
    moved.parent.mkdir(parents=True)
    _session(CacheLayout(tmp_path / "cache"), case).rename(moved)
    with pytest.raises(ValueError, match="not a session directory"):
        promote.promote(moved, tmp_path / "evals")


def test_a_session_on_a_committed_fixture_has_nothing_to_promote(tmp_path: Path) -> None:
    session = _session(CacheLayout(tmp_path / "cache"), {"suite": "s/evals/eval_lint.py", "name": "eval_lint"})
    with pytest.raises(ValueError, match="committed fixture"):
        promote.promote(session, tmp_path / "evals")


def test_a_session_whose_scenario_is_gone_from_the_cache_is_refused(tmp_path: Path) -> None:
    case = {"suite": "s/evals/eval_lint.py", "name": "eval_lint", "scenario": "gone--00000000"}
    session = _session(CacheLayout(tmp_path / "cache"), case)
    with pytest.raises(FileNotFoundError, match="no longer stored"):
        promote.promote(session, tmp_path / "evals")


def test_promotion_never_overwrites_a_committed_fixture(tmp_path: Path) -> None:
    stored = _stored(CacheLayout(tmp_path / "cache"))
    first = promote.promote(stored, tmp_path / "evals")
    (first / "doc.md").write_text("# a maintainer's note\n", encoding="utf-8")
    with pytest.raises(FileExistsError, match="--name"):
        promote.promote(stored, tmp_path / "evals")
    assert (first / "doc.md").read_text(encoding="utf-8") == "# a maintainer's note\n"


def test_main_promotes_what_its_command_line_names(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    stored = _stored(CacheLayout(tmp_path / "cache"))
    assert promote.main([str(stored), str(tmp_path / "evals"), "--name", "kept"]) == 0
    assert capsys.readouterr().out == f"promoted to {tmp_path / 'evals' / 'fixtures' / 'kept'}\n"
    assert (tmp_path / "evals" / "fixtures" / "kept" / "doc.md").is_file()
