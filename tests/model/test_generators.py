"""``model.generators``: the fixture generators that ship, and the adversary's search (ADR 0074)."""

# Standard Library
from collections import Counter
from pathlib import Path
from typing import Any

# Third Party
import pytest

# Our Libraries
from pytest_xharness_eval.model import generators as gen
from pytest_xharness_eval.model.scenario import (
    Draw,
    Files,
    GenerationContext,
    Scenario,
    ScenarioStore,
    write_scenario,
    write_tree,
)


def _context(tmp_path: Path, **fields: Any) -> GenerationContext:
    return GenerationContext(evals_dir=tmp_path / "evals", case="eval_x", **fields)


def _doc(row: Any) -> Files:
    return {str(row["target"]): f"# {row['target']}\n\nbody\n"}


SEEDS = gen.Table(name="seeds", rows=[{"target": "a.md"}, {"target": "b.md"}], build=_doc, label="target")


def append_noise(files: Files, draw: Draw) -> Files:
    """A mutator whose every application is distinct: what a test of the search's bookkeeping wants."""
    return {p: f"{c}{draw.integer(0, 10**9)}\n" for p, c in files.items()}


def add_a(files: Files, draw: Draw) -> Files:
    return {p: f"{c}A" for p, c in files.items()}


def add_b(files: Files, draw: Draw) -> Files:
    return {p: f"{c}B" for p, c in files.items()}


def _adversary(**overrides: Any) -> gen.Adversarial:
    fields: dict[str, Any] = {"name": "adv", "seeds": SEEDS, "mutators": [append_noise], "budget": 6}
    return gen.Adversarial(**(fields | overrides))


def _parent(mutant: Scenario) -> str:
    """The seed id a mutant records under its ``mutation`` param."""
    return str(mutant.params[gen.MUTATION_KEY]["parent"])


def _swept(tmp_path: Path, scenarios: list[Scenario], outcome: tuple[int, int]) -> dict[str, tuple[int, int]]:
    """Store each scenario as collection would, and give every one the same ``(failed, sampled)``."""
    for s in scenarios:
        write_scenario(s, tmp_path / "store")
    return {s.id: outcome for s in scenarios}


# -- Table, Generated, from_dir ----------------------------------------------------


def test_a_table_yields_one_scenario_per_row_labelled_and_tasked_from_it(tmp_path: Path) -> None:
    table = gen.Table(name="t", rows=[{"target": "a.md", "n": 1}], build=_doc, label="target", task="Fix {target}")
    (s,) = table.scenarios(_context(tmp_path))
    assert (s.generator, s.label, s.task, dict(s.params)) == ("t", "a.md", "Fix a.md", {"target": "a.md", "n": 1})
    assert s.id.startswith("a-md--") and s.files == {"a.md": "# a.md\n\nbody\n"}
    (plain,) = gen.Table(name="t", rows=[{"target": "a.md"}], build=_doc).scenarios(_context(tmp_path))
    assert (plain.label, plain.task) == (None, None)


def test_a_tables_expect_keys_reach_the_grader_but_not_the_id(tmp_path: Path) -> None:
    """Tuning a tolerance keeps the scenario's history in one piece."""

    def one(recall: float) -> Scenario:
        rows = [{"target": "a.md", "recall": recall}]
        return next(iter(gen.Table(name="t", rows=rows, build=_doc, expect=["recall"]).scenarios(_context(tmp_path))))

    loose, strict = one(0.5), one(0.9)
    assert (dict(strict.params), dict(strict.expect)) == ({"target": "a.md"}, {"recall": 0.9})
    assert strict.merged == {"target": "a.md", "recall": 0.9}
    assert loose.id == strict.id
    with pytest.raises(KeyError, match="lacks the expectation keys"):
        list(
            gen.Table(name="t", rows=[{"target": "a.md"}], build=_doc, expect=["recall"]).scenarios(_context(tmp_path))
        )


def _drawn(draw: Draw) -> tuple[dict[str, Any], Files]:
    n = draw.integer(1, 10**6)
    return {"n": n}, {"f.md": f"{n}\n"}


def test_generated_draws_the_same_scenarios_every_time_and_others_for_another_seed(tmp_path: Path) -> None:
    def ids(seed: int) -> list[str]:
        return [s.id for s in gen.Generated(name="g", build=_drawn, count=4, seed=seed).scenarios(_context(tmp_path))]

    assert ids(0) == ids(0) and len(set(ids(0))) == 4
    assert ids(0) != ids(1)
    first = next(iter(gen.Generated(name="g", build=_drawn, count=1, task="n={n}").scenarios(_context(tmp_path))))
    assert first.label == "g-0" and first.task == f"n={first.params['n']}"


def test_generated_takes_its_label_from_the_drawn_params_when_one_is_there(tmp_path: Path) -> None:
    (s,) = gen.Generated(name="g", build=lambda d: ({"label": "Named"}, {"f.md": "x"}), count=1).scenarios(
        _context(tmp_path)
    )
    assert s.id.startswith("named--")


def test_from_dir_yields_one_transformed_scenario_per_subdirectory(tmp_path: Path) -> None:
    root = tmp_path / "rules"
    write_tree({"MD001/doc.md": "<!-- expect: MD001 -->\nbad\n"}, root / "md001")
    write_tree({"doc.md": "<!-- expect: MD009 -->\nworse\n"}, root / "md009")
    table = gen.from_dir("rules", root, transform=lambda path, text: text.split("\n", 1)[1])
    scenarios = list(table.scenarios(_context(tmp_path)))
    assert [s.label for s in scenarios] == ["md001", "md009"]
    assert scenarios[0].files == {"MD001/doc.md": "bad\n"} and scenarios[1].files == {"doc.md": "worse\n"}
    untouched = next(iter(gen.from_dir("rules", root).scenarios(_context(tmp_path))))
    assert untouched.files == {"MD001/doc.md": "<!-- expect: MD001 -->\nbad\n"}
    (tmp_path / "empty").mkdir()
    with pytest.raises(FileNotFoundError, match="no subdirectories"):
        gen.from_dir("x", tmp_path / "empty")


# -- Promoted ----------------------------------------------------------------------


def test_promoted_reads_every_frozen_fixture_or_only_one_generators(tmp_path: Path) -> None:
    fixtures = tmp_path / "evals" / "fixtures"
    a = write_scenario(Scenario(generator="a", params={"i": 1}, files={"x.md": "1"}), fixtures)
    b = write_scenario(Scenario(generator="b", params={"i": 2}, files={"x.md": "2"}), fixtures)
    (fixtures / "hand-written").mkdir()  # a committed fixture without provenance is not a promoted one
    every = gen.Promoted(name="p").scenarios(_context(tmp_path))
    assert sorted(s.id for s in every) == sorted([a.name, b.name])
    assert [s.id for s in gen.Promoted(name="p", source="a").scenarios(_context(tmp_path))] == [a.name]


def test_promoted_that_finds_nothing_yields_nothing_and_says_it_may(tmp_path: Path) -> None:
    """A regression case is declared before its first failure is promoted; collection warns by name."""
    assert gen.Promoted(name="p", source="nobody").scenarios(_context(tmp_path)) == []
    write_scenario(Scenario(generator="a", params={"i": 1}, files={"x.md": "1"}), tmp_path / "evals" / "fixtures")
    assert gen.Promoted(name="p", source="nobody").scenarios(_context(tmp_path)) == []
    assert gen.Promoted.may_be_empty and gen.Adversarial.may_be_empty
    assert not gen.Table.may_be_empty and not gen.Generated.may_be_empty


# -- Adversarial -------------------------------------------------------------------


def test_an_adversary_is_deterministic_and_spends_exactly_its_budget(tmp_path: Path) -> None:
    first = _adversary().scenarios(_context(tmp_path))
    again = _adversary().scenarios(_context(tmp_path))
    assert [s.id for s in first] == [s.id for s in again] and len(first) == 6
    assert len({s.fingerprint for s in first}) == 6  # no two mutants are the same bytes
    assert all(_parent(s) in {p.id for p in SEEDS.scenarios(_context(tmp_path))} for s in first)
    assert [s.id for s in _adversary(seed=1).scenarios(_context(tmp_path))] != [s.id for s in first]


def test_an_adversary_reruns_stored_failures_worst_first_up_to_half_its_budget(tmp_path: Path) -> None:
    store = tmp_path / "store"
    past = _adversary().scenarios(_context(tmp_path))
    for s in past:
        write_scenario(s, store)
    foreign = write_scenario(Scenario(generator="other", params={"i": 1}, files={"x.md": "x"}), store)
    outcomes = {past[0].id: (1, 3), past[1].id: (2, 2), past[2].id: (1, 2), past[3].id: (0, 4), foreign.name: (5, 5)}
    context = _context(tmp_path, outcomes=outcomes, store=ScenarioStore(store))

    now = _adversary().scenarios(context)

    assert [s.id for s in now[:3]] == [past[1].id, past[2].id, past[0].id]  # budget 6: three confirmations
    assert len(now) == 6 and len({s.id for s in now}) == 6  # exploring never re-yields a confirmed id
    assert foreign.name not in {s.id for s in now}


def test_exploring_mutates_the_parent_that_failed_more_often(tmp_path: Path) -> None:
    """Weight (f+1)/(n+2): a parent failing 5/5 weighs 6/7, one passing 5/5 weighs 1/7."""
    weak, strong = SEEDS.scenarios(_context(tmp_path))
    context = _context(tmp_path, outcomes={weak.id: (5, 5), strong.id: (0, 5)})
    parents = Counter(_parent(s) for s in _adversary(budget=40).scenarios(context))
    assert parents[weak.id] > 2 * parents[strong.id] > 0


def test_an_oracle_screens_out_silent_mutants_and_repeats_of_one_signal_set(tmp_path: Path) -> None:
    def oracle(files: Files) -> frozenset[str]:
        text = "".join(str(c) for c in files.values())
        return frozenset(ch for ch in "AB" if ch in text)

    kept = _adversary(mutators=[add_a, add_b, append_noise], budget=10, oracle=oracle).scenarios(_context(tmp_path))
    signals = [oracle(dict(s.files)) for s in kept]
    assert all(signals) and len(set(signals)) == len(signals)
    assert len(kept) <= 3  # only {A}, {B} and {A, B} differ in kind, whatever the budget


def test_a_second_sweep_explores_ids_never_sampled_and_does_not_exhaust(tmp_path: Path) -> None:
    """The draws are salted by how many mutants were sampled, so history moves the search on."""
    seen: set[str] = set()
    outcomes: dict[str, tuple[int, int]] = {}
    for _ in range(3):
        context = _context(tmp_path, outcomes=outcomes, store=ScenarioStore(tmp_path / "store"))
        now = _adversary().scenarios(context)
        assert len(now) == 6  # every sweep spends its whole budget: nothing failed, nothing to confirm
        assert not seen & {s.id for s in now}
        seen |= {s.id for s in now}
        outcomes |= _swept(tmp_path, now, (0, 1))
    assert len(seen) == 18


def test_confirmed_and_explored_mutants_never_share_an_id_or_repeat_a_sampled_one(tmp_path: Path) -> None:
    first = _adversary().scenarios(_context(tmp_path))
    outcomes = _swept(tmp_path, first, (0, 2)) | _swept(tmp_path, first[:4], (2, 2))
    context = _context(tmp_path, outcomes=outcomes, store=ScenarioStore(tmp_path / "store"))
    now = _adversary().scenarios(context)
    confirmed, explored = now[:3], now[3:]
    assert {s.id for s in confirmed} <= {s.id for s in first[:4]}
    assert all(s.fingerprint == Scenario.promoted(tmp_path / "store" / s.id).fingerprint for s in confirmed)
    assert len(explored) == 3 and not {s.id for s in explored} & {s.id for s in first}
    assert len({s.id for s in now}) == 6


def test_a_mutants_samples_are_credited_to_the_parent_it_was_bred_from(tmp_path: Path) -> None:
    """No seed was ever sampled itself: the weight comes only from its stored offspring."""
    weak = next(iter(SEEDS.scenarios(_context(tmp_path)))).id
    first = _adversary(budget=10).scenarios(_context(tmp_path))
    assert {_parent(s) for s in first} == {p.id for p in SEEDS.scenarios(_context(tmp_path))}
    outcomes: dict[str, tuple[int, int]] = {}
    for s in first:
        outcomes |= _swept(tmp_path, [s], (5, 5) if _parent(s) == weak else (0, 1))
    context = _context(tmp_path, outcomes=outcomes, store=ScenarioStore(tmp_path / "store"))
    explored = [s for s in _adversary(budget=60).scenarios(context) if s.params[gen.MUTATION_KEY]["generation"]]
    parents = Counter(_parent(s) for s in explored)
    strong = parents.keys() - {weak}
    assert parents[weak] > 3 * sum(parents[p] for p in strong) > 0


def test_a_rejected_mutant_does_not_spend_its_signal_set(tmp_path: Path) -> None:
    """A mutant that changed nothing is dropped before the oracle, so its signals stay free for a real one."""

    def unchanged(files: Files, draw: Draw) -> Files:
        return files

    def oracle(files: Files) -> frozenset[str]:
        return frozenset({"A"})

    seeds = gen.Table(name="seeds", rows=[{"n": 1}], build=lambda row: {"a.md": "A\n"})
    for seed in range(10):
        kept = _adversary(seeds=seeds, mutators=[unchanged, append_noise], depth=1, oracle=oracle, seed=seed)
        (only,) = kept.scenarios(_context(tmp_path))
        assert only.params[gen.MUTATION_KEY]["mutators"] == ["append_noise"]


def test_a_mutant_inherits_its_parents_params_expectations_and_task(tmp_path: Path) -> None:
    seeds = gen.Table(
        name="seeds",
        rows=[{"target": "a.md", "recall": 0.9}],
        build=_doc,
        label="target",
        task="Fix {target}",
        expect=["recall"],
    )
    (child,) = _adversary(seeds=seeds, budget=1, mutators=[add_a, add_b], depth=2).scenarios(_context(tmp_path))
    (parent,) = seeds.scenarios(_context(tmp_path))
    mutation = child.params[gen.MUTATION_KEY]
    assert {k: v for k, v in child.params.items() if k != gen.MUTATION_KEY} == {"target": "a.md"}
    assert (dict(child.expect), child.task, child.merged["recall"]) == ({"recall": 0.9}, "Fix a.md", 0.9)
    assert (mutation["parent"], mutation["generation"]) == (parent.id, 0)
    assert child.label == f"a.md-{'-'.join(mutation['mutators'])}"


def test_a_mutants_chain_never_applies_one_mutator_twice(tmp_path: Path) -> None:
    kept = _adversary(mutators=[add_a, add_b], depth=6, budget=4).scenarios(_context(tmp_path))
    chains = [s.params[gen.MUTATION_KEY]["mutators"] for s in kept]
    assert chains and all(len(c) == len(set(c)) for c in chains)


def test_an_adversary_needs_a_mutator_and_a_seed(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="at least one mutator"):
        _adversary(mutators=[]).scenarios(_context(tmp_path))
    empty = gen.Table(name="none", rows=[], build=_doc)
    with pytest.raises(ValueError, match="yielded no scenarios"):
        _adversary(seeds=empty).scenarios(_context(tmp_path))


# -- text mutators -----------------------------------------------------------------

TEXT = "# Head\n\n" + "\n\n".join(f"Paragraph {i} has a few words in it." for i in range(30)) + "\n"


@pytest.mark.parametrize(
    ("mutator", "undo"),
    [
        (gen.CRLF, lambda t: t.replace("\r\n", "\n")),
        (gen.TRAILING_WHITESPACE, lambda t: "\n".join(line.rstrip(" ") for line in t.split("\n"))),
        (gen.ZERO_WIDTH, lambda t: t.replace("​", "")),
        (gen.NBSP, lambda t: t.replace(" ", " ")),
        (gen.NO_FINAL_NEWLINE, lambda t: t + "\n"),
    ],
    ids=lambda m: getattr(m, "name", ""),
)
def test_each_encoding_mutator_changes_the_text_and_nothing_it_says(mutator: gen.TextMutator, undo: Any) -> None:
    out = mutator({"doc.md": TEXT}, Draw(mutator.name))["doc.md"]
    assert out != TEXT and undo(out) == TEXT


def test_the_paragraph_mutators_keep_the_paragraphs_and_the_head() -> None:
    paragraphs = TEXT.split("\n\n")
    duplicated = str(gen.DUPLICATE_PARAGRAPH({"d.md": TEXT}, Draw("dup"))["d.md"]).split("\n\n")
    assert len(duplicated) == len(paragraphs) + 1 and set(duplicated) == set(paragraphs)
    shuffled = str(gen.SHUFFLE_PARAGRAPHS({"d.md": TEXT}, Draw("shuf"))["d.md"]).split("\n\n")
    assert (
        shuffled[0] == "# Head"
        and sorted(p.strip() for p in shuffled) == sorted(p.strip() for p in paragraphs)
        and shuffled != paragraphs
    )


def test_a_text_mutator_touches_one_text_file_and_names_itself() -> None:
    files: Files = {"a.md": "x\n", "b.py": "y\n", "c.bin": b"\n"}
    out = gen.CRLF(files, Draw("one"))
    assert out == {"a.md": "x\r\n", "b.py": "y\n", "c.bin": b"\n"} and files["a.md"] == "x\n"
    assert gen.CRLF({"b.py": "y\n"}, Draw("none")) == {"b.py": "y\n"}  # nothing to touch: unchanged
    assert gen.CRLF.__name__ == "crlf" and len(gen.TEXT_MUTATORS) == 7
