"""``model.matrix``: expanding and narrowing the harness/model/effort matrix (ADR 0015, ADR 0049)."""


# Standard Library

# Third Party
import pytest

# Our Libraries
from pytest_xharness_eval import Cell
from pytest_xharness_eval.model import matrix as mx
from pytest_xharness_eval.model import registry

#: A fixed six-entry matrix to expand and narrow; what the plugin default is lives in the
#: catalogue and is pinned by ``tests/test_plugin.py`` (ADR 0058).
SIX = [
    "claude/claude-opus-5",
    "claude/claude-sonnet-5",
    "claude/claude-haiku-4-5-20251001",
    "codex/gpt-5.6-sol",
    "codex/gpt-5.6-luna",
    "codex/gpt-5.6-terra",
]


def test_catalogued_lists_every_harness_model_in_declared_order() -> None:
    entries = mx.catalogued(registry.catalogue())
    assert entries[0] == "claude/claude-haiku-4-5-20251001"
    assert entries.index("claude/claude-fable-5-1") < entries.index("codex/gpt-5.6-luna")
    assert set(SIX) <= set(entries)


def test_expand_a_matrix() -> None:
    cells = mx.expand(SIX)
    assert [c.id for c in cells] == [
        "claude/claude-opus-5",
        "claude/claude-sonnet-5",
        "claude/claude-haiku-4-5-20251001",
        "codex/gpt-5.6-sol",
        "codex/gpt-5.6-luna",
        "codex/gpt-5.6-terra",
    ]
    assert cells[0].id == "claude/claude-opus-5"
    assert cells[0].harness == "claude"


@pytest.mark.parametrize("entry", ["gemini/pro", "claude", "claude/", "/opus"])
def test_expand_rejects_malformed_entries(entry: str) -> None:
    with pytest.raises(ValueError, match="matrix entry must be"):
        mx.expand([entry])


def test_narrow_by_harness_and_model() -> None:
    cells = mx.expand(SIX)
    assert [c.id for c in mx.narrow(cells, None, ["codex"])] == [
        "codex/gpt-5.6-sol",
        "codex/gpt-5.6-luna",
        "codex/gpt-5.6-terra",
    ]
    assert mx.narrow(cells, ["opus"], None) == [Cell("claude", "claude-opus-5")]
    assert mx.narrow(cells, ["codex/gpt-5.6-sol"], None) == [Cell("codex", "gpt-5.6-sol")]
    assert mx.narrow(cells, ["opus"], ["codex"]) == []
    assert mx.narrow(cells, None, None) == cells


def test_a_matrix_entry_may_name_an_effort_and_resolves_it_once() -> None:
    """The third component is resolved at expansion, so nothing downstream holds an alias."""
    cells = mx.expand(["claude/claude-opus-5/mid", "codex/gpt-5.6-sol/max", "claude/claude-opus-5"])
    assert cells == [
        Cell("claude", "claude-opus-5", "high"),
        Cell("codex", "gpt-5.6-sol", "max"),
        Cell("claude", "claude-opus-5"),
    ]
    # The node id shows the rung that was sent, and omits the component entirely when the
    # entry named none -- so a pre-0049 matrix keys its history exactly as it always did.
    assert [c.id for c in cells] == [
        "claude/claude-opus-5/high",
        "codex/gpt-5.6-sol/max",
        "claude/claude-opus-5",
    ]


@pytest.mark.parametrize(
    ("entry", "match"),
    [
        ("claude/claude-opus-5/hgih", "unknown effort"),
        ("claude/claude-opus-5/minimal", "unknown effort"),
        ("claude/claude-opus-5/high/extra", "matrix entry must be"),
    ],
)
def test_a_bad_effort_stops_the_sweep_at_expansion_before_any_spend(entry: str, match: str) -> None:
    """ADR 0007's rule for an unpriced model, applied to the rung (ADR 0049).

    The offending line is named in front of the harness's own message, because the line is
    what the reader has to go and edit.
    """
    with pytest.raises(ValueError, match=match):
        mx.expand([entry])


def test_narrow_by_effort_matches_the_resolved_rung() -> None:
    cells = mx.expand(["claude/claude-opus-5/high", "claude/claude-opus-5/low", "claude/claude-opus-5"])
    assert mx.narrow(cells, None, None, ["high"]) == [Cell("claude", "claude-opus-5", "high")]
    # An alias filters by what it resolves to on that harness, so --effort mid finds the
    # cell that ``.../mid`` expanded into.
    assert mx.narrow(cells, None, None, ["mid"]) == [Cell("claude", "claude-opus-5", "high")]
    # A cell that named no rung has none to compare a CLI default against, so it is only
    # selectable explicitly and is never swept up by a rung filter.
    assert mx.narrow(cells, None, None, ["low", ""]) == [
        Cell("claude", "claude-opus-5", "low"),
        Cell("claude", "claude-opus-5"),
    ]
    assert mx.narrow(cells, None, None, None) == cells


def test_treat_keeps_the_control_first_and_crosses_every_cell() -> None:
    """The control is always swept beside a treatment: it is what the treatment is compared to (ADR 0055)."""
    cells = mx.expand(["claude/claude-haiku-4-5", "codex/gpt-5.6-luna"])
    assert [c.id for c in mx.treat(cells, ["lean-ci"])] == [
        "claude/claude-haiku-4-5",
        "codex/gpt-5.6-luna",
        "claude/claude-haiku-4-5+lean-ci",
        "codex/gpt-5.6-luna+lean-ci",
    ]
    # No treatments is exactly the matrix it was before ADR 0055.
    assert mx.treat(cells, []) == cells


def test_a_treated_cell_id_puts_the_treatment_after_the_rung() -> None:
    assert Cell("claude", "claude-opus-5", "high", "lean-ci").id == "claude/claude-opus-5/high+lean-ci"


def test_narrow_by_treatment_names_the_control_by_its_reserved_word() -> None:
    cells = mx.treat(mx.expand(["claude/claude-haiku-4-5"]), ["lean-ci", "terse"])
    assert [c.treatment for c in mx.narrow(cells, None, None, None, ["control"])] == [None]
    assert [c.treatment for c in mx.narrow(cells, None, None, None, ["lean-ci", "control"])] == [None, "lean-ci"]
    assert mx.narrow(cells, None, None, None, None) == cells
