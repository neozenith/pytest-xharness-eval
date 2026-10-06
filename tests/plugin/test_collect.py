"""``plugin.collect``: the matrix axes a suite's cells are collected across (ADR 0049, ADR 0055).

Run through ``pytester`` as real nested sessions, like ``tests/test_plugin.py``: collection
is a pytest hook, and nothing short of a session exercises it. Nothing spends -- every
cell here is only collected, or skipped by ``--dry-run``.
"""

# Standard Library
import json
from pathlib import Path

# Third Party
import pytest

# Our Libraries
from tests.support import cell_ids, make_tree

# -- effort: the third matrix axis (ADR 0049) -----------------------------------

EFFORT_INI = (
    "xharness_matrix =\n    claude/claude-opus-5/high\n    claude/claude-opus-5/low\n    codex/gpt-5.6-sol/max\n"
)


def test_a_matrix_entry_sweeps_one_model_at_several_efforts(pytester: pytest.Pytester) -> None:
    """The axis earns its keep here: one model, two rungs, two separately graded cells.

    codex's ``max`` shows as ``xhigh`` because the alias resolved to that harness's own top
    rung at expansion -- the node id names what was sent, not what was typed.
    """
    make_tree(pytester, ini=EFFORT_INI)
    result = pytester.runpytest("--collect-only", "-q")
    assert cell_ids(result) == [
        "claude/claude-opus-5/high",
        "claude/claude-opus-5/low",
        "codex/gpt-5.6-sol/max",
    ]


def test_effort_narrows_the_matrix_by_the_rung_each_alias_resolved_to(pytester: pytest.Pytester) -> None:
    make_tree(pytester, ini=EFFORT_INI)
    assert cell_ids(pytester.runpytest("--collect-only", "-q", "--effort", "low")) == ["claude/claude-opus-5/low"]
    # One flag, both arms: ``max`` is the top rung of whichever ladder the harness has.
    assert cell_ids(pytester.runpytest("--collect-only", "-q", "--effort", "max")) == ["codex/gpt-5.6-sol/max"]


def test_an_effort_rung_the_harness_lacks_aborts_at_collection_before_any_spend(pytester: pytest.Pytester) -> None:
    """ADR 0049 borrows ADR 0007's rule: both CLIs accept a bad rung and bill the run anyway."""
    make_tree(pytester, ini="xharness_matrix =\n    claude/claude-opus-5/minimal\n")
    result = pytester.runpytest("--collect-only")
    assert result.ret != 0
    result.stdout.fnmatch_lines(["*unknown effort 'minimal'*"])


def test_a_cell_with_an_effort_keeps_its_rung_through_the_dry_run_record(pytester: pytest.Pytester) -> None:
    make_tree(pytester, ini=EFFORT_INI)
    result = pytester.runpytest("--dry-run", "-v")
    result.assert_outcomes(skipped=3)
    result.stdout.fnmatch_lines(["*eval_demo?claude/claude-opus-5/high? DRY-RUN*"])
    report = json.loads((pytester.path / ".xharness_eval_cache" / "report" / "report.json").read_text("utf-8"))
    assert sorted((c["model"], c["effort"]) for c in report["cells"]) == [
        ("claude-opus-5", "high"),
        ("claude-opus-5", "low"),
        ("gpt-5.6-sol", "max"),
    ]


# -- treatment: the opt-in fourth axis (ADR 0055) --------------------------------


def make_treatment(evals: Path, name: str, files: dict[str, str] | None = None) -> Path:
    """``evals/treatments/<name>/`` holding ``files`` (an ``AGENTS.md`` by default)."""
    d = evals / "treatments" / name
    d.mkdir(parents=True)
    for rel, body in (files or {"AGENTS.md": "use cheap subagents\n"}).items():
        (d / rel).write_text(body, encoding="utf-8")
    return d


def test_a_treatment_sweeps_every_cell_beside_its_control(pytester: pytest.Pytester) -> None:
    evals = make_tree(pytester, ini="xharness_treatments =\n    lean-ci\n")
    make_treatment(evals, "lean-ci")
    result = pytester.runpytest("--collect-only", "-q")
    assert cell_ids(result) == [
        "claude/claude-opus-5",
        "codex/gpt-5.6-sol",
        "claude/claude-opus-5+lean-ci",
        "codex/gpt-5.6-sol+lean-ci",
    ]


def test_a_case_names_its_own_treatments_over_the_projects(pytester: pytest.Pytester) -> None:
    evals = make_tree(pytester, models=', treatments=["terse"]', ini="xharness_treatments =\n    lean-ci\n")
    make_treatment(evals, "terse")
    assert cell_ids(pytester.runpytest("--collect-only", "-q", "--harness", "codex")) == [
        "codex/gpt-5.6-sol",
        "codex/gpt-5.6-sol+terse",
    ]


def test_treatment_narrows_to_one_arm_and_control_names_the_untreated_one(pytester: pytest.Pytester) -> None:
    evals = make_tree(pytester, ini="xharness_treatments =\n    lean-ci\n")
    make_treatment(evals, "lean-ci")
    assert cell_ids(pytester.runpytest("--collect-only", "-q", "--treatment", "control")) == [
        "claude/claude-opus-5",
        "codex/gpt-5.6-sol",
    ]
    assert cell_ids(pytester.runpytest("--collect-only", "-q", "--treatment", "lean-ci", "--harness", "claude")) == [
        "claude/claude-opus-5+lean-ci"
    ]


def test_a_treatment_with_no_files_for_a_swept_harness_aborts_at_collection(pytester: pytest.Pytester) -> None:
    """A claude-only treatment would bill codex's control twice under two names."""
    evals = make_tree(pytester, ini="xharness_treatments =\n    lean-ci\n")
    make_treatment(evals, "lean-ci__claude", {"CLAUDE.md": "@AGENTS.md\n"})
    result = pytester.runpytest("--collect-only")
    assert result.ret != 0
    result.stdout.fnmatch_lines(["*eval_demo: treatment 'lean-ci' has no files for codex*"])


def test_a_malformed_treatment_line_stops_the_session_before_collection(pytester: pytest.Pytester) -> None:
    make_tree(pytester, ini="xharness_treatments =\n    control\n")
    result = pytester.runpytest("--collect-only")
    assert result.ret == pytest.ExitCode.USAGE_ERROR
    result.stderr.fnmatch_lines(["*treatment 'control' is reserved*"])


def test_a_treated_cell_keeps_its_treatment_through_the_dry_run_record(pytester: pytest.Pytester) -> None:
    evals = make_tree(pytester, ini="xharness_treatments =\n    lean-ci\n")
    make_treatment(evals, "lean-ci")
    result = pytester.runpytest("--dry-run", "-v", "--harness", "claude")
    result.assert_outcomes(skipped=2)
    result.stdout.fnmatch_lines(["*eval_demo?claude/claude-opus-5+lean-ci? DRY-RUN*"])
    result.stdout.fnmatch_lines(["xharness-eval: treatments = xharness_treatments (1 entries)*"])
    report = json.loads((pytester.path / ".xharness_eval_cache" / "report" / "report.json").read_text("utf-8"))
    assert sorted(c["treatment"] for c in report["cells"]) == ["", "lean-ci"]


# -- live pricing: a gap is priced from the feed into <cache>/pricing/ (ADR 0060) -------

NEW_MODEL = "xharness_models =\n    codex/gpt-7-terra: line=terra tier=2 released=2026-10-06\n"


def test_a_catalogued_model_with_no_price_is_priced_live_and_saved_in_the_cache(pytester: pytest.Pytester) -> None:
    source = pytester.path / "feed.json"
    source.write_text(
        json.dumps(
            {
                "gpt-7-terra": {
                    "litellm_provider": "openai",
                    "input_cost_per_token": 2e-06,
                    "output_cost_per_token": 1e-05,
                }
            }
        ),
        encoding="utf-8",
    )
    make_tree(
        pytester,
        models=', models=["codex/gpt-7-terra"]',
        ini=f"{NEW_MODEL}xharness_price_feed = {source}\n",
    )
    pytester.runpytest("--dry-run").assert_outcomes(skipped=1)
    (record,) = (pytester.path / ".xharness_eval_cache" / "pricing").glob("prices-*.toml")
    assert 'codex."gpt-7-terra"' in record.read_text(encoding="utf-8")


def test_a_model_the_feed_does_not_price_either_still_stops_collection(pytester: pytest.Pytester) -> None:
    make_tree(pytester, models=', models=["codex/gpt-7-terra"]', ini=NEW_MODEL)
    result = pytester.runpytest("--dry-run")
    result.assert_outcomes(errors=1)
    result.stdout.fnmatch_lines(["*PricingError*unpriced models in matrix*codex/gpt-7-terra*"])
    assert not (pytester.path / ".xharness_eval_cache" / "pricing").exists()
