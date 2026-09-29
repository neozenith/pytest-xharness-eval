"""``model.effort``: the effort vocabulary and how an alias resolves on a ladder (ADR 0049)."""

# Standard Library
import re

# Third Party
import pytest

# Our Libraries
from pytest_xharness_eval import harness as harnesses
from pytest_xharness_eval.harness import claude as claude_harness
from pytest_xharness_eval.harness import codex as codex_harness
from pytest_xharness_eval.model import effort as effort_words

CLAUDE_LADDER = claude_harness.CLAUDE_EFFORTS

CODEX_LADDER = codex_harness.CODEX_EFFORTS


@pytest.mark.parametrize(("alias", "rung"), [("min", "low"), ("mid", "high"), ("max", "max")])
def test_a_portable_alias_names_a_position_on_each_harnesss_own_ladder(alias: str, rung: str) -> None:
    """``min``/``mid``/``max`` name a position, and both shipped ladders answer the same.

    That the two agree is a fact about these two CLIs, not a rule: the ladder lives on the
    harness class, so the resolution is by index either way.
    """
    assert effort_words.resolve(alias, CLAUDE_LADDER, harness="claude") == rung
    assert effort_words.resolve(alias, CODEX_LADDER, harness="codex") == rung


#: A third harness's ladder: shorter, and sharing only its middle with the shipped two.
#: Divergence has to be written down here, because both shipped CLIs declare the same five
#: rungs and so cannot demonstrate a rung one harness has and another lacks.
PROBE_LADDER = ("cheap", "medium", "lavish")


@pytest.mark.parametrize(("alias", "rung"), [("min", "cheap"), ("mid", "medium"), ("max", "lavish")])
def test_an_alias_follows_a_ladder_that_is_not_the_shipped_one(alias: str, rung: str) -> None:
    """The resolution is positional, so a harness with its own vocabulary needs no special case."""
    assert effort_words.resolve(alias, PROBE_LADDER, harness="probe") == rung


def test_a_native_rung_resolves_to_itself_and_a_foreign_one_is_refused() -> None:
    """Exact, never nearest.

    Rounding a missing rung to the closest one this harness does have would silently run a
    different experiment than the matrix line asked for, and bill it in full.
    """
    assert effort_words.resolve("high", CLAUDE_LADDER, harness="claude") == "high"
    with pytest.raises(effort_words.UnknownEffort, match="no effort rung 'medium'"):
        effort_words.resolve("medium", ("cheap", "lavish"), harness="probe")


def test_a_rung_the_provider_rejects_is_not_in_the_vocabulary_at_all() -> None:
    """``minimal`` was in codex-cli's local enum and is not a rung any gpt-5.6 model accepts.

    A paid sweep proved it: the CLI forwarded the value, the API answered 400 ``unsupported
    _value``, and the run exited 1 having produced nothing. The ladder is pinned to the
    provider's answer, so the word is now unknown everywhere rather than accepted here and
    rejected on the wire (ADR 0049).
    """
    for word in ("minimal", "none", "ultra", "persistent"):
        with pytest.raises(effort_words.UnknownEffort, match="unknown effort"):
            effort_words.resolve(word, CODEX_LADDER, harness="codex")


def test_a_word_outside_the_vocabulary_names_the_whole_vocabulary() -> None:
    """A typo must not reach a CLI: both of them accept one, warn at most, and bill a run."""
    with pytest.raises(effort_words.UnknownEffort, match="unknown effort 'hgih'"):
        effort_words.resolve("hgih", CLAUDE_LADDER, harness="claude")


def test_a_harness_with_no_ladder_cannot_be_asked_for_an_effort() -> None:
    """An empty ladder means "no effort control", never "run it at the default"."""
    with pytest.raises(effort_words.UnknownEffort, match="declares no effort ladder"):
        effort_words.resolve("high", (), harness="probe")


def test_the_report_page_ranks_rungs_on_the_ladders_the_harnesses_declare(pytestconfig: pytest.Config) -> None:
    """``LADDER`` in ``report-ui/src/lib/effort.ts`` is the page's copy of the rung order.

    The page sorts chips, table columns, summary rows, sidebar branches and chart lines by it, so a
    rung a harness gains here and the page lacks would sort after every known rung as if it came
    from a third CLI, and a reordered ladder would print ``high`` above ``low``. The page cannot
    import Python, so the copy is pinned here instead: every registered harness's ladder must be
    the page's ladder read in order, and the page may name no rung no harness has (ADR 0049).
    """
    source = (pytestconfig.rootpath / "report-ui" / "src" / "lib" / "effort.ts").read_text(encoding="utf-8")
    declared = re.search(r"export const LADDER\b[^=]*=\s*\[([^\]]*)\]", source)
    assert declared, "report-ui/src/lib/effort.ts no longer declares LADDER as an array literal"
    page_ladder = tuple(re.findall(r'"([^"]+)"', declared.group(1)))
    ladders = {name: tuple(harnesses.get(name).efforts) for name in harnesses.names()}
    for name, ladder in ladders.items():
        in_page_order = tuple(rung for rung in page_ladder if rung in ladder)
        assert in_page_order == ladder, f"{name}'s ladder is not the page's, in order"
    assert set(page_ladder) == {rung for ladder in ladders.values() for rung in ladder}
    assert set(page_ladder) <= {word.value for word in effort_words.Effort}
