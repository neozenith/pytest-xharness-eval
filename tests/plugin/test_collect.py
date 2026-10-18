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


def test_a_rung_on_a_model_that_ignores_effort_stops_collection(pytester: pytest.Pytester) -> None:
    """Haiku 4.5 accepts --effort and runs at its default, so a rung on it would mislabel a billed run (ADR 0063)."""
    make_tree(pytester, ini="xharness_matrix =\n    claude/claude-haiku-4-5-20251001/high\n")
    result = pytester.runpytest("--collect-only")
    assert result.ret != 0
    result.stdout.fnmatch_lines(["*claude-haiku-4-5-20251001 takes no effort rung*"])


def test_the_same_model_without_a_rung_still_collects(pytester: pytest.Pytester) -> None:
    make_tree(pytester, ini="xharness_matrix =\n    claude/claude-haiku-4-5-20251001\n")
    assert cell_ids(pytester.runpytest("--collect-only", "-q")) == ["claude/claude-haiku-4-5-20251001"]


# -- scenario cases and fixture generators (ADR 0074) ---------------------------

SCENARIO_SUITE = """
from pytest_xharness_eval import evalcase
from pytest_xharness_eval.model.generators import Table
{head}

@evalcase({task}fixture={fixture}{extra})
def eval_lint(output):
    assert output.run.exit_code == 0
"""


TASK = 'task="Clear every lint finding in doc.md", '


def _tool_suite(
    pytester: pytest.Pytester, fixture: str = '"seed"', head: str = "", *, task: str = TASK, extra: str = ""
) -> Path:
    """``skills/lint/evals/eval_lint.py``: a scenario case under a directory that holds no skill at all."""
    make_tree(pytester)
    evals = pytester.path / "skills" / "lint" / "evals"
    (evals / "fixtures" / "seed").mkdir(parents=True)
    (evals / "fixtures" / "seed" / "doc.md").write_text("# bad  \n", encoding="utf-8")
    (evals / "eval_lint.py").write_text(
        SCENARIO_SUITE.format(fixture=fixture, head=head, task=task, extra=extra), encoding="utf-8"
    )
    return evals


ROWS = 'ROWS = Table(name="rows", rows=[{"n": 1}, {"n": 2}], build=lambda r: {"doc.md": "x" * r["n"]}, label="n")'


def test_a_scenario_case_collects_without_a_skill_and_previews_its_task_verbatim(pytester: pytest.Pytester) -> None:
    evals = _tool_suite(pytester)
    assert not (evals.parent / "SKILL.md").exists()
    result = pytester.runpytest(str(evals), "--dry-run", "-v", "-rs")
    result.assert_outcomes(skipped=2)
    result.stdout.fnmatch_lines(
        [
            "*would invoke claude/claude-opus-5 with 'Clear every lint finding in doc.md'*",
            "*would invoke codex/gpt-5.6-sol with 'Clear every lint finding in doc.md'*",
        ]
    )


def test_a_generator_case_collects_one_item_per_scenario_and_cell_and_stores_each(pytester: pytest.Pytester) -> None:
    evals = _tool_suite(pytester, fixture="ROWS", head=ROWS)
    result = pytester.runpytest(str(evals), "--collect-only", "-q")
    nodes = [line.split("::", 1)[1] for line in result.stdout.lines if "::eval_lint[" in line]
    assert len(nodes) == 4
    # Keyed by the suite's whole path, so another subject's eval_lint.py never shares the store.
    store = pytester.path.joinpath(
        ".xharness_eval_cache", "scenarios", "skills", "lint", "evals", "eval_lint", "eval_lint"
    )
    ids = sorted(p.name for p in store.iterdir() if p.is_dir())
    assert [i.split("--")[0] for i in ids] == ["1", "2"]
    assert sorted(nodes) == sorted(
        f"eval_lint[{i}/{c}]" for i in ids for c in ("claude/claude-opus-5", "codex/gpt-5.6-sol")
    )
    for i in ids:
        assert (store / i / "doc.md").is_file() and not (store / i / f"{i}.provenance.json").exists()
        assert json.loads((store / f"{i}.provenance.json").read_text(encoding="utf-8"))["generator"] == "rows"
    pytester.runpytest(str(evals), "--dry-run").assert_outcomes(skipped=4)


@pytest.mark.parametrize(
    ("rows", "build", "message"),
    [
        ("[]", '{"doc.md": "x"}', "yielded no scenarios"),
        ('[{"n": 1}, {"n": 1}]', '{"doc.md": "x"}', "two scenarios share an id"),
        ('[{"n": {1, 2}}]', '{"doc.md": "x"}', "fixture generator rows: TypeError: *params must be JSON-able*"),
        ('[{"n": 1}]', "1 / 0", "fixture generator rows: ZeroDivisionError: *"),
    ],
    ids=["empty", "duplicate", "non-json-params", "raising-build"],
)
def test_a_generator_yielding_nothing_one_id_twice_or_raising_stops_collection_by_name(
    pytester: pytest.Pytester, rows: str, build: str, message: str
) -> None:
    """Whatever a generator raises is the suite's fault: a usage error naming it, never an INTERNALERROR."""
    head = f'ROWS = Table(name="rows", rows={rows}, build=lambda r: {build})'
    result = pytester.runpytest(str(_tool_suite(pytester, fixture="ROWS", head=head)), "--collect-only")
    output = result.stdout.str() + "\n" + result.stderr.str()
    assert result.ret != 0 and "INTERNALERROR" not in output
    pytest.LineMatcher(output.splitlines()).fnmatch_lines([f"*{message}*"])


def test_a_suite_helper_module_beside_it_imports_without_a_conftest(pytester: pytest.Pytester) -> None:
    evals = _tool_suite(pytester, fixture="ROWS", head="from _lint_rows_helper import ROWS")
    (evals / "_lint_rows_helper.py").write_text(f"from pytest_xharness_eval.model.generators import Table\n{ROWS}\n")
    assert not list(pytester.path.rglob("conftest.py"))
    pytester.runpytest(str(evals), "--dry-run").assert_outcomes(skipped=4)


# -- repeats, empty generators, prechecks, scenario tasks (ADR 0074, ADR 0075) ----------


def test_repeat_collects_each_cell_n_times_as_numbered_samples(pytester: pytest.Pytester) -> None:
    make_tree(pytester, ini="xharness_matrix =\n    claude/claude-opus-5\n")
    result = pytester.runpytest("--collect-only", "-q", "--xharness-repeat", "3")
    nodes = [line.split("::", 1)[1] for line in result.stdout.lines if "::eval_demo[" in line]
    assert nodes == [f"eval_demo[claude/claude-opus-5]#{k}" for k in (1, 2, 3)]
    # One run is the default, and its node id carries no sample suffix.
    assert cell_ids(pytester.runpytest("--collect-only", "-q", "--xharness-repeat", "1")) == ["claude/claude-opus-5"]
    pytester.runpytest("--dry-run", "--xharness-repeat", "2").assert_outcomes(skipped=2)


@pytest.mark.parametrize("repeat", ["0", "-1"])
def test_a_repeat_below_one_stops_collection(pytester: pytest.Pytester, repeat: str) -> None:
    """``0`` is not ``1``: a sweep asked for no samples must say so, not run one each."""
    make_tree(pytester)
    result = pytester.runpytest("--collect-only", f"--xharness-repeat={repeat}")
    assert result.ret == pytest.ExitCode.USAGE_ERROR
    result.stderr.fnmatch_lines([f"*--xharness-repeat must be at least 1, got {repeat}*"])


def test_a_regression_case_with_nothing_promoted_warns_and_collects_nothing(pytester: pytest.Pytester) -> None:
    head = (
        "from pytest_xharness_eval.model.generators import Promoted\nREGRESS = Promoted(name='regress', source='rows')"
    )
    evals = _tool_suite(pytester, fixture="REGRESS", head=head)
    result = pytester.runpytest(str(evals), "--collect-only", "-q")
    assert result.ret == pytest.ExitCode.NO_TESTS_COLLECTED
    result.stdout.fnmatch_lines(["*PytestCollectionWarning*eval_lint: regress yielded no scenarios this sweep*"])


GATES = """
def gate(seed):
    assert "bad" in seed.read("doc.md"), "the seed no longer shows the finding"
    assert seed.params["n"] in (1, 2)

def broken(seed):
    assert "never there" in seed.read("doc.md"), "the seed no longer shows the finding"
"""
BAD_ROWS = 'ROWS = Table(name="rows", rows=[{"n": 1}, {"n": 2}], build=lambda r: {"doc.md": "bad" * r["n"]})'


def test_a_passing_precheck_lets_the_dry_run_preview_and_tidies_its_workspace(pytester: pytest.Pytester) -> None:
    evals = _tool_suite(pytester, fixture="ROWS", head=BAD_ROWS + GATES, extra=", precheck=gate")
    pytester.runpytest(str(evals), "--dry-run").assert_outcomes(skipped=4)
    build = pytester.path / ".xharness_eval_cache" / "build"
    assert not build.exists() or not any(build.iterdir())


def test_a_precheck_that_refuses_the_seed_errors_the_cell_even_under_dry_run(pytester: pytest.Pytester) -> None:
    """A fixture that no longer reproduces its rule is found for free, before a sweep pays for it."""
    evals = _tool_suite(pytester, fixture="ROWS", head=BAD_ROWS + GATES, extra=", precheck=broken")
    result = pytester.runpytest(str(evals), "--dry-run")
    result.assert_outcomes(failed=4)
    result.stdout.fnmatch_lines(["*RunError: precheck refused the seed before any run*no longer shows the finding*"])


def test_a_case_with_no_task_sends_each_scenarios_own(pytester: pytest.Pytester) -> None:
    head = 'ROWS = Table(name="rows", rows=[{"t": "a.md"}], build=lambda r: {r["t"]: "x"}, task="Fix {t}")'
    evals = _tool_suite(pytester, fixture="ROWS", head=head, task="")
    result = pytester.runpytest(str(evals), "--dry-run", "-rs", "--harness", "claude")
    result.assert_outcomes(skipped=1)
    result.stdout.fnmatch_lines(["*would invoke claude/claude-opus-5 with 'Fix a.md'*"])


def test_a_case_with_no_task_whose_scenarios_name_none_stops_collection(pytester: pytest.Pytester) -> None:
    head = 'ROWS = Table(name="rows", rows=[{"n": 1}], build=lambda r: {"doc.md": "x"}, label="n")'
    result = pytester.runpytest(str(_tool_suite(pytester, fixture="ROWS", head=head, task="")), "--collect-only")
    assert result.ret != 0
    result.stdout.fnmatch_lines(["*eval_lint: declares no task= and these scenarios name none: ?'1--*"])
