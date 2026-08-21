"""pytest plugin entry point (registered via the ``pytest11`` entry point group).

The plugin turns a *harness* — an AI agent runtime such as a CLI coding agent — into
a first-class pytest dimension:

* ``--xharness NAME`` (repeatable) or the ``xharness`` ini list selects which harnesses
  a session evaluates.
* Any test that requests the ``xharness`` fixture is parametrized once per selected
  harness, so a single test body yields one result per harness.
* ``@pytest.mark.xharness("a", "b")`` restricts a test to a subset of harnesses.
"""

from __future__ import annotations

# Standard Library
import dataclasses
import logging

# Third Party
import pytest

log = logging.getLogger(__name__)

OPTION_NAME = "xharness"
MARKER_NAME = "xharness"
FIXTURE_NAME = "xharness"


@dataclasses.dataclass(frozen=True)
class Harness:
    """An AI agent harness under evaluation.

    Attributes:
        name: Stable identifier used in test ids, CLI flags and reports (e.g. ``claude-code``).
    """

    name: str

    def __str__(self) -> str:
        return self.name


def pytest_addoption(parser: pytest.Parser) -> None:
    """Register the ``--xharness`` CLI option and the ``xharness`` ini list."""
    group = parser.getgroup("xharness-eval", "Cross AI agent harness evaluation")
    group.addoption(
        f"--{OPTION_NAME}",
        action="append",
        default=None,
        dest=OPTION_NAME,
        metavar="NAME",
        help="Harness to evaluate (repeatable). Overrides the `xharness` ini list when given.",
    )
    parser.addini(
        OPTION_NAME,
        type="linelist",
        default=[],
        help="Default harnesses to evaluate, one per line.",
    )


def pytest_configure(config: pytest.Config) -> None:
    """Register the ``xharness`` marker so ``--strict-markers`` sessions accept it."""
    config.addinivalue_line(
        "markers",
        f"{MARKER_NAME}(*names): restrict a test to the named harnesses (omit names to run on every selected harness).",
    )


def selected_harnesses(config: pytest.Config) -> list[Harness]:
    """Resolve the harnesses for this session: CLI flags win, then the ini list.

    Args:
        config: The active pytest config.

    Returns:
        Harnesses in declaration order, de-duplicated, blank entries dropped.
    """
    raw: list[str] = config.getoption(OPTION_NAME) or config.getini(OPTION_NAME)
    seen: dict[str, Harness] = {}
    for name in raw:
        cleaned = name.strip()
        if cleaned and cleaned not in seen:
            seen[cleaned] = Harness(cleaned)
    harnesses = list(seen.values())
    log.debug("Selected harnesses: %s", [h.name for h in harnesses])
    return harnesses


def pytest_report_header(config: pytest.Config) -> str:
    """Show which harnesses are in play at the top of the run."""
    names = ", ".join(h.name for h in selected_harnesses(config)) or "(none selected)"
    return f"xharness-eval: harnesses = {names}"


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    """Parametrize every test that requests ``xharness`` once per selected harness.

    A test marked ``@pytest.mark.xharness("a")`` is narrowed to the intersection of
    the session's harnesses and the marker's names. An empty result leaves pytest to
    skip the test with its standard "got empty parameter set" reason.
    """
    if FIXTURE_NAME not in metafunc.fixturenames:
        return
    harnesses = selected_harnesses(metafunc.config)
    marker = metafunc.definition.get_closest_marker(MARKER_NAME)
    if marker is not None and marker.args:
        allowed = set(marker.args)
        harnesses = [h for h in harnesses if h.name in allowed]
    metafunc.parametrize(
        FIXTURE_NAME,
        harnesses,
        ids=[h.name for h in harnesses],
        indirect=True,
    )


@pytest.fixture
def xharness(request: pytest.FixtureRequest) -> Harness:
    """The :class:`Harness` this parametrized test instance evaluates against."""
    harness: Harness = request.param
    return harness
