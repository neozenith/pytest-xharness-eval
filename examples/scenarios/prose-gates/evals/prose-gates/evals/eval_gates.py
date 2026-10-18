"""prose-gates as a scenario: can an agent clear one gate finding from its message alone?

No skill is invoked. Every harness is sent the same sentence, and every scenario is graded
by the same built-in checkers: the seed still reproduces its rule, scope held, nothing was
hidden in code, the prose survived, and the gate is clean.
"""

from __future__ import annotations

from functools import partial

from _gate import GATE_ARGV, SCRATCH, SEEDS, TASK, TOOL, rules_hit

from pytest_xharness_eval import Analysis, CaseOutput, Promoted, Seed, analyzer, evalcase

from pytest_xharness_eval.model.generators import NO_FINAL_NEWLINE, SHUFFLE_PARAGRAPHS, TRAILING_WHITESPACE, Adversarial
from pytest_xharness_eval.verify import (
    check_all,
    check_content_kept,
    check_files_written,
    check_length_kept,
    check_no_files_added,
    check_nothing_hidden,
    check_rollout,
    check_tool_clean,
    require_seed_fails,
)

TRACKS = [str(TOOL.parent)]


def _seed_reproduces(seed: Seed) -> None:
    """Free, before the paid run: the seed still fails the rule the scenario is about."""
    target, rule = str(seed.params["target"]), str(seed.params["rule"])
    exactly = "mutation" not in seed.params
    require_seed_fails(seed, seed.read(target), [*GATE_ARGV, "--json"], rules={rule}, name=target, exactly=exactly)


def _grade(output: CaseOutput) -> None:
    params = output.params
    target = str(params["target"])
    seed = output.seed(target)
    check_rollout(output)
    check_all(
        output,
        lambda o: check_files_written(o, target),
        partial(check_no_files_added, allow=SCRATCH),
        lambda o: check_nothing_hidden(o, target, seed),
        lambda o: check_content_kept(o, target, seed, at_least=float(params["at_least"])),
        lambda o: check_length_kept(o, target, seed, ratio=(params["ratio"][0], params["ratio"][1])),
        lambda o: check_tool_clean(o, [*GATE_ARGV, "--json", target]),
    )


@evalcase(fixture=SEEDS, tracks=TRACKS, precheck=_seed_reproduces)
def eval_gate(output: CaseOutput) -> None:
    """Each committed rule fixture, as a generated scenario."""
    _grade(output)


ADVERSARY = Adversarial(
    name="prose-gates-adversary",
    seeds=SEEDS,
    mutators=[TRAILING_WHITESPACE, SHUFFLE_PARAGRAPHS, NO_FINAL_NEWLINE],
    budget=3,
    oracle=rules_hit,
)


@evalcase(fixture=ADVERSARY, tracks=TRACKS, precheck=_seed_reproduces)
def eval_gate_adversarial(output: CaseOutput) -> None:
    """Mutants of the rule fixtures, screened by the gate's own rule ids before any is paid for."""
    _grade(output)


REGRESSIONS = Promoted(name="prose-gates-regressions", source=ADVERSARY.name, task=TASK)


@evalcase(fixture=REGRESSIONS, tracks=TRACKS, precheck=_seed_reproduces)
def eval_gate_regressions(output: CaseOutput) -> None:
    """Every adversarial failure promoted into evals/fixtures/: frozen bytes, re-run every sweep."""
    _grade(output)


@analyzer
def analyze_where_it_works(a: Analysis) -> None:
    """The environment as the variable: which tier, harness and model clear the gate, and at what cost."""
    a.note("pass_rate_by_tier", a.tiers("verdict"))
    a.note("pass_rate_by_model", a.summarise("verdict", by=("harness", "model")))
    a.note("cost_per_pass_by_model", a.summarise("cost_per_pass", by=("harness", "model")))
    a.note("turns_by_model", a.summarise("turns", by=("harness", "model")))
    a.note("front", a.pareto())
    a.note("fragile_scenarios", a.fragile())
    a.note("failures_by_model", a.failures(by=("model",)))
    a.expect_at_least("verdict", 0.5, by=("harness",), bound="point")


@analyzer
def analyze_subject_versions(a: Analysis) -> None:
    """The subject as the variable: did the newest version of the tool regress any matched cell?"""
    versions = a.note("versions", list(a.versions()))
    a.note("trend_by_tier", a.trend("verdict", by=("family_tier",)))
    if len(versions) >= 2:
        a.note("comparisons", a.compare("verdict", baseline=versions[-2], candidate=versions[-1]))
        a.expect_no_regression("verdict", baseline=versions[-2], candidate=versions[-1])
