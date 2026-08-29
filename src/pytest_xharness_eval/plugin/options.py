"""The plugin's configuration surface: what it registers, validates and announces.

Every option and every ini key is registered in one :func:`pytest_addoption`, because
``--help`` is the documentation a user actually reads and its order is this file's order
(ADR 0010, ADR 0026, ADR 0030). What each key *means* is
:mod:`~pytest_xharness_eval.runtime.settings`; this module only declares them and hands
pytest the defaults.

:func:`pytest_configure` is where a session becomes able to run cells: markers registered,
the run stamp minted before any xdist worker forks, the price and ignore lines parsed
while a mistake in them is still free, and the one result collector registered by name.
:func:`pytest_report_header` then says out loud where cells will be looked for, since the
commonest confusion is a skills root that does not exist.
"""

from __future__ import annotations

# Third Party
import pytest

# Our Libraries
from pytest_xharness_eval.derive import pricing
from pytest_xharness_eval.derive.ignorerules import IgnoreRules
from pytest_xharness_eval.model import matrix as mx
from pytest_xharness_eval.plugin.cell import run_stamp
from pytest_xharness_eval.plugin.results import RESULTS_KEY, ResultCollector
from pytest_xharness_eval.runtime.settings import (
    INI_CACHE_DIR,
    INI_MATRIX,
    INI_PRICES,
    INI_REPORT_INLINE,
    INI_REPORT_TOKENS,
    INI_SKILL_IGNORE,
    INI_SKILLS_DIR,
    Settings,
)

# The name the result collector is registered under; one per session.
COLLECTOR_NAME = "xharness-eval-results"


def pytest_addoption(parser: pytest.Parser) -> None:
    """Register the matrix-narrowing options and the layout / matrix ini keys."""
    g = parser.getgroup("xharness-eval", "cross-harness agent CLI evals (always live, always paid)")
    g.addoption(
        "--harness",
        action="append",
        default=None,
        choices=list(mx.known_harnesses()),
        help="narrow the matrix to one harness (repeatable)",
    )
    g.addoption(
        "--model",
        action="append",
        default=None,
        metavar="SUBSTRING",
        help="narrow the matrix to models containing this string, or to one exact harness/model cell (repeatable)",
    )
    g.addoption(
        "--dry-run",
        action="store_true",
        dest="eval_dry_run",
        help="enumerate cells and validate pricing without invoking any CLI",
    )
    parser.addini(INI_SKILLS_DIR, default="skills", help="directory under rootdir holding <skill>/evals/ trees")
    parser.addini(
        INI_CACHE_DIR,
        default=".xharness_eval_cache",
        help="git-ignored root under rootdir for build workspaces, results and the report (ADR 0032)",
    )
    parser.addini(
        INI_PRICES,
        type="linelist",
        default=[],
        help=(
            "price rows that add to or override the bundled table: "
            "'<model>: input=<usd/MTok> output=<usd/MTok> [cache_read=..] [cache_write=..] [cache_write_1h=..]'"
        ),
    )
    parser.addini(
        INI_MATRIX,
        type="linelist",
        default=[],
        help="project matrix: harness/model entries, one per line; a case's models= overrides it",
    )
    g.addoption(
        "--xharness-report-design-tokens",
        dest="xharness_report_design_tokens",
        default=None,
        metavar="FILE",
        help="design tokens JSON that themes captured/report.html (overrides the ini key)",
    )
    g.addoption(
        "--xharness-report-inline",
        dest="xharness_report_inline",
        action="store_true",
        default=False,
        help="write captured/report.html with every result, log and the tokens embedded (opens over file://)",
    )
    parser.addini(
        INI_REPORT_TOKENS, default="", help="design tokens JSON for captured/report.html, relative to rootdir"
    )
    parser.addini(INI_REPORT_INLINE, type="bool", default=False, help="embed all data into captured/report.html")
    parser.addini(
        INI_SKILL_IGNORE,
        type="linelist",
        default=[],
        help=(
            "gitignore-style patterns for skill files that are not part of the decision surface; "
            "a bare pattern applies to every skill, '<skill>: <pattern>' to the skills matching the selector"
        ),
    )


def pytest_configure(config: pytest.Config) -> None:
    """Register markers and the per-session result registry, and validate the config lines."""
    config.addinivalue_line("markers", "eval: paid agent eval cell (always live, ADR 0002)")
    # xdist registers this itself when installed; registering again is harmless and keeps
    # --strict-markers happy when it is not.
    config.addinivalue_line("markers", "xdist_group(name): cells of one harness share a worker under --dist loadgroup")
    config.stash[RESULTS_KEY] = {}
    # Minted here, before any xdist worker is forked, so the workers inherit it through the
    # environment and a run's cells share one results/{...}/{run}/ level (ADR 0032).
    run_stamp()
    # ADR 0026 / ADR 0030: a malformed ignore or price line stops the session here,
    # before any cell is collected.
    try:
        IgnoreRules.for_skill("", [str(p) for p in config.getini(INI_SKILL_IGNORE)])
        pricing.parse_price_lines([str(line) for line in config.getini(INI_PRICES)])
    except (ValueError, pricing.PricingError) as exc:
        raise pytest.UsageError(str(exc)) from exc
    config.pluginmanager.register(ResultCollector(config), COLLECTOR_NAME)


def pytest_report_header(config: pytest.Config) -> list[str]:
    """Show where cells are looked for and which matrix scope applies.

    A missing skills root is reported here rather than as a warning: the plugin is
    installed in environments that have no evals at all, and must stay silent there.
    """
    settings = Settings.from_config(config)
    root = settings.skills_root
    state = "" if root.is_dir() else " (missing: no eval cells will be collected)"
    project = settings.matrix_lines
    source = (
        f"{INI_MATRIX} ({len(project)} entries)" if project else f"plugin default ({len(mx.DEFAULT_MATRIX)} entries)"
    )
    return [
        f"xharness-eval: skills root = {root}{state}, cache = {settings.cache.root}",
        f"xharness-eval: matrix = {source}; a case's models= overrides it",
    ]
