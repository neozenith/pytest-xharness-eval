"""The free derivations: what a folded run costs, and which of a skill it reached.

Everything here takes a :class:`~pytest_xharness_eval.model.runresult.RunResult` that some
harness has already produced and computes something *about* it. No CLI is invoked, no
money is spent, and -- since ADR 0039 -- no adapter is named: the shell vocabulary a
coverage walk needs arrives as a :class:`~pytest_xharness_eval.model.registry.Shells`
value rather than as a registry lookup taken mid-walk.

* :mod:`.pricing` -- tokens to USD from the bundled dated records plus the project's rows,
  chosen by the run's date, with the rates it applied recorded beside the estimate
  (ADR 0006, ADR 0007, ADR 0030, ADR 0050).
* :mod:`.skillcov` -- which of the skill's files each turn loaded or ran (ADR 0022).
* :mod:`.ignorerules` -- the gitignore-style patterns that say which of those files are
  not decision surface (ADR 0026). String matching, and nothing above it.
"""

from __future__ import annotations

# Our Libraries
from pytest_xharness_eval.derive.ignorerules import IgnoreRules
from pytest_xharness_eval.derive.pricing import (
    AppliedRates,
    CostEstimate,
    Interval,
    LongContext,
    PriceTable,
    PricingError,
    Rates,
    load_table,
    price,
)
from pytest_xharness_eval.derive.skillcov import (
    Access,
    CoverageSummary,
    FileCoverage,
    FileKind,
    SkillCoverage,
    SkillFile,
    annotate,
    catalog,
)

__all__ = [
    "Access",
    "AppliedRates",
    "CostEstimate",
    "LongContext",
    "CoverageSummary",
    "FileCoverage",
    "FileKind",
    "IgnoreRules",
    "Interval",
    "PriceTable",
    "PricingError",
    "Rates",
    "SkillCoverage",
    "SkillFile",
    "annotate",
    "catalog",
    "load_table",
    "price",
]
