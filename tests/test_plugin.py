"""Behavioural tests for the xharness-eval plugin, run through ``pytester``."""

# Standard Library
import textwrap

# Third Party
import pytest

# Our Libraries
from pytest_xharness_eval import Harness, __version__

PARAMETRIZED_TEST = textwrap.dedent(
    """
    def test_per_harness(xharness):
        assert xharness.name
    """
)


def test_version_is_exposed() -> None:
    assert __version__ == "0.1.0"


def test_harness_str_is_its_name() -> None:
    assert str(Harness("claude-code")) == "claude-code"


def test_plugin_registers_cli_option(pytester: pytest.Pytester) -> None:
    result = pytester.runpytest("--help")
    result.stdout.fnmatch_lines(["*--xharness=NAME*"])


def test_marker_is_registered_for_strict_mode(pytester: pytest.Pytester) -> None:
    result = pytester.runpytest("--markers")
    result.stdout.fnmatch_lines(["*@pytest.mark.xharness(*names)*"])


def test_report_header_with_no_harnesses(pytester: pytest.Pytester) -> None:
    pytester.makepyfile("def test_noop(): pass")
    result = pytester.runpytest()
    result.stdout.fnmatch_lines(["xharness-eval: harnesses = (none selected)"])


def test_cli_harnesses_parametrize_fixture(pytester: pytest.Pytester) -> None:
    pytester.makepyfile(PARAMETRIZED_TEST)
    result = pytester.runpytest("-v", "--xharness", "alpha", "--xharness", "beta")
    result.assert_outcomes(passed=2)
    result.stdout.fnmatch_lines(
        [
            "xharness-eval: harnesses = alpha, beta",
            "*test_per_harness?alpha? PASSED*",
            "*test_per_harness?beta? PASSED*",
        ]
    )


def test_ini_harnesses_are_the_default(pytester: pytest.Pytester) -> None:
    pytester.makeini(
        textwrap.dedent(
            """
            [pytest]
            xharness =
                alpha
                beta
                gamma
            """
        )
    )
    pytester.makepyfile(PARAMETRIZED_TEST)
    result = pytester.runpytest()
    result.assert_outcomes(passed=3)


def test_cli_overrides_ini(pytester: pytest.Pytester) -> None:
    pytester.makeini("[pytest]\nxharness =\n    alpha\n    beta\n")
    pytester.makepyfile(PARAMETRIZED_TEST)
    result = pytester.runpytest("-v", "--xharness", "gamma")
    result.assert_outcomes(passed=1)
    result.stdout.fnmatch_lines(["*test_per_harness?gamma? PASSED*"])


def test_duplicate_and_blank_harnesses_are_dropped(pytester: pytest.Pytester) -> None:
    pytester.makepyfile(PARAMETRIZED_TEST)
    result = pytester.runpytest("--xharness", "alpha", "--xharness", " alpha ", "--xharness", "  ")
    result.assert_outcomes(passed=1)


def test_marker_restricts_to_named_harnesses(pytester: pytest.Pytester) -> None:
    pytester.makepyfile(
        textwrap.dedent(
            """
            import pytest

            @pytest.mark.xharness("beta")
            def test_only_beta(xharness):
                assert xharness.name == "beta"

            def test_everywhere(xharness):
                assert xharness.name in {"alpha", "beta"}
            """
        )
    )
    result = pytester.runpytest("--xharness", "alpha", "--xharness", "beta", "--strict-markers")
    result.assert_outcomes(passed=3)


def test_no_selected_harness_skips_parametrized_tests(pytester: pytest.Pytester) -> None:
    pytester.makepyfile(PARAMETRIZED_TEST)
    result = pytester.runpytest()
    result.assert_outcomes(skipped=1)


def test_tests_without_fixture_are_untouched(pytester: pytest.Pytester) -> None:
    pytester.makepyfile("def test_plain(): assert True")
    result = pytester.runpytest("--xharness", "alpha", "--xharness", "beta")
    result.assert_outcomes(passed=1)
