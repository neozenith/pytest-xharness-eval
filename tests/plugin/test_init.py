"""``plugin``: the hook manifest binds exactly its hooks (ADR 0040, ADR 0041)."""

# Standard Library
import tomllib

# Third Party
import pytest

# Our Libraries
from pytest_xharness_eval import plugin


def test_the_plugin_module_binds_every_hook_and_nothing_of_its_own(pytestconfig: pytest.Config) -> None:
    """A fitness function for the manifest: pluggy's surface plus the compatibility names (ADR 0041).

    Pluggy discovers a hook as an attribute of the imported plugin module, so every hook
    implemented in the package has to be bound here or it silently stops firing. Nothing
    else belongs: an internal re-exported from the manifest becomes API by accident.
    """
    hooks = sorted(name for name in plugin.__all__ if name.startswith("pytest_"))
    assert hooks == [
        "pytest_addoption",
        "pytest_collect_file",
        "pytest_configure",
        "pytest_report_header",
        "pytest_report_teststatus",
        "pytest_runtest_makereport",
        "pytest_terminal_summary",
    ]
    # Every hook the package implements is bound, wherever it is implemented.
    implemented = {
        name
        for module in (plugin.collect, plugin.options, plugin.results, plugin.summary)
        for name, obj in vars(module).items()
        if name.startswith("pytest_") and getattr(obj, "__module__", None) == module.__name__
    }
    assert implemented == set(hooks)
    assert all(getattr(plugin, name).__module__.startswith("pytest_xharness_eval.plugin.") for name in hooks)
    # The compatibility surface a consuming repository's conftest.py imports, and no more.
    assert sorted(set(plugin.__all__) - set(hooks)) == [
        "EvalFile",
        "EvalItem",
        "PROPERTY",
        "RECORD_KEY",
        "RESULTS_KEY",
    ]
    assert plugin.EvalItem is plugin.collect.EvalItem and plugin.PROPERTY == "xharness_eval"
    # The pytest11 entry point names this package, and it is the one registration (ADR 0014).
    pyproject = tomllib.loads((pytestconfig.rootpath / "pyproject.toml").read_text(encoding="utf-8"))
    assert pyproject["project"]["entry-points"]["pytest11"] == {"xharness_eval": "pytest_xharness_eval.plugin"}
