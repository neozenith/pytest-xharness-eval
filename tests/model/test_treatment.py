"""``model.treatment``: naming, locating and validating a treatment's overlay (ADR 0055)."""

# Standard Library
from pathlib import Path

# Third Party
import pytest

# Our Libraries
from pytest_xharness_eval.model import treatment


def _evals(tmp_path: Path, *dirs: str) -> Path:
    """An ``evals/`` dir holding each ``treatments/<dir>/`` with one file in it."""
    evals = tmp_path / "evals"
    for name in dirs:
        d = evals / treatment.TREATMENTS_DIR / name
        d.mkdir(parents=True)
        (d / "AGENTS.md").write_text(name, encoding="utf-8")
    return evals


@pytest.mark.parametrize("name", ["lean-ci", "a", "cheap_eval_subagents", "cheap-subagents-2"])
def test_lowercase_words_joined_by_one_separator_name_a_treatment(name: str) -> None:
    assert treatment.check_name(name) == name


@pytest.mark.parametrize("name", ["Lean", "lean--ci", "lean+ci", "lean__claude", "-lean", "lean_", "", "a/b"])
def test_a_name_that_would_collide_with_a_separator_is_refused(name: str) -> None:
    with pytest.raises(treatment.UnknownTreatment, match="lowercase words"):
        treatment.check_name(name)


def test_control_is_reserved_for_the_untreated_cell() -> None:
    with pytest.raises(treatment.UnknownTreatment, match="reserved"):
        treatment.check_name(treatment.CONTROL)


def test_layers_are_universal_first_then_the_harness_dialect(tmp_path: Path) -> None:
    evals = _evals(tmp_path, "lean", "lean__claude")
    root = evals / treatment.TREATMENTS_DIR
    assert treatment.layers(evals, "lean", "claude") == [root / "lean", root / "lean__claude"]
    assert treatment.layers(evals, "lean", "codex") == [root / "lean"]
    assert treatment.layers(evals, "absent", "codex") == []


def test_a_dialect_only_treatment_is_valid_where_every_swept_harness_has_one(tmp_path: Path) -> None:
    evals = _evals(tmp_path, "lean__claude", "lean__codex")
    treatment.validate(evals, ["lean"], ["claude", "codex"])


def test_a_treatment_that_copies_nothing_onto_a_swept_harness_is_refused(tmp_path: Path) -> None:
    """Otherwise the codex arm would bill its control twice under two names."""
    evals = _evals(tmp_path, "lean__claude")
    treatment.validate(evals, ["lean"], ["claude"])
    with pytest.raises(treatment.UnknownTreatment, match="no files for codex"):
        treatment.validate(evals, ["lean"], ["claude", "codex"])


def test_validation_checks_the_name_before_the_directory(tmp_path: Path) -> None:
    with pytest.raises(treatment.UnknownTreatment, match="reserved"):
        treatment.validate(_evals(tmp_path), [treatment.CONTROL], ["claude"])
