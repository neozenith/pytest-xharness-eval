"""An ``eval_*.py`` suite: importing one, and finding the case it declares (ADR 0008, ADR 0040).

A suite is a Python module that belongs to no package -- it lives beside the skill it
grades, in the consuming repository -- so it is imported by path, under a name derived
from that path. Exactly two callers do that: collection, which turns every case in the
file into cells, and a replay, which re-reads the suites of a skill to recover the case a
stored session only names.

They had a loader each, and the two were the same eight lines with one difference nobody
had decided: one registered the module in ``sys.modules`` before executing it and the
other did not. They had a "find the ``EvalCase`` in this module" walk each as well. Both
questions are answered once here, so a change to how a suite is imported cannot apply to
one entry point and not the other -- the drift class ADR 0034 removed for the settings.
"""

from __future__ import annotations

# Standard Library
import hashlib
import importlib.util
import logging
import sys
from dataclasses import dataclass
from typing import TYPE_CHECKING, Self

# Our Libraries
from pytest_xharness_eval.model.case import EvalCase

if TYPE_CHECKING:
    # Standard Library
    from pathlib import Path
    from types import ModuleType

log = logging.getLogger(__name__)

# Suites are imported under a derived name so that two skills may both have an
# ``eval_smoke.py`` without the second shadowing the first.
MODULE_PREFIX = "_xharness_eval"


@dataclass(frozen=True, slots=True)
class EvalSuite:
    """One imported ``eval_*.py`` module, and the cases it declares.

    Constructed only by :meth:`load`: a suite that was never executed has no cases to
    offer, so there is no way to hold one that has not been imported.
    """

    path: Path
    module: ModuleType

    @classmethod
    def load(cls, path: Path) -> Self:
        """Import ``path`` as a standalone module; an import error propagates loudly.

        The module is registered in :data:`sys.modules` under its derived name *before* it
        executes, because a module that is not registered while it runs cannot be found by
        the machinery its own top level may reach for -- ``dataclasses``, ``pickle``,
        ``typing.get_type_hints``. A collection-time ImportError is the point: a suite that
        does not import must fail the session, not collect zero cells (ADR 0008).
        """
        digest = hashlib.sha1(str(path).encode("utf-8")).hexdigest()[:8]
        name = f"{MODULE_PREFIX}_{path.stem}_{digest}"
        spec = importlib.util.spec_from_file_location(name, path)
        if spec is None or spec.loader is None:
            raise ImportError(f"cannot load eval module {path}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        return cls(path, module)

    @property
    def cases(self) -> list[EvalCase]:
        """Every ``@evalcase`` the module declares, in the order it declares them."""
        return [value for value in vars(self.module).values() if isinstance(value, EvalCase)]

    def case_named(self, name: str) -> EvalCase | None:
        """The case whose grader function is called ``name``, or None when it declares no such case."""
        return next((case for case in self.cases if case.name == name), None)


def suites_under(evals_dir: Path) -> list[Path]:
    """Every ``eval_*.py`` under one ``evals/`` directory, in path order."""
    return sorted(evals_dir.glob("eval_*.py"))


def find_case(evals_dir: Path, name: str) -> tuple[Path, EvalCase] | None:
    """The first suite under ``evals_dir`` declaring a case called ``name``, with its path.

    A suite that cannot be imported is logged and skipped rather than raised, because the
    caller is a replay recovering metadata for one session: one broken file must not stop
    the other sessions from being rebuilt (ADR 0023).
    """
    for path in suites_under(evals_dir):
        try:
            suite = EvalSuite.load(path)
        except Exception as exc:  # noqa: BLE001 - a broken suite must not block replaying the others
            log.warning("could not import %s to recover case metadata: %s", path.name, exc)
            continue
        case = suite.case_named(name)
        if case is not None:
            return path, case
    return None
