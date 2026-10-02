"""The test suite's own shape: it mirrors the package it tests, and no module outgrows its budget (ADR 0053).

A reader looking for the tests of ``src/pytest_xharness_eval/<layer>/<module>.py`` finds them
at ``tests/<layer>/test_<module>.py`` and nowhere else; a module's ``__init__.py`` is
``test_init.py``. Repository tooling under ``.github/scripts/`` is mirrored by
``tests/scripts/``. The few suites that exercise the whole system rather than one module
live at the top level, each named here with the reason it cannot live beside one module.
"""

from __future__ import annotations

# Standard Library
from pathlib import Path

# Third Party
import pytest

TESTS = Path(__file__).resolve().parent
ROOT = TESTS.parent
PACKAGE = ROOT / "src" / "pytest_xharness_eval"
SCRIPTS = ROOT / ".github" / "scripts"

# The line budget for one test module. A module that outgrows it is testing more than one
# thing, or testing one thing with a repeated block that belongs in a builder or a parametrize.
MAX_LINES = 500

# Top-level suites that exercise the whole system, and why each is not beside one module.
CROSS_CUTTING = {
    "test_plugin.py": "runs the installed plugin end to end in pytester sessions",
    "test_characterization.py": "pins the whole pipeline's output against goldens",
    "test_suite_shape.py": "checks the suite itself",
}
# Modules that hold no tests: package markers, fixtures, and the shared builders.
HELPERS = {"__init__.py", "conftest.py", "support.py", "characterization_fixtures.py"}


def _source_for(test: Path) -> Path | None:
    """The file a test module mirrors, or None when it mirrors nothing."""
    rel = test.relative_to(TESTS)
    name = rel.name.removeprefix("test_")
    name = "__init__.py" if name == "init.py" else name
    if rel.parts[0] == "scripts":
        return SCRIPTS / name
    return PACKAGE.joinpath(*rel.parts[:-1], name)


def _test_modules() -> list[Path]:
    return sorted(p for p in TESTS.rglob("*.py") if "__pycache__" not in p.parts and p.name not in HELPERS)


@pytest.mark.parametrize("test", _test_modules(), ids=lambda p: str(p.relative_to(TESTS)))
def test_each_test_module_mirrors_one_source_module(test: Path) -> None:
    if test.parent == TESTS and test.name in CROSS_CUTTING:
        return
    assert test.name.startswith("test_"), f"{test.name} holds no tests; name it test_* or add it to HELPERS"
    source = _source_for(test)
    assert source is not None and source.is_file(), (
        f"{test.relative_to(TESTS)} mirrors no module (expected {source.relative_to(ROOT) if source else '?'}); "
        "move it beside the module it tests, or name it in CROSS_CUTTING with the reason"
    )


@pytest.mark.parametrize("test", _test_modules(), ids=lambda p: str(p.relative_to(TESTS)))
def test_no_test_module_outgrows_its_budget(test: Path) -> None:
    lines = len(test.read_text(encoding="utf-8").splitlines())
    assert lines <= MAX_LINES, (
        f"{test.relative_to(TESTS)} is {lines} lines (budget {MAX_LINES}); split it along the "
        "structure it tests, or fold its repetition into a builder or a parametrize"
    )


def test_every_test_module_says_what_it_tests() -> None:
    silent = [
        str(p.relative_to(TESTS))
        for p in _test_modules()
        if not p.read_text(encoding="utf-8").lstrip().startswith('"""')
    ]
    assert silent == [], f"test modules without a docstring naming their subject: {silent}"


def test_the_cross_cutting_suites_all_exist() -> None:
    """A name in CROSS_CUTTING must be a real suite, so the exception list cannot outlive its reason."""
    assert sorted(n for n in CROSS_CUTTING if not (TESTS / n).is_file()) == []
