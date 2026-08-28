"""Behavioural tests for the plugin, run through ``pytester`` as real nested sessions.

Nothing here invokes an agent CLI. Every path that would spend money is reached
only up to the ``--dry-run`` skip; the live path is exercised by paid evals in a
consuming repository (ADR 0002).
"""

# Standard Library
import json
import textwrap
from pathlib import Path

# Third Party
import pytest

CASE = textwrap.dedent(
    """
    from pytest_xharness_eval import evalcase

    @evalcase(prompt="say hi", skill="demo", fixture="seed"{models})
    def eval_demo(run, workspace):
        assert run.exit_code == 0
    """
)


def make_tree(pytester: pytest.Pytester, *, models: str = "", skills_dir: str = "skills", ini: str = "") -> Path:
    """Lay out ``<skills_dir>/demo/evals/eval_demo.py`` with ``fixtures/seed/`` and return the evals dir."""
    pytester.makeini(f"[pytest]\n{ini}\n")
    skill = pytester.path / skills_dir / "demo"
    (skill / "evals" / "fixtures" / "seed").mkdir(parents=True)
    (skill / "SKILL.md").write_text("# demo skill\n", encoding="utf-8")
    (skill / "evals" / "fixtures" / "seed" / "README.md").write_text("seed\n", encoding="utf-8")
    (skill / "evals" / "eval_demo.py").write_text(CASE.format(models=models), encoding="utf-8")
    return skill / "evals"


def cell_ids(result: pytest.RunResult) -> list[str]:
    """The ``harness/model`` part of every collected eval node id, in order."""
    return [line.split("[", 1)[1].rstrip("]") for line in result.stdout.lines if "::eval_demo[" in line]


# -- options and headers -------------------------------------------------------


def test_help_lists_options_and_ini_keys(pytester: pytest.Pytester) -> None:
    result = pytester.runpytest("--help")
    result.stdout.fnmatch_lines(["*--harness=*", "*--model=SUBSTRING*", "*--dry-run*"])
    result.stdout.fnmatch_lines(
        ["*xharness_skills_dir*", "*xharness_cache_dir*", "*xharness_prices*", "*xharness_matrix*"]
    )
    result.stdout.fnmatch_lines(["*--xharness-report-design-tokens=FILE*", "*--xharness-report-inline*"])
    # Ini keys print in registration order: the report keys are registered before the ignore key.
    result.stdout.fnmatch_lines(
        ["*xharness_report_design_tokens*", "*xharness_report_inline*", "*xharness_skill_ignore*"]
    )


def test_a_malformed_skill_ignore_line_stops_the_session_before_collection(pytester: pytest.Pytester) -> None:
    """ADR 0026: '<skill>:' with nothing after it ignores nothing and is a typo, not a no-op."""
    make_tree(pytester, ini="xharness_skill_ignore =\n    README.md\n    demo:\n")
    result = pytester.runpytest("--collect-only")
    assert result.ret == pytest.ExitCode.USAGE_ERROR
    result.stderr.fnmatch_lines(["*xharness_skill_ignore: expected '<skill>: <pattern>' or '<pattern>', got 'demo:'*"])


def test_skill_ignore_lines_scope_by_skill_name(pytester: pytest.Pytester) -> None:
    """A bare line applies to every skill; a '<skill>: <pattern>' line only to the skills it names."""
    evals = make_tree(pytester, ini="xharness_skill_ignore =\n    assets/\n    demo: README.md\n    other: SKILL.md\n")
    skill = evals.parent
    (skill / "assets").mkdir()
    (skill / "assets" / "icon.png").write_bytes(b"png")
    (skill / "README.md").write_text("readme\n", encoding="utf-8")
    pytester.makeconftest(
        "import pytest\n"
        "from pytest_xharness_eval.plugin import EvalItem\n\n"
        "def pytest_collection_modifyitems(items):\n"
        "    for item in items:\n"
        "        if isinstance(item, EvalItem):\n"
        "            for f in item.skill_files:\n"
        "                print('FILE', f.path, f.ignored)\n"
    )
    result = pytester.runpytest("--collect-only", "-s")
    result.stdout.fnmatch_lines(["FILE SKILL.md False", "FILE assets/icon.png True", "FILE README.md True"])


def test_header_names_the_skills_root_and_matrix_source(pytester: pytest.Pytester) -> None:
    make_tree(pytester)
    result = pytester.runpytest("--collect-only")
    result.stdout.fnmatch_lines(
        [
            "xharness-eval: skills root = *skills, cache = *.xharness_eval_cache",
            "xharness-eval: matrix = plugin default (2 entries)*",
        ]
    )


def test_missing_skills_root_is_named_in_the_header_without_warning(pytester: pytest.Pytester) -> None:
    pytester.makeini("[pytest]\n")
    pytester.makepyfile(test_plain="def test_plain(): pass")
    result = pytester.runpytest()
    result.assert_outcomes(passed=1, warnings=0)
    result.stdout.fnmatch_lines(["xharness-eval: skills root = *skills (missing: no eval cells will be collected)*"])


# -- matrix scopes: case > project ini > plugin default (ADR 0015) ---------------


def test_plugin_default_matrix_when_nothing_else_is_set(pytester: pytest.Pytester) -> None:
    make_tree(pytester)
    result = pytester.runpytest("--collect-only", "-q")
    assert cell_ids(result) == ["claude/claude-opus-5", "codex/gpt-5.6-sol"]


def test_project_matrix_ini_replaces_the_plugin_default(pytester: pytest.Pytester) -> None:
    make_tree(pytester, ini="xharness_matrix =\n    claude/claude-sonnet-5\n    codex/gpt-5.6-luna\n")
    result = pytester.runpytest("--dry-run")
    result.assert_outcomes(skipped=2)
    assert cell_ids(result) == ["claude/claude-sonnet-5", "codex/gpt-5.6-luna"]
    result.stdout.fnmatch_lines(["xharness-eval: matrix = xharness_matrix (2 entries)*"])


def test_case_models_override_the_project_matrix(pytester: pytest.Pytester) -> None:
    make_tree(pytester, models=', models=["claude/claude-sonnet-5"]', ini="xharness_matrix =\n    codex/gpt-5.6-luna\n")
    result = pytester.runpytest("--collect-only", "-q")
    assert cell_ids(result) == ["claude/claude-sonnet-5"]


# -- narrowing -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("flags", "expected_ids"),
    [
        (["--harness", "codex"], ["codex/gpt-5.6-sol"]),
        (["--model", "opus"], ["claude/claude-opus-5"]),
        (["--model", "codex/gpt-5.6-sol"], ["codex/gpt-5.6-sol"]),
        (["--harness", "claude", "--model", "gpt"], []),
        (["-k", "opus or sol"], ["claude/claude-opus-5", "codex/gpt-5.6-sol"]),
        (["-k", "codex and not sol"], []),
    ],
)
def test_harness_model_and_k_flags_narrow_the_matrix(
    pytester: pytest.Pytester, flags: list[str], expected_ids: list[str]
) -> None:
    make_tree(pytester)
    result = pytester.runpytest("--collect-only", "-q", *flags)
    assert cell_ids(result) == expected_ids


def test_unknown_harness_is_rejected_by_argparse(pytester: pytest.Pytester) -> None:
    make_tree(pytester)
    result = pytester.runpytest("--harness", "gemini")
    assert result.ret != 0
    result.stderr.fnmatch_lines(["*--harness: invalid choice: 'gemini'*"])


# -- visibility: verbose status words and the report -----------------------------


def test_verbose_dry_run_shows_dry_run_per_cell(pytester: pytest.Pytester) -> None:
    make_tree(pytester)
    result = pytester.runpytest("--dry-run", "-v")
    result.assert_outcomes(skipped=2)
    result.stdout.fnmatch_lines(
        [
            "*eval_demo?claude/claude-opus-5? DRY-RUN*",
            "*eval_demo?codex/gpt-5.6-sol? DRY-RUN*",
        ]
    )


def test_dry_run_writes_report_and_summary(pytester: pytest.Pytester) -> None:
    make_tree(pytester)
    result = pytester.runpytest("--dry-run")
    result.assert_outcomes(skipped=2)
    result.stdout.fnmatch_lines(
        [
            "*agent eval report*",
            # fnmatch treats [...] as a character class, hence ? for the brackets.
            "*dry-run * -  skills/demo/evals/eval_demo.py::eval_demo?claude/claude-opus-5?",
            "*dry-run * -  skills/demo/evals/eval_demo.py::eval_demo?codex/gpt-5.6-sol?",
            "*total estimated spend: $0.0000 across 2 cell(s)",
        ]
    )
    report = json.loads((pytester.path / ".xharness_eval_cache" / "report" / "report.json").read_text(encoding="utf-8"))
    # report.json is two keys and has always been two keys: a frozen wire format (ADR 0037).
    assert sorted(report) == ["cells", "total_usd"]
    assert report["total_usd"] == 0
    assert [c["verdict"] for c in report["cells"]] == ["dry-run", "dry-run"]
    assert {c["harness"] for c in report["cells"]} == {"claude", "codex"}
    # A dry-run cell is the same record as a live one, not a shape of its own: the whole
    # metrics vocabulary is present, unmeasured (tests/test_units.py pins the key set).
    assert all(c["accumulative_billed_tokens"] == 0 and c["estimated_cost_usd"] is None for c in report["cells"])


def test_dry_run_writes_no_results(pytester: pytest.Pytester) -> None:
    evals = make_tree(pytester)
    pytester.runpytest("--dry-run").assert_outcomes(skipped=2)
    # No evidence and no aggregated page for a run that invoked nothing (ADR 0032);
    # only report.json (the run summary) is written. Nothing lands in the skills tree.
    cache = pytester.path / ".xharness_eval_cache"
    assert not (cache / "results").exists()
    assert not (cache / "report" / "report.html").exists()
    assert not (evals / "captured").exists()


def test_no_report_when_every_cell_is_deselected(pytester: pytest.Pytester) -> None:
    make_tree(pytester)
    pytester.makepyfile(test_plain="def test_plain(): pass")
    result = pytester.runpytest("-m", "not eval")
    result.assert_outcomes(passed=1, deselected=2)
    assert "agent eval report" not in result.stdout.str()


def test_junitxml_carries_the_cell_record(pytester: pytest.Pytester) -> None:
    make_tree(pytester)
    result = pytester.runpytest("--dry-run", "--junitxml=junit.xml")
    result.assert_outcomes(skipped=2)
    xml = (pytester.path / "junit.xml").read_text(encoding="utf-8")
    assert 'name="xharness_harness" value="claude"' in xml
    assert 'name="xharness_verdict" value="dry-run"' in xml


# -- xdist: records travel on the report, cells group by harness (ADR 0016) -------


def test_xdist_keeps_status_words_and_report(pytester: pytest.Pytester) -> None:
    make_tree(pytester)
    result = pytester.runpytest("--dry-run", "-v", "-n", "2")
    result.assert_outcomes(skipped=2)
    # xdist puts the status word before the node id: "[gw0] [ 50%] DRY-RUN skills/...".
    out = result.stdout.str()
    assert "DRY-RUN skills/demo/evals/eval_demo.py::eval_demo[claude/claude-opus-5]" in out
    assert "DRY-RUN skills/demo/evals/eval_demo.py::eval_demo[codex/gpt-5.6-sol]" in out
    result.stdout.fnmatch_lines(["*total estimated spend: $0.0000 across 2 cell(s)"])


def test_xdist_loadgroup_puts_each_harness_on_one_worker(pytester: pytest.Pytester) -> None:
    make_tree(
        pytester, ini="xharness_matrix =\n    claude/claude-opus-5\n    claude/claude-sonnet-5\n    codex/gpt-5.6-sol\n"
    )
    result = pytester.runpytest("--dry-run", "-v", "-n", "2", "--dist", "loadgroup")
    result.assert_outcomes(skipped=3)
    # xdist prints the worker id in front of each verbose line: "[gw0] ... DRY-RUN".
    workers: dict[str, set[str]] = {}
    for line in result.stdout.lines:
        if "::eval_demo[" in line and "DRY-RUN" in line:
            harness = line.split("::eval_demo[")[1].split("/")[0]
            workers.setdefault(harness, set()).add(line.split("]")[0].lstrip("["))
    assert all(len(ws) == 1 for ws in workers.values()), workers
    assert set(workers) == {"claude", "codex"}


def test_cells_carry_an_xdist_group_marker_named_for_the_harness(pytester: pytest.Pytester) -> None:
    make_tree(pytester)
    result = pytester.runpytest("--strict-markers", "-m", "xdist_group", "--dry-run")
    result.assert_outcomes(skipped=2)


# -- failure modes that must stay loud -----------------------------------------


def test_evalcase_function_without_eval_prefix_is_a_usage_error(pytester: pytest.Pytester) -> None:
    evals = make_tree(pytester)
    (evals / "eval_demo.py").write_text(CASE.format(models="").replace("def eval_demo(", "def check_demo("), "utf-8")
    result = pytester.runpytest("--dry-run")
    assert result.ret != 0
    out = result.stdout.str() + result.stderr.str()
    assert "@evalcase functions must be named eval_*, got ['check_demo']" in out


def test_unpriced_model_aborts_at_collection_before_any_spend(pytester: pytest.Pytester) -> None:
    make_tree(pytester, models=', models=["claude/claude-unknown-99"]')
    result = pytester.runpytest("--dry-run")
    result.assert_outcomes(errors=1)
    result.stdout.fnmatch_lines(["*PricingError*unpriced models in matrix*claude/claude-unknown-99*"])


def test_price_lines_in_the_ini_add_rows_to_the_bundled_table(pytester: pytest.Pytester) -> None:
    make_tree(
        pytester,
        models=', models=["codex/gpt-house-blend"]',
        ini="xharness_prices =\n    gpt-house-blend: input=1.00 output=2.00\n",
    )
    result = pytester.runpytest("--dry-run")
    result.assert_outcomes(skipped=1)


def test_a_malformed_price_line_stops_the_session_before_collection(pytester: pytest.Pytester) -> None:
    """ADR 0030: a per-token value pasted from the bundled table must not under-price by 1e6."""
    make_tree(pytester, ini="xharness_prices =\n    gpt-house-blend: input=1.0e-6 output=2.0e-6\n")
    result = pytester.runpytest("--collect-only")
    assert result.ret == pytest.ExitCode.USAGE_ERROR
    result.stderr.fnmatch_lines(["*looks like a per-token rate*USD per million tokens*"])


def test_module_without_evalcase_is_a_usage_error(pytester: pytest.Pytester) -> None:
    evals = make_tree(pytester)
    (evals / "eval_demo.py").write_text("X = 1\n", encoding="utf-8")
    result = pytester.runpytest("--dry-run")
    assert result.ret != 0
    assert "eval_demo.py matched the evals layout but defines no @evalcase" in result.stdout.str() + result.stderr.str()


def test_import_error_in_case_module_fails_collection(pytester: pytest.Pytester) -> None:
    evals = make_tree(pytester)
    (evals / "eval_demo.py").write_text("import does_not_exist_anywhere\n", encoding="utf-8")
    result = pytester.runpytest("--dry-run")
    result.assert_outcomes(errors=1)
    result.stdout.fnmatch_lines(["*ModuleNotFoundError*does_not_exist_anywhere*"])


def test_missing_skill_directory_fails_even_in_dry_run(pytester: pytest.Pytester) -> None:
    evals = make_tree(pytester)
    (evals / "eval_demo.py").write_text(CASE.format(models="").replace('skill="demo"', 'skill="ghost"'), "utf-8")
    result = pytester.runpytest("--dry-run")
    result.assert_outcomes(failed=2)
    result.stdout.fnmatch_lines(["*RunError*skill under test not found*ghost*"])


def test_missing_fixture_fails_even_in_dry_run(pytester: pytest.Pytester) -> None:
    evals = make_tree(pytester)
    (evals / "eval_demo.py").write_text(CASE.format(models="").replace('fixture="seed"', 'fixture="nope"'), "utf-8")
    result = pytester.runpytest("--dry-run", "--harness", "claude")
    result.assert_outcomes(failed=1)
    result.stdout.fnmatch_lines(["*RunError*fixture directory not found*fixtures/nope*"])


# -- layout rules ----------------------------------------------------------------


def test_eval_modules_outside_the_skills_root_are_ignored(pytester: pytest.Pytester) -> None:
    make_tree(pytester)
    stray = pytester.path / "elsewhere" / "demo" / "evals"
    stray.mkdir(parents=True)
    (stray / "eval_stray.py").write_text("raise RuntimeError('must never be imported')\n", encoding="utf-8")
    result = pytester.runpytest("--collect-only", "-q")
    assert "eval_stray" not in result.stdout.str()
    assert cell_ids(result) == ["claude/claude-opus-5", "codex/gpt-5.6-sol"]


def test_custom_skills_dir_ini(pytester: pytest.Pytester) -> None:
    make_tree(pytester, skills_dir="agent_skills", ini="xharness_skills_dir = agent_skills")
    result = pytester.runpytest("--collect-only", "-q")
    result.stdout.fnmatch_lines(["agent_skills/demo/evals/eval_demo.py::eval_demo[claude/claude-opus-5]"])


def test_custom_cache_dir_ini_relocates_the_report(pytester: pytest.Pytester) -> None:
    make_tree(pytester, ini="xharness_cache_dir = build/eval-cache")
    result = pytester.runpytest("--dry-run")
    result.assert_outcomes(skipped=2)
    assert (pytester.path / "build" / "eval-cache" / "report" / "report.json").is_file()


def test_cells_carry_the_eval_marker(pytester: pytest.Pytester) -> None:
    make_tree(pytester)
    pytester.makepyfile(test_plain="def test_plain(): pass")
    selected = pytester.runpytest("--strict-markers", "-m", "eval", "--dry-run")
    selected.assert_outcomes(skipped=2, deselected=1)
    deselected = pytester.runpytest("--strict-markers", "-m", "not eval", "--dry-run")
    deselected.assert_outcomes(passed=1, deselected=2)


def test_xdist_loadgroup_suffix_is_stripped_from_recorded_node_ids(pytester: pytest.Pytester) -> None:
    make_tree(pytester)
    result = pytester.runpytest("--dry-run", "-n", "2", "--dist", "loadgroup")
    result.assert_outcomes(skipped=2)
    report = json.loads((pytester.path / ".xharness_eval_cache" / "report" / "report.json").read_text(encoding="utf-8"))
    assert all(not c["node"].endswith(("@claude", "@codex")) for c in report["cells"]), report
